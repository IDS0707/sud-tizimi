"""SQLAlchemy ORM models — the database schema (TZ section 8).

Nine tables map one-to-one to the specification:

    users • documents • pages • ocr_results • search_index
    entities • ai_results • api_keys • tasks

The schema is intentionally database-agnostic (generic ``JSON``/``Text`` types)
so it runs identically on SQLite (dev) and PostgreSQL (prod).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return uuid.uuid4().hex


# --------------------------------------------------------------------------- #
#  Status / type constants (kept as plain strings for cross-DB portability)
# --------------------------------------------------------------------------- #
class DocStatus:
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PARSED = "parsed"
    OCR_DONE = "ocr_done"
    INDEXED = "indexed"
    FAILED = "failed"


class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class FileCategory:
    IMAGE = "image"
    DOCUMENT = "document"
    SPECIAL = "special"


# --------------------------------------------------------------------------- #
#  Mixins
# --------------------------------------------------------------------------- #
class TimestampMixin:
    """Adds ``created_at`` / ``updated_at`` columns."""

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )


# --------------------------------------------------------------------------- #
#  1. users
# --------------------------------------------------------------------------- #
class User(Base, TimestampMixin):
    """Platform users (TZ 8: ``users``)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    documents: Mapped[list["Document"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r}>"


# --------------------------------------------------------------------------- #
#  2. documents
# --------------------------------------------------------------------------- #
class Document(Base, TimestampMixin):
    """Uploaded documents — top-level record (TZ 8: ``documents``)."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(32), default=_new_uuid, unique=True, index=True, nullable=False
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), index=True, nullable=False)  # pdf, docx...
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    category: Mapped[str] = mapped_column(String(16), default=FileCategory.DOCUMENT, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=DocStatus.UPLOADED, index=True)
    doc_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    owner: Mapped["User | None"] = relationship(back_populates="documents")
    pages: Mapped[list["Page"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Page.page_number"
    )
    ocr_results: Mapped[list["OcrResult"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    entities: Mapped[list["Entity"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    ai_results: Mapped[list["AiResult"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    index_entries: Mapped[list["SearchIndex"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    # --- Court-specific fields, stored in doc_metadata (no schema migration) ---
    @property
    def doc_type(self) -> str | None:
        """Court document type: ariza, qaror, bayonnoma, dalil, …"""
        return (self.doc_metadata or {}).get("doc_type")

    @property
    def case_number(self) -> str | None:
        """Associated court case number (ish raqami)."""
        return (self.doc_metadata or {}).get("case_number")

    @property
    def note(self) -> str | None:
        return (self.doc_metadata or {}).get("note")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Document id={self.id} {self.filename!r} status={self.status}>"


# --------------------------------------------------------------------------- #
#  3. pages
# --------------------------------------------------------------------------- #
class Page(Base):
    """Individual pages of a document (TZ 8: ``pages``)."""

    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    width: Mapped[float | None] = mapped_column(Float, nullable=True)
    height: Mapped[float | None] = mapped_column(Float, nullable=True)
    layout: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # blocks: title/text/table...
    image_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="pages")
    ocr_results: Mapped[list["OcrResult"]] = relationship(
        back_populates="page", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Page doc={self.document_id} #{self.page_number}>"


# --------------------------------------------------------------------------- #
#  4. ocr_results
# --------------------------------------------------------------------------- #
class OcrResult(Base):
    """Text recognised from images/scans (TZ 8: ``ocr_results``)."""

    __tablename__ = "ocr_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    page_id: Mapped[int | None] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"), index=True, nullable=True
    )
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # boxes: [{"text": ..., "bbox": [x1,y1,x2,y2], "confidence": 0.97}, ...]
    boxes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    engine: Mapped[str] = mapped_column(String(32), default="stub", nullable=False)
    lang: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="ocr_results")
    page: Mapped["Page | None"] = relationship(back_populates="ocr_results")


# --------------------------------------------------------------------------- #
#  5. search_index
# --------------------------------------------------------------------------- #
class SearchIndex(Base):
    """Search-ready normalised text (TZ 8: ``search_index``)."""

    __tablename__ = "search_index"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    page_id: Mapped[int | None] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"), index=True, nullable=True
    )
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)        # original text chunk
    normalized: Mapped[str] = mapped_column(Text, nullable=False)     # lowercased for matching
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="parser", nullable=False)  # parser|ocr
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="index_entries")


# --------------------------------------------------------------------------- #
#  6. entities
# --------------------------------------------------------------------------- #
class Entity(Base):
    """Important data extracted from documents (TZ 8: ``entities``)."""

    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    page_id: Mapped[int | None] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"), nullable=True
    )
    entity_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)  # date/money...
    value: Mapped[str] = mapped_column(String(1024), nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="entities")


# --------------------------------------------------------------------------- #
#  7. ai_results
# --------------------------------------------------------------------------- #
class AiResult(Base):
    """AI analysis output and summaries (TZ 8: ``ai_results``)."""

    __tablename__ = "ai_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # summary|qa|extraction|classify
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)  # RAG citations
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="ai_results")


# --------------------------------------------------------------------------- #
#  8. api_keys
# --------------------------------------------------------------------------- #
class ApiKey(Base):
    """API keys for external access (TZ 8: ``api_keys``)."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    hashed_key: Mapped[str] = mapped_column(String(128), nullable=False)  # never store raw key
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    user: Mapped["User | None"] = relationship(back_populates="api_keys")


# --------------------------------------------------------------------------- #
#  9. tasks
# --------------------------------------------------------------------------- #
class Task(Base):
    """Background task state (TZ 8: ``tasks``; exposed via GET /task/{id})."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_uuid)
    type: Mapped[str] = mapped_column(String(32), nullable=False)  # upload|ocr|parse|export|ai
    status: Mapped[str] = mapped_column(String(16), default=TaskStatus.PENDING, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0..100
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Task id={self.id} type={self.type} status={self.status}>"
