"""Search schemas (TZ section 3 / 7: POST /api/v1/search)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """A keyword query across all indexed documents."""

    query: str = Field(min_length=1, description="Qidiriladigan kalit so'z")
    limit: int = Field(default=30, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    document_id: int | None = Field(default=None, description="Faqat shu hujjat ichida qidirish")


class SearchResultItem(BaseModel):
    """One search hit with a highlighted context snippet."""

    document_id: int
    public_id: str
    filename: str
    file_type: str
    page_number: int | None = None
    score: float
    snippet: str          # HTML with <mark> around matches
    context: str          # plain-text context


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResultItem]
