"""Smart search — the *read* side of search (TZ section 2.9 & 3).

Finds a keyword across every indexed document (PDF, Word, images, OCR text),
ranks the hits, and returns each with a highlighted context snippet and a page
reference so the UI can jump to the exact spot (TZ section 3.1, step 5).

Implementation notes
--------------------
Matching runs against the ``search_index`` table populated during processing.
A portable LIKE pre-filter narrows candidates, then scoring/snippeting happens
in Python — no DB-specific full-text extension required (works on SQLite and
PostgreSQL alike). For very large corpora this is the natural place to swap in
PostgreSQL ``tsvector`` / SQLite FTS5 without changing the API.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database.models import Document, SearchIndex
from app.services.index_service import normalize
from app.utils.logger import get_logger

log = get_logger("udip.search")

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _tokens(query: str) -> list[str]:
    return [t for t in _WORD_RE.findall(query.lower()) if t]


@dataclass
class Hit:
    entry: SearchIndex
    score: float
    snippet: str
    context: str


def _score(normalized_content: str, phrase: str, tokens: list[str]) -> float:
    """Score a candidate: phrase matches weigh more than scattered tokens."""
    score = 0.0
    if phrase and phrase in normalized_content:
        score += 10.0 * normalized_content.count(phrase)
    for t in tokens:
        score += normalized_content.count(t)
    # Light normalisation by length so long pages don't always win.
    return score / (1 + len(normalized_content) / 5000.0)


def _make_snippet(content: str, tokens: list[str], phrase: str, width: int = 180) -> tuple[str, str]:
    """Return (html_snippet_with_marks, plain_context)."""
    low = content.lower()
    pos = low.find(phrase) if phrase and phrase in low else -1
    if pos == -1:
        positions = [low.find(t) for t in tokens if low.find(t) != -1]
        pos = min(positions) if positions else 0

    start = max(0, pos - width // 3)
    end = min(len(content), start + width)
    context = content[start:end].strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(content) else ""
    plain = f"{prefix}{context}{suffix}"

    # Escape, then wrap each token occurrence in <mark>.
    escaped = html.escape(plain)
    seen = set()
    for t in sorted(tokens, key=len, reverse=True):
        if t in seen:
            continue
        seen.add(t)
        escaped = re.sub(
            f"({re.escape(html.escape(t))})",
            r"<mark>\1</mark>",
            escaped,
            flags=re.IGNORECASE,
        )
    return escaped, plain


def search(db: Session, query: str, *, limit: int = 30, offset: int = 0,
           document_id: int | None = None) -> tuple[int, list[Hit]]:
    """Run a keyword search; return (total_hits, page_of_hits)."""
    tokens = _tokens(query)
    if not tokens:
        return 0, []
    phrase = normalize(query)

    # Portable LIKE pre-filter: rows containing ANY token.
    conditions = [SearchIndex.normalized.like(f"%{t}%") for t in tokens]
    stmt = select(SearchIndex).where(or_(*conditions))
    if document_id is not None:
        stmt = stmt.where(SearchIndex.document_id == document_id)

    candidates = db.execute(stmt).scalars().all()

    hits: list[Hit] = []
    for entry in candidates:
        s = _score(entry.normalized, phrase, tokens)
        if s <= 0:
            continue
        snippet, context = _make_snippet(entry.content, tokens, phrase)
        hits.append(Hit(entry=entry, score=s, snippet=snippet, context=context))

    hits.sort(key=lambda h: h.score, reverse=True)
    total = len(hits)
    log.info("Search %r -> %d hits", query, total)
    return total, hits[offset:offset + limit]


def hit_to_dict(db: Session, hit: Hit) -> dict:
    """Enrich a hit with its parent document's display fields."""
    doc = db.get(Document, hit.entry.document_id)
    return {
        "document_id": hit.entry.document_id,
        "public_id": doc.public_id if doc else "",
        "filename": doc.filename if doc else "—",
        "file_type": doc.file_type if doc else "",
        "page_number": hit.entry.page_number,
        "score": round(hit.score, 3),
        "snippet": hit.snippet,
        "context": hit.context,
    }
