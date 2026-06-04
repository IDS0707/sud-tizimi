"""Chat-with-document endpoint (TZ section 2.11 / 7: POST /api/v1/chat)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai import analyzer
from app.database.models import Document
from app.database.session import get_db
from app.schemas.ai import ChatRequest, ChatResponse, ChatSource

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, summary="Hujjat bilan suhbatlashish")
def chat(req: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    """Answer a question about a document using RAG (retrieval + AI)."""
    if req.document_id is not None and db.get(Document, req.document_id) is None:
        raise HTTPException(status_code=404, detail="Hujjat topilmadi")

    result = analyzer.answer_question(db, req.document_id, req.question, top_k=req.top_k)
    return ChatResponse(
        question=req.question,
        answer=result.answer or "",
        model=result.model or "stub",
        sources=[ChatSource(**s) for s in (result.sources or [])],
    )
