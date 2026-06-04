"""AI analysis endpoints (TZ section 2.10): summary + entity extraction."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai import analyzer
from app.database.models import Document, Entity
from app.database.session import get_db
from app.schemas.ai import (
    EntitiesResponse,
    EntityOut,
    SummarizeRequest,
    SummaryResponse,
)

router = APIRouter(prefix="/ai", tags=["ai"])


def _require_doc(db: Session, document_id: int) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Hujjat topilmadi")
    return doc


@router.post("/summarize", response_model=SummaryResponse, summary="Hujjatni xulosalash")
def summarize(req: SummarizeRequest, db: Session = Depends(get_db)) -> SummaryResponse:
    _require_doc(db, req.document_id)
    result = analyzer.summarize_document(db, req.document_id, max_sentences=req.max_sentences)
    return SummaryResponse(
        document_id=req.document_id, summary=result.answer or "", model=result.model or "stub"
    )


@router.post("/entities/{document_id}", response_model=EntitiesResponse,
             summary="Muhim ma'lumotlarni ajratish")
def extract_entities(document_id: int, db: Session = Depends(get_db)) -> EntitiesResponse:
    _require_doc(db, document_id)
    entities = analyzer.extract_entities(db, document_id)
    return EntitiesResponse(
        document_id=document_id,
        count=len(entities),
        entities=[EntityOut.model_validate(e, from_attributes=True) for e in entities],
    )


@router.get("/entities/{document_id}", response_model=EntitiesResponse,
            summary="Ajratilgan ma'lumotlarni olish")
def get_entities(document_id: int, db: Session = Depends(get_db)) -> EntitiesResponse:
    _require_doc(db, document_id)
    entities = db.query(Entity).filter(Entity.document_id == document_id).all()
    return EntitiesResponse(
        document_id=document_id,
        count=len(entities),
        entities=[EntityOut.model_validate(e, from_attributes=True) for e in entities],
    )
