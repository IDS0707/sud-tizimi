"""PP-Structure layout/table engine hook (TZ section 5: PP-StructureV3).

This is an *optional* high-quality backend for document structure analysis. If
PaddleOCR's ``PPStructure`` is installed it returns rich region/table data;
otherwise ``analyze`` returns ``None`` and callers fall back to the dependency-
free heuristic in ``app.services.layout_service``.
"""
from __future__ import annotations

from app.config import settings
from app.utils.logger import get_logger

log = get_logger("udip.ocr.structure")

_engine = None
_tried = False


def _get_engine():
    global _engine, _tried
    if _tried:
        return _engine
    _tried = True
    try:
        from paddleocr import PPStructure

        _engine = PPStructure(show_log=False, lang=settings.ocr_lang)
        log.info("PP-Structure engine initialised")
    except Exception as exc:  # pragma: no cover - optional dependency
        log.debug("PP-Structure unavailable: %s", exc)
        _engine = None
    return _engine


def is_available() -> bool:
    return _get_engine() is not None


def analyze(image_path: str) -> dict | None:
    """Return layout blocks + tables for an image, or None if unavailable.

    Output shape matches ``layout_service``:
        {"blocks": [...], "_tables": [[...rows...]], "source": "pp-structure"}
    """
    engine = _get_engine()
    if engine is None:
        return None
    try:  # pragma: no cover - exercised only when PP-Structure is installed
        regions = engine(image_path)
    except Exception as exc:  # pragma: no cover
        log.warning("PP-Structure analyze failed: %s", exc)
        return None

    blocks: list[dict] = []
    tables: list[list[list[str]]] = []
    for region in regions or []:  # pragma: no cover
        rtype = region.get("type", "text")
        bbox = region.get("bbox")
        res = region.get("res")
        if rtype == "table" and isinstance(res, dict) and res.get("html"):
            rows = _html_table_to_rows(res["html"])
            if rows:
                tables.append(rows)
                blocks.append({"type": "table", "rows": rows, "bbox": bbox})
        else:
            text = _region_text(res)
            if text:
                btype = "heading" if rtype in ("title", "header") else "text"
                blocks.append({"type": btype, "text": text, "bbox": bbox})
    return {"blocks": blocks, "_tables": tables, "source": "pp-structure"}


def _region_text(res) -> str:  # pragma: no cover
    if isinstance(res, list):
        return "\n".join(
            r.get("text", "") for r in res if isinstance(r, dict) and r.get("text")
        ).strip()
    if isinstance(res, dict):
        return str(res.get("text", "")).strip()
    return ""


def _html_table_to_rows(html: str) -> list[list[str]]:  # pragma: no cover
    """Very small HTML-table -> rows parser (no external deps)."""
    import re

    rows: list[list[str]] = []
    for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S | re.I):
        cells = re.findall(r"<t[dh].*?>(.*?)</t[dh]>", tr, re.S | re.I)
        rows.append([re.sub(r"<[^>]+>", "", c).strip() for c in cells])
    return [r for r in rows if any(r)]
