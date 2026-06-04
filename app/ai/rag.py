"""Retrieval-Augmented Generation (TZ section 10 note: RAG).

Before answering, relevant passages are *retrieved* from the document's search
index and handed to the AI provider as grounding context. This keeps answers
tied to the document (TZ 2.11) and prevents the model from inventing facts.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.provider import get_provider
from app.config import settings
from app.services import search_service
from app.utils.logger import get_logger

log = get_logger("udip.ai.rag")


@dataclass
class Source:
    page_number: int | None
    text: str


def retrieve(db: Session, question: str, *, document_id: int | None = None,
             top_k: int | None = None) -> list[Source]:
    """Retrieve the most relevant index chunks for a question."""
    top_k = top_k or settings.rag_top_k
    _, hits = search_service.search(db, question, limit=top_k, document_id=document_id)
    return [Source(page_number=h.entry.page_number, text=h.entry.content) for h in hits]


def answer(db: Session, question: str, *, document_id: int | None = None,
           top_k: int | None = None) -> dict:
    """Answer a question using retrieved context (RAG)."""
    sources = retrieve(db, question, document_id=document_id, top_k=top_k)
    provider = get_provider()
    contexts = [s.text for s in sources]
    text = provider.answer(question, contexts)
    return {
        "answer": text,
        "model": provider.name,
        "sources": [
            {"page_number": s.page_number, "snippet": s.text[:240]} for s in sources
        ],
    }
