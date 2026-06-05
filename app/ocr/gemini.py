"""Gemini (Google AI Studio) OCR backend.

Sends the image to a Gemini multimodal model and asks for **every word** with
its bounding box and a confidence score, returned as structured JSON. The
output is normalised into the exact same shape as the local OCR backends:

    {"text", "boxes": [{"text", "bbox":[x1,y1,x2,y2] (0..1), "confidence"}], "confidence"}

so the rest of the platform (word-level UI, search, crop) works unchanged.

Gemini returns boxes as ``[ymin, xmin, ymax, xmax]`` normalised to 0–1000; we
convert them to ``[x1, y1, x2, y2]`` in the 0..1 range used everywhere else.
"""
from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

from app.utils.logger import get_logger

log = get_logger("udip.ocr.gemini")

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

_PROMPT = (
    "You are a precise OCR engine for legal/court documents. "
    "Read EVERY piece of text in the image, including handwriting, in natural "
    "reading order (top-to-bottom, left-to-right). For each word return its exact "
    "characters (preserve Uzbek-Latin, Russian/Cyrillic, English and punctuation; "
    "do NOT translate or correct spelling), its bounding box and your confidence. "
    "Do not skip any word."
)

# Structured-output schema (OpenAPI subset Gemini accepts).
_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "text": {"type": "STRING"},
            "box_2d": {"type": "ARRAY", "items": {"type": "INTEGER"}},  # [ymin,xmin,ymax,xmax] 0-1000
            "confidence": {"type": "NUMBER"},
        },
        "required": ["text", "box_2d", "confidence"],
    },
}


def is_configured(cfg: dict) -> bool:
    return cfg.get("ocr_provider") == "gemini" and bool(cfg.get("gemini_api_key"))


def validate(api_key: str, model: str) -> tuple[bool, str]:
    """Lightweight check that the key + model work. Returns (ok, message)."""
    if not api_key:
        return False, "API kalit kiritilmagan"
    try:
        import httpx

        url = _ENDPOINT.format(model=model)
        payload = {"contents": [{"role": "user", "parts": [{"text": "ping"}]}]}
        with httpx.Client(timeout=30) as client:
            r = client.post(url, params={"key": api_key}, json=payload)
        if r.status_code == 200:
            return True, "Kalit va model ishlayapti ✓"
        detail = ""
        try:
            detail = r.json().get("error", {}).get("message", "")
        except Exception:
            detail = r.text[:200]
        return False, f"Xato ({r.status_code}): {detail}"
    except Exception as exc:  # pragma: no cover
        return False, f"Ulanib bo'lmadi: {exc}"


def _mime_for(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "image/jpeg"


def recognize(image_path: str, *, api_key: str, model: str, lang: str | None = None) -> dict:
    """Run Gemini OCR on one image. Returns the normalised OCR dict.

    Raises on transport/API errors so the caller can surface them.
    """
    import httpx

    data = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": _PROMPT},
                {"inlineData": {"mimeType": _mime_for(image_path), "data": data}},
            ],
        }],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": _SCHEMA,
        },
    }
    url = _ENDPOINT.format(model=model)
    with httpx.Client(timeout=120) as client:
        resp = client.post(url, params={"key": api_key}, json=payload)
        resp.raise_for_status()
        body = resp.json()

    raw = (
        body.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )
    try:
        items = json.loads(raw)
    except Exception:
        log.warning("Gemini returned non-JSON; treating as plain text")
        items = []

    boxes: list[dict] = []
    texts: list[str] = []
    confs: list[float] = []
    for it in items if isinstance(items, list) else []:
        text = str(it.get("text", "")).strip()
        if not text:
            continue
        b = it.get("box_2d") or [0, 0, 0, 0]
        if len(b) != 4:
            b = [0, 0, 0, 0]
        ymin, xmin, ymax, xmax = (max(0.0, min(1000.0, float(v))) / 1000.0 for v in b)
        conf = float(it.get("confidence", 0.0))
        conf = max(0.0, min(1.0, conf))
        boxes.append({
            "text": text,
            "bbox": [round(xmin, 4), round(ymin, 4), round(xmax, 4), round(ymax, 4)],
            "confidence": round(conf, 4),
        })
        texts.append(text)
        confs.append(conf)

    # If the model didn't give boxes (rare), fall back to a plain-text read.
    if not texts and isinstance(raw, str) and raw.strip():
        texts = [raw.strip()]

    log.info("Gemini OCR: %d words (model=%s)", len(boxes), model)
    return {
        "text": " ".join(texts),
        "boxes": boxes,
        "confidence": (sum(confs) / len(confs)) if confs else 0.0,
        "engine": "gemini",
        "lang": lang,
    }
