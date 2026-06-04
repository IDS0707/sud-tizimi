"""Export endpoint (TZ section 2.12 / 7: POST /api/v1/export)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database.session import get_db
from app.schemas.ai import ExportRequest, ExportResponse
from app.services import export_service

router = APIRouter(prefix="/export", tags=["export"])


@router.post("", response_model=ExportResponse, summary="Natijani eksport qilish")
def export(req: ExportRequest, db: Session = Depends(get_db)) -> ExportResponse:
    """Export a document to TXT / JSON / Markdown / DOCX."""
    try:
        path = export_service.export_document(db, req.document_id, req.format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExportResponse(
        format=req.format.lower(),
        filename=path.name,
        download_url=f"{settings.api_prefix}/export/download/{path.name}",
    )


@router.get("/download/{filename}", summary="Eksport faylini yuklab olish")
def download(filename: str) -> FileResponse:
    """Serve a previously exported file from the outputs directory."""
    # Prevent path traversal.
    safe = Path(filename).name
    path = settings.output_dir / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail="Eksport fayli topilmadi")
    return FileResponse(path, filename=safe)
