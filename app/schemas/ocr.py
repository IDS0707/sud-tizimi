"""OCR schemas (TZ section 2.1 / 7: POST /api/v1/ocr)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class OcrBox(BaseModel):
    """One recognised text region and where it sits on the page."""

    text: str
    bbox: list[float] = Field(description="[x1, y1, x2, y2] pixel coordinates")
    confidence: float = 0.0


class OcrResultOut(BaseModel):
    """Full OCR result for one image/page."""

    text: str
    boxes: list[OcrBox] = []
    confidence: float = 0.0
    engine: str = "stub"
    lang: str | None = None
    page_number: int | None = None


class OcrRequest(BaseModel):
    """Run OCR against an already-uploaded document."""

    document_id: int
    lang: str | None = None
    async_mode: bool = Field(
        default=False,
        description="If true, returns a task id immediately and runs OCR in the background.",
    )
