"""Document listing / detail / file-serving endpoints.

Not in the original endpoint table (TZ 7) but required by the three-column UI
(TZ 4): the left panel lists files, the centre panel views them.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database.models import Document
from app.database.session import get_db
from app.schemas.document import DocumentDetail, DocumentOut
from app.services.storage import storage

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut], summary="Hujjatlar ro'yxati")
def list_documents(limit: int = 50, offset: int = 0,
                   db: Session = Depends(get_db)) -> list[DocumentOut]:
    docs = (
        db.query(Document)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(min(limit, 200))
        .all()
    )
    return [DocumentOut.model_validate(d) for d in docs]


def _get_or_404(db: Session, public_id: str) -> Document:
    doc = db.query(Document).filter(Document.public_id == public_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Hujjat topilmadi")
    return doc


@router.get("/{public_id}", response_model=DocumentDetail, summary="Hujjat tafsilotlari")
def get_document(public_id: str, db: Session = Depends(get_db)) -> DocumentDetail:
    return DocumentDetail.model_validate(_get_or_404(db, public_id))


@router.get("/{public_id}/file", summary="Hujjat faylini ko'rsatish")
def get_document_file(public_id: str, db: Session = Depends(get_db)) -> FileResponse:
    """Serve the raw stored file (used by the PDF/image viewer)."""
    doc = _get_or_404(db, public_id)
    path = storage.path(doc.stored_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fayl diskda topilmadi")
    return FileResponse(path, media_type=doc.mime_type or "application/octet-stream",
                        filename=doc.filename)


@router.delete("/{public_id}", summary="Hujjatni o'chirish")
def delete_document(public_id: str, db: Session = Depends(get_db)) -> dict:
    doc = _get_or_404(db, public_id)
    storage.delete(doc.stored_path)
    db.delete(doc)
    db.commit()
    return {"detail": "Hujjat o'chirildi"}
