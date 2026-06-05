"""Runtime-editable OCR configuration.

Lets the OCR provider / Gemini key / model be changed from the admin panel at
runtime (persisted to a small JSON file) without editing ``.env`` or restarting.
Falls back to the values in ``app.config.settings`` (i.e. ``.env``) as defaults.
"""
from __future__ import annotations

import json
import threading

from app.config import BASE_DIR, settings
from app.utils.logger import get_logger

log = get_logger("udip.runtime_config")

_PATH = BASE_DIR / "runtime_config.json"
_KEYS = ("ocr_provider", "gemini_api_key", "gemini_model")
_lock = threading.Lock()


def _defaults() -> dict:
    return {
        "ocr_provider": settings.ocr_provider,
        "gemini_api_key": settings.gemini_api_key or "",
        "gemini_model": settings.gemini_model,
    }


def get_config() -> dict:
    """Return the effective OCR config (file overrides .env defaults)."""
    cfg = _defaults()
    if _PATH.exists():
        try:
            cfg.update({k: v for k, v in json.loads(
                _PATH.read_text(encoding="utf-8")).items() if k in _KEYS})
        except Exception as exc:  # pragma: no cover
            log.warning("runtime_config read failed: %s", exc)
    return cfg


def update_config(patch: dict) -> dict:
    """Persist a partial update and return the new effective config."""
    with _lock:
        cfg = get_config()
        for k in _KEYS:
            if k in patch and patch[k] is not None:
                cfg[k] = patch[k]
        _PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("OCR config updated: provider=%s model=%s key=%s",
             cfg["ocr_provider"], cfg["gemini_model"], "set" if cfg["gemini_api_key"] else "none")
    return cfg


def signature() -> tuple:
    """A hashable snapshot used to detect config changes (cache invalidation)."""
    cfg = get_config()
    return (cfg["ocr_provider"], cfg["gemini_model"], bool(cfg["gemini_api_key"]),
            cfg["gemini_api_key"][-6:] if cfg["gemini_api_key"] else "")
