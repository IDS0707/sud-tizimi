"""Formula OCR endpoint (TZ section 2.8)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.ocr import formula
from app.services import file_detector

router = APIRouter(prefix="/formula", tags=["formula"])


@router.post("/image", summary="Rasmdagi formulani aniqlash (LaTeX)")
async def recognize_formula(file: UploadFile = File(...)) -> dict:
    """Recognise a mathematical formula from an uploaded image → LaTeX."""
    if not file.filename or file_detector.detect(file.filename).category != "image":
        raise HTTPException(status_code=415, detail="Faqat rasm fayllari qabul qilinadi")

    suffix = Path(file.filename).suffix or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        result = formula.recognize_formula(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return result.to_dict()


@router.get("/status", summary="Formula OCR mexanizmi holati")
def formula_status() -> dict:
    return {"available": formula.is_available()}
