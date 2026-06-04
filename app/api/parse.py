"""Parse endpoint (TZ section 7: POST /api/v1/parse).

Parses an uploaded document according to its type (PDF, DOCX, XLSX, PPTX, TXT,
RTF, image) and returns the structured result: per-page text, metadata and any
tables found. Re-callable to re-process a document.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.models import Document
from app.database.session import get_db
from app.schemas.document import DocumentDetail
from app.schemas.parse import ParseRequest, ParseResponse, TableOut
from app.services import document_service

router = APIRouter(prefix="/parse", tags=["parse"])


def _tables_from_pages(doc: Document) -> list[TableOut]:
    """Collect tables stored inside each page's layout blocks."""
    out: list[TableOut] = []
    for page in doc.pages:
        layout = page.layout or {}
        for block in layout.get("blocks", []):
            if block.get("type") == "table" and block.get("rows"):
                out.append(TableOut(page_number=page.page_number, rows=block["rows"]))
    return out


@router.post("", response_model=ParseResponse, summary="Hujjatni tahlil qilish")
def parse_document(req: ParseRequest, db: Session = Depends(get_db)) -> ParseResponse:
    doc = db.get(Document, req.document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Hujjat topilmadi")

    doc = document_service.process_document(
        db, doc.id, run_ocr=req.run_ocr, lang=req.lang
    )
    return ParseResponse(
        document=DocumentDetail.model_validate(doc),
        parser=(doc.doc_metadata or {}).get("parser", doc.file_type),
        tables=_tables_from_pages(doc),
    )
