"""OCR endpoints (TZ section 7: POST /api/v1/ocr).

Two ways to use it:
  * ``POST /api/v1/ocr``        — OCR an already-uploaded document by id.
  * ``POST /api/v1/ocr/image``  — quick OCR of a directly-uploaded image
                                  (no persistence), for the "rasmdan matn olish"
                                  use case.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database.models import Document, OcrResult
from app.database.session import get_db
from app.ocr.engine import ocr_engine
from app.schemas.ocr import OcrRequest, OcrResultOut
from app.services import document_service, file_detector
from app.services.storage import storage
from app.utils.logger import get_logger

router = APIRouter(prefix="/ocr", tags=["ocr"])
log = get_logger("udip.api.ocr")


@router.post("", response_model=list[OcrResultOut], summary="Hujjatni OCR qilish")
def ocr_document(req: OcrRequest, db: Session = Depends(get_db)) -> list[OcrResultOut]:
    """Run OCR over every scanned page of an uploaded document."""
    doc = db.get(Document, req.document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Hujjat topilmadi")

    # (Re)process to ensure pages + OCR results exist.
    document_service.process_document(db, doc.id, run_ocr=True, lang=req.lang)

    results = (
        db.query(OcrResult)
        .filter(OcrResult.document_id == doc.id)
        .order_by(OcrResult.page_id)
        .all()
    )
    out: list[OcrResultOut] = []
    for r in results:
        out.append(OcrResultOut(
            text=r.text or "",
            boxes=r.boxes or [],
            confidence=r.confidence or 0.0,
            engine=r.engine,
            lang=r.lang,
        ))
    return out


@router.post("/image", response_model=OcrResultOut, summary="Rasmdan tezkor matn olish")
async def ocr_image(
    file: UploadFile = File(...),
    lang: str | None = None,
) -> OcrResultOut:
    """OCR a directly-uploaded image without storing it."""
    if not file.filename or not file_detector.detect(file.filename).category == "image":
        raise HTTPException(status_code=415, detail="Faqat rasm fayllari qabul qilinadi")

    suffix = Path(file.filename).suffix or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        out = ocr_engine.recognize(tmp_path, lang=lang)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return OcrResultOut(
        text=out.text,
        boxes=out.boxes,
        confidence=out.confidence,
        engine=out.engine,
        lang=out.lang,
        page_number=1,
    )


@router.get("/engine", summary="OCR mexanizmi holati")
def ocr_engine_status() -> dict:
    """Report which OCR backend is active (real engine vs stub)."""
    return {"real_engine": ocr_engine.is_real}
