"""Document AI analysis (TZ section 2.10).

Orchestrates the document-level AI features:
  * **summarise** the whole document,
  * **extract entities** (dates, money, …),
  * **answer** questions via RAG,
storing each outcome in ``ai_results`` so it can be shown/reused.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai import rag
from app.ai.provider import get_provider
from app.database.models import AiResult, Document, Entity
from app.services import entity_service
from app.utils.logger import get_logger

log = get_logger("udip.ai.analyzer")


def _document_text(doc: Document) -> str:
    return "\n".join(p.text for p in doc.pages if p.text)


def summarize_document(db: Session, document_id: int, *, max_sentences: int = 5) -> AiResult:
    """Produce and persist a document summary."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise ValueError(f"Document {document_id} not found")

    text = _document_text(doc)
    provider = get_provider()
    summary = provider.summarize(text, max_sentences=max_sentences) if text else ""

    result = AiResult(
        document_id=document_id,
        kind="summary",
        answer=summary,
        model=provider.name,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    log.info("Summarised document %d (%d chars -> %d chars)", document_id, len(text), len(summary))
    return result


def extract_entities(db: Session, document_id: int) -> list[Entity]:
    """Extract and persist entities; return the stored rows."""
    entity_service.extract_for_document(db, document_id)
    return db.query(Entity).filter(Entity.document_id == document_id).all()


def answer_question(db: Session, document_id: int | None, question: str,
                    *, top_k: int | None = None) -> AiResult:
    """Answer a question about a document (RAG) and persist it."""
    out = rag.answer(db, question, document_id=document_id, top_k=top_k)
    result = AiResult(
        document_id=document_id or 0,
        kind="qa",
        question=question,
        answer=out["answer"],
        model=out["model"],
        sources=out["sources"],
    )
    if document_id:
        db.add(result)
        db.commit()
        db.refresh(result)
    return result
