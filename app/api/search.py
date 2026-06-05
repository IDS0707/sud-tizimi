"""Search endpoint (TZ section 7: POST /api/v1/search)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem
from app.services import search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse, summary="Hujjatlar ichida qidirish")
def search_documents(req: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    """Find a keyword across all indexed documents and return ranked hits."""
    total, hits = search_service.search(
        db, req.query, limit=req.limit, offset=req.offset, document_id=req.document_id
    )
    results = [SearchResultItem(**search_service.hit_to_dict(db, h, req.query)) for h in hits]
    return SearchResponse(query=req.query, total=total, results=results)
