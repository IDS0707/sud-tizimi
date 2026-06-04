"""Admin / management panel API (TZ section 6: boshqaruv paneli).

Exposes platform-wide statistics for the admin dashboard. Requires a valid API
key, demonstrating the SaaS access-control model end to end.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.database.models import (
    AiResult,
    ApiKey,
    Document,
    Entity,
    OcrResult,
    Page,
    Task,
    User,
)
from app.database.session import get_db
from app.schemas.admin import AdminStats

router = APIRouter(prefix="/admin", tags=["admin"])


def _count(db: Session, model) -> int:
    return db.query(func.count()).select_from(model).scalar() or 0


def _build_stats(db: Session) -> AdminStats:
    by_type = dict(
        db.query(Document.file_type, func.count()).group_by(Document.file_type).all()
    )
    by_status = dict(
        db.query(Document.status, func.count()).group_by(Document.status).all()
    )
    total_bytes = db.query(func.coalesce(func.sum(Document.size_bytes), 0)).scalar() or 0

    return AdminStats(
        documents=_count(db, Document),
        pages=_count(db, Page),
        ocr_results=_count(db, OcrResult),
        entities=_count(db, Entity),
        ai_results=_count(db, AiResult),
        tasks=_count(db, Task),
        api_keys=_count(db, ApiKey),
        users=_count(db, User),
        documents_by_type={str(k): int(v) for k, v in by_type.items()},
        documents_by_status={str(k): int(v) for k, v in by_status.items()},
        total_storage_bytes=int(total_bytes),
    )


@router.get("/overview", response_model=AdminStats, summary="Tizim holati (oddiy panel)")
def overview(db: Session = Depends(get_db)) -> AdminStats:
    """Open dashboard stats — no API key needed (used by the simple admin panel)."""
    return _build_stats(db)


@router.get("/stats", response_model=AdminStats, summary="Platforma statistikasi (API)")
def stats(db: Session = Depends(get_db), _=Depends(require_api_key)) -> AdminStats:
    """Same stats, but requires an API key — for programmatic/SaaS access."""
    return _build_stats(db)
