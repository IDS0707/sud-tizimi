"""Text indexing — the *write* side of search (TZ section 6, stage 7).

After a document is parsed/OCR-ed, each page's text is normalised and stored in
``search_index`` so it can be queried later. The *read* side (smart search) is
built on top of these rows in V4.
"""
from __future__ import annotations

import re

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.database.models import Page, SearchIndex
from app.utils.logger import get_logger

log = get_logger("udip.index")

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def normalize(text: str) -> str:
    """Lowercase and collapse whitespace for case-insensitive matching."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def token_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def index_page(db: Session, page: Page, *, source: str = "parser") -> SearchIndex | None:
    """Create (or skip) a search-index row for one page."""
    if not page.text or not page.text.strip():
        return None
    entry = SearchIndex(
        document_id=page.document_id,
        page_id=page.id,
        page_number=page.page_number,
        content=page.text,
        normalized=normalize(page.text),
        token_count=token_count(page.text),
        source=source,
    )
    db.add(entry)
    return entry


def reindex_document(db: Session, document_id: int) -> int:
    """Rebuild all index rows for a document from its current page text."""
    db.execute(delete(SearchIndex).where(SearchIndex.document_id == document_id))
    pages = db.query(Page).filter(Page.document_id == document_id).all()
    count = 0
    for page in pages:
        if index_page(db, page) is not None:
            count += 1
    db.commit()
    log.info("Indexed document %d: %d pages", document_id, count)
    return count
