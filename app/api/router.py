"""Top-level API router.

Sub-routers are registered here as each subsystem is built out across the
roadmap (TZ section 10). Keeping a single aggregator keeps ``main.py`` clean.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api import (
    ai,
    chat,
    documents,
    export,
    formula,
    ocr,
    parse,
    search,
    task,
    upload,
)

api_router = APIRouter()


@api_router.get("/ping", tags=["health"], summary="Liveness probe")
async def ping() -> dict[str, str]:
    """Lightweight check that the API layer is reachable."""
    return {"status": "ok", "message": "pong"}


# --- V1 subsystems: upload, OCR, tasks, document browsing ---
api_router.include_router(upload.router)
api_router.include_router(ocr.router)
api_router.include_router(task.router)
api_router.include_router(documents.router)

# --- V2 subsystem: document parsing (Office + text) ---
api_router.include_router(parse.router)

# --- V4 subsystems: smart search + formula OCR ---
api_router.include_router(search.router)
api_router.include_router(formula.router)

# --- V5 subsystems: AI analysis, chat (RAG), export ---
api_router.include_router(ai.router)
api_router.include_router(chat.router)
api_router.include_router(export.router)

# Added in later milestones: admin / API keys.
