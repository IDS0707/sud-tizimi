"""PDF parser (TZ section 2.2).

Handles both flavours of PDF described in the spec:

  * **Text PDF** — text is embedded and copied out directly.
  * **Scanned PDF** — pages are images; they are rendered to PNG and flagged
    ``needs_ocr`` so the OCR engine can read them.

Built on PyMuPDF (``fitz``). If PyMuPDF is not installed the parser degrades to
an empty result with a clear metadata note instead of raising.
"""
from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.parsers.base import BaseParser, ParsedPage, ParseResult, ParsedTable
from app.utils.logger import get_logger

log = get_logger("udip.parsers.pdf")

try:
    import fitz  # PyMuPDF

    _HAS_FITZ = True
except Exception:  # pragma: no cover - optional dependency
    _HAS_FITZ = False

# Below this many characters a page is treated as "scanned" → send to OCR.
_MIN_TEXT_CHARS = 12
_RENDER_DPI = 200


class PdfParser(BaseParser):
    name = "pdf"
    extensions = ("pdf",)

    def parse(self, file_path: str, *, render_dir: str | None = None, **kwargs) -> ParseResult:
        if not _HAS_FITZ:
            log.warning("PyMuPDF not installed; cannot parse PDF %s", file_path)
            return ParseResult(parser=self.name, metadata={"error": "PyMuPDF not installed"})

        render_root = Path(render_dir or settings.upload_dir / "_pages")
        render_root.mkdir(parents=True, exist_ok=True)

        result = ParseResult(parser=self.name)
        doc = fitz.open(file_path)
        result.metadata = {
            "page_count": doc.page_count,
            "title": doc.metadata.get("title") if doc.metadata else None,
            "author": doc.metadata.get("author") if doc.metadata else None,
            **({k: v for k, v in (doc.metadata or {}).items() if v} ),
        }

        stem = Path(file_path).stem
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            rect = page.rect
            parsed = ParsedPage(
                page_number=i + 1,
                text=text,
                width=float(rect.width),
                height=float(rect.height),
            )
            if len(text) < _MIN_TEXT_CHARS:
                # Likely a scanned page — render to image for OCR.
                parsed.needs_ocr = True
                img_path = render_root / f"{stem}_p{i + 1}.png"
                try:
                    pix = page.get_pixmap(dpi=_RENDER_DPI)
                    pix.save(str(img_path))
                    parsed.image_path = str(img_path)
                except Exception as exc:  # pragma: no cover
                    log.warning("Failed to render page %d: %s", i + 1, exc)
            else:
                # Text page — analyse layout (headings) and detect tables.
                parsed.blocks = self._layout_blocks(page)
                for rows in self._extract_tables(page):
                    result.tables.append(ParsedTable(page_number=i + 1, rows=rows))
                    parsed.blocks.append({"type": "table", "rows": rows})
            result.pages.append(parsed)

        doc.close()
        scanned = sum(1 for p in result.pages if p.needs_ocr)
        log.info(
            "Parsed PDF %s: %d pages (%d need OCR, %d tables)",
            file_path, result.page_count, scanned, len(result.tables),
        )
        return result

    # ------------------------------------------------------------------ #
    #  Layout & table helpers (TZ 2.6 / 2.7)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _layout_blocks(page) -> list[dict]:
        """Classify a text page's blocks into headings vs body by font size."""
        try:
            data = page.get_text("dict")
        except Exception:  # pragma: no cover
            return []

        # Body font size = the size carrying the most characters (body text
        # dominates by volume; a short large-font title must not skew this).
        from collections import Counter

        size_chars: Counter = Counter()
        for blk in data.get("blocks", []):
            for line in blk.get("lines", []):
                for span in line.get("spans", []):
                    txt = span.get("text", "").strip()
                    if txt:
                        size_chars[round(span.get("size", 0) * 2) / 2] += len(txt)
        if not size_chars:
            return []
        body_size = max(size_chars, key=size_chars.get)
        heading_size = body_size * 1.2

        blocks: list[dict] = []
        for blk in data.get("blocks", []):
            if blk.get("type") != 0:  # 0 = text block (1 = image)
                if blk.get("type") == 1:
                    blocks.append({"type": "image", "bbox": list(blk.get("bbox", []))})
                continue
            lines_text: list[str] = []
            max_size = 0.0
            bold = False
            for line in blk.get("lines", []):
                spans = line.get("spans", [])
                lines_text.append("".join(s.get("text", "") for s in spans))
                for s in spans:
                    max_size = max(max_size, s.get("size", 0))
                    if "bold" in (s.get("font", "").lower()):
                        bold = True
            text = "\n".join(t for t in lines_text if t.strip()).strip()
            if not text:
                continue
            is_heading = (max_size >= heading_size or (bold and len(text) < 80))
            blocks.append({
                "type": "heading" if is_heading else "text",
                "text": text,
                "bbox": list(blk.get("bbox", [])),
            })
        return blocks

    @staticmethod
    def _extract_tables(page) -> list[list[list[str]]]:
        """Extract tables from a text page using PyMuPDF's table finder."""
        out: list[list[list[str]]] = []
        try:
            finder = page.find_tables()
        except Exception:  # pragma: no cover - older PyMuPDF / odd PDFs
            return out
        for tbl in getattr(finder, "tables", []):
            try:
                rows = tbl.extract()
            except Exception:  # pragma: no cover
                continue
            clean = [["" if c is None else str(c).strip() for c in row] for row in rows]
            clean = [r for r in clean if any(c for c in r)]
            if len(clean) >= 1:
                out.append(clean)
        return out


pdf_parser = PdfParser()
