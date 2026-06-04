"""Top-level API router.

Sub-routers are registered here as each subsystem is built out across the
roadmap (TZ section 10). Keeping a single aggregator keeps ``main.py`` clean.
"""
from __future__ import annotations

from fastapi import APIRouter

api_router = APIRouter()


@api_router.get("/ping", tags=["health"], summary="Liveness probe")
async def ping() -> dict[str, str]:
    """Lightweight check that the API layer is reachable."""
    return {"status": "ok", "message": "pong"}


# Sub-routers (added incrementally as subsystems land):
#   from app.api import upload, ocr, parse, search, chat, export, task
#   api_router.include_router(upload.router)
#   ...
