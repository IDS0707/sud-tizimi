"""Image parser (TZ section 1.2: JPG, PNG, WEBP).

An image is modelled as a single-page document whose only page must go through
OCR. Pillow is used to read the dimensions; if absent, dimensions are left None.
"""
from __future__ import annotations

from pathlib import Path

from app.parsers.base import BaseParser, ParsedPage, ParseResult
from app.utils.logger import get_logger

log = get_logger("udip.parsers.image")

try:
    from PIL import Image

    _HAS_PIL = True
except Exception:  # pragma: no cover
    _HAS_PIL = False


class ImageParser(BaseParser):
    name = "image"
    extensions = ("jpg", "jpeg", "png", "webp")

    def parse(self, file_path: str, **kwargs) -> ParseResult:
        width = height = None
        if _HAS_PIL:
            try:
                with Image.open(file_path) as im:
                    width, height = float(im.width), float(im.height)
            except Exception as exc:  # pragma: no cover
                log.warning("Could not read image dimensions: %s", exc)

        page = ParsedPage(
            page_number=1,
            text="",
            width=width,
            height=height,
            image_path=str(Path(file_path)),
            needs_ocr=True,
        )
        return ParseResult(parser=self.name, pages=[page], metadata={"page_count": 1})


image_parser = ImageParser()
