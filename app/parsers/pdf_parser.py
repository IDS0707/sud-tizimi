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
from app.parsers.base import BaseParser, ParsedPage, ParseResult
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
            result.pages.append(parsed)

        doc.close()
        scanned = sum(1 for p in result.pages if p.needs_ocr)
        log.info("Parsed PDF %s: %d pages (%d need OCR)", file_path, result.page_count, scanned)
        return result


pdf_parser = PdfParser()
