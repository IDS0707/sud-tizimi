"""Entity extraction (TZ section 2.10; ``entities`` table).

Pulls structured facts out of free text — dates, money amounts, percentages,
emails, phone numbers — using language-agnostic regular expressions. Results
are stored in the ``entities`` table so the UI/AI can surface "important data"
(sana, summa, ism, …) as the spec requires.

This is deliberately dependency-free; a richer NER model can be layered on top
later without changing the storage contract.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.database.models import Document, Entity, Page
from app.utils.logger import get_logger

log = get_logger("udip.entities")


@dataclass
class Found:
    entity_type: str
    value: str
    start: int
    end: int


# --- patterns ------------------------------------------------------- #
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    # +998 90 123 45 67 / 90-123-45-67 / (90) 123 4567
    ("phone", re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)\d{3}[\s\-]?\d{2}[\s\-]?\d{2}(?!\d)")),
    # 12.05.2024 / 2024-05-12 / 12/05/2024
    ("date", re.compile(r"\b(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}[./-]\d{1,2}[./-]\d{1,2})\b")),
    # 1 500 000 so'm / $1,200.50 / 500000 UZS
    ("money", re.compile(r"(?:[$€₽]\s?\d[\d\s.,]*|\b\d[\d\s.,]*\s?(?:so['’]m|sum|UZS|USD|EUR|RUB|\$|€))",
                         re.IGNORECASE)),
    ("percent", re.compile(r"\b\d{1,3}(?:[.,]\d+)?\s?%")),
]

_CONTEXT = 40


def extract_from_text(text: str) -> list[Found]:
    """Find all entities in a piece of text (de-duplicated by value+type)."""
    found: list[Found] = []
    seen: set[tuple[str, str]] = set()
    for etype, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            value = m.group(0).strip()
            key = (etype, value.lower())
            if not value or key in seen:
                continue
            seen.add(key)
            found.append(Found(etype, value, m.start(), m.end()))
    return found


def extract_for_document(db: Session, document_id: int) -> int:
    """Extract entities for every page of a document and store them."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise ValueError(f"Document {document_id} not found")

    db.execute(delete(Entity).where(Entity.document_id == document_id))
    pages = db.query(Page).filter(Page.document_id == document_id).all()

    count = 0
    for page in pages:
        text = page.text or ""
        for f in extract_from_text(text):
            ctx_start = max(0, f.start - _CONTEXT)
            ctx_end = min(len(text), f.end + _CONTEXT)
            db.add(Entity(
                document_id=document_id,
                page_id=page.id,
                entity_type=f.entity_type,
                value=f.value[:1024],
                normalized_value=_normalize(f.entity_type, f.value),
                context=text[ctx_start:ctx_end].strip(),
                confidence=0.7,
            ))
            count += 1
    db.commit()
    log.info("Extracted %d entities from document %d", count, document_id)
    return count


def _normalize(etype: str, value: str) -> str | None:
    if etype == "phone":
        return re.sub(r"[^\d+]", "", value)
    if etype == "money":
        return re.sub(r"\s+", " ", value)
    return None
