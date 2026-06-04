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
    layout: dict | None = None  # {"blocks": [{type, text|rows}, ...]}


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
    # Court-specific (read from doc_metadata)
    doc_type: str | None = None
    case_number: str | None = None
    note: str | None = None


class DocumentDetail(DocumentOut):
    """Full document detail including pages and metadata."""

    doc_metadata: dict | None = None
    pages: list[PageOut] = []


class DocumentUpdate(BaseModel):
    """Editable court fields (stored into doc_metadata)."""

    doc_type: str | None = None       # ariza | qaror | bayonnoma | dalil | ...
    case_number: str | None = None    # ish raqami
    note: str | None = None           # izoh


class UploadResponse(BaseModel):
    """Returned immediately after a successful upload."""

    document: DocumentOut
    task_id: str | None = None
    message: str = "Fayl muvaffaqiyatli yuklandi"
