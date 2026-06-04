"""Upload endpoint (TZ section 7: POST /api/v1/upload).

Accepts a multipart file, validates it, stores it and registers a Document.
Processing (parse + OCR + index) runs either synchronously or, for large jobs,
in the background with a task id the client can poll.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database.session import SessionLocal, get_db
from app.schemas.document import DocumentOut, UploadResponse
from app.services import document_service, file_detector, task_service
from app.utils.logger import get_logger

router = APIRouter(prefix="/upload", tags=["upload"])
log = get_logger("udip.api.upload")


def _run_processing(document_id: int, task_id: str) -> None:
    """Background worker: parse + OCR + index a document, updating its task."""
    db = SessionLocal()
    try:
        task_service.start_task(db, task_id)
        document_service.process_document(db, document_id)
        task_service.complete_task(db, task_id, {"document_id": document_id})
    except Exception as exc:  # pragma: no cover - background safety net
        task_service.fail_task(db, task_id, str(exc))
        log.exception("Background processing failed for document %d", document_id)
    finally:
        db.close()


@router.post("", response_model=UploadResponse, summary="Fayl yuklash")
async def upload_file(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    process: bool = True,
    async_mode: bool = False,
    db: Session = Depends(get_db),
) -> UploadResponse:
    """Upload a document or image.

    - ``process=true`` runs parse/OCR/index after storing.
    - ``async_mode=true`` does that processing in the background and returns a
      ``task_id`` to poll via ``GET /api/v1/task/{id}``.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Fayl nomi yo'q")
    if not file_detector.is_allowed(file.filename):
        raise HTTPException(
            status_code=415,
            detail=f"Qo'llab-quvvatlanmaydigan format. Ruxsat etilgan: "
                   f"{', '.join(sorted(settings.allowed_extensions))}",
        )

    # Peek at the head for magic-byte detection, then rewind.
    head = await file.read(16)
    await file.seek(0)

    # Determine size (Starlette exposes .size for spooled uploads).
    size = file.size or 0
    if size and size > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Fayl hajmi {settings.max_upload_mb}MB dan oshmasligi kerak",
        )

    doc = document_service.store_upload(
        db,
        file_obj=file.file,
        filename=file.filename,
        size_bytes=size,
        head=head,
    )

    task_id: str | None = None
    if process:
        if async_mode:
            task = task_service.create_task(db, task_type="parse", document_id=doc.id)
            task_id = task.id
            background.add_task(_run_processing, doc.id, task.id)
        else:
            document_service.process_document(db, doc.id)
            db.refresh(doc)

    return UploadResponse(document=DocumentOut.model_validate(doc), task_id=task_id)
