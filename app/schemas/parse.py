"""Parse schemas (TZ section 7: POST /api/v1/parse)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.document import DocumentDetail


class ParseRequest(BaseModel):
    """Parse (or re-parse) an uploaded document."""

    document_id: int
    run_ocr: bool = True
    lang: str | None = None


class TableOut(BaseModel):
    """A reconstructed table (TZ section 2.7)."""

    page_number: int
    rows: list[list[str]]


class ParseResponse(BaseModel):
    """Full parse output: document detail + extracted tables."""

    document: DocumentDetail
    parser: str
    tables: list[TableOut] = Field(default_factory=list)
