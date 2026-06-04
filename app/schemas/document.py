"""Document & page schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PageOut(BaseModel):
    """A single page of a document."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    page_number: int
    text: str | None = None
    width: float | None = None
    height: float | None = None
    image_path: str | None = None


class DocumentOut(BaseModel):
    """Document summary (list view)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    public_id: str
    filename: str
    file_type: str
    category: str
    mime_type: str | None = None
    size_bytes: int
    page_count: int
    status: str
    created_at: datetime


class DocumentDetail(DocumentOut):
    """Full document detail including pages and metadata."""

    doc_metadata: dict | None = None
    pages: list[PageOut] = []


class UploadResponse(BaseModel):
    """Returned immediately after a successful upload."""

    document: DocumentOut
    task_id: str | None = None
    message: str = "Fayl muvaffaqiyatli yuklandi"
