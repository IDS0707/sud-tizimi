"""AI / chat / export schemas (TZ sections 2.10–2.12, 7)."""
from __future__ import annotations

from pydantic import BaseModel, Field


# ---- chat (RAG) ---------------------------------------------------- #
class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    document_id: int | None = Field(default=None, description="Bitta hujjat doirasida")
    top_k: int | None = None


class ChatSource(BaseModel):
    page_number: int | None = None
    snippet: str


class ChatResponse(BaseModel):
    question: str
    answer: str
    model: str
    sources: list[ChatSource] = []


# ---- summary ------------------------------------------------------- #
class SummarizeRequest(BaseModel):
    document_id: int
    max_sentences: int = Field(default=5, ge=1, le=20)


class SummaryResponse(BaseModel):
    document_id: int
    summary: str
    model: str


# ---- entities ------------------------------------------------------ #
class EntityOut(BaseModel):
    entity_type: str
    value: str
    normalized_value: str | None = None
    context: str | None = None
    page_id: int | None = None


class EntitiesResponse(BaseModel):
    document_id: int
    count: int
    entities: list[EntityOut]


# ---- export -------------------------------------------------------- #
class ExportRequest(BaseModel):
    document_id: int
    format: str = Field(description="txt | json | md | docx")


class ExportResponse(BaseModel):
    format: str
    filename: str
    download_url: str
