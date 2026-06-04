"""Common parser contracts shared by every format parser.

A parser turns a stored file into a normalised ``ParseResult``: per-page text,
optional rendered page images (for OCR), tables and document metadata. Keeping
one shape lets the rest of the platform treat PDFs, Word, images, etc. uniformly.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParsedTable:
    """A reconstructed table (TZ section 2.7)."""

    page_number: int
    rows: list[list[str]]
    bbox: list[float] | None = None

    def to_dict(self) -> dict:
        return {"page_number": self.page_number, "rows": self.rows, "bbox": self.bbox}


@dataclass
class ParsedPage:
    """A single page of a parsed document."""

    page_number: int
    text: str = ""
    width: float | None = None
    height: float | None = None
    image_path: str | None = None          # rendered image, used for OCR
    blocks: list[dict] = field(default_factory=list)  # layout blocks (TZ 2.6)
    needs_ocr: bool = False                # True for scanned/empty pages

    def to_dict(self) -> dict:
        return {
            "page_number": self.page_number,
            "text": self.text,
            "width": self.width,
            "height": self.height,
            "image_path": self.image_path,
            "blocks": self.blocks,
            "needs_ocr": self.needs_ocr,
        }


@dataclass
class ParseResult:
    """Normalised output of any parser."""

    pages: list[ParsedPage] = field(default_factory=list)
    tables: list[ParsedTable] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    parser: str = "base"

    @property
    def text(self) -> str:
        """Full document text, pages joined by form feed."""
        return "\n\f\n".join(p.text for p in self.pages if p.text)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def needs_ocr(self) -> bool:
        """True if any page has no extractable text (scanned)."""
        return any(p.needs_ocr for p in self.pages)


class BaseParser:
    """Interface every concrete parser implements."""

    name = "base"
    #: file extensions this parser handles
    extensions: tuple[str, ...] = ()

    def parse(self, file_path: str, **kwargs) -> ParseResult:  # pragma: no cover - abstract
        raise NotImplementedError
