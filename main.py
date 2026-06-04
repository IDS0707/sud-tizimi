"""UDIP application entry point (TZ section 9: ``main.py``).

Run locally with:

    uvicorn main:app --reload

or simply:

    python main.py
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.router import api_router
from app.config import BASE_DIR, settings
from app.utils.logger import get_logger

WEB_DIR = BASE_DIR / "web"

log = get_logger("udip.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    log.info("Starting %s v%s (env=%s)", settings.app_name, __version__, settings.app_env)
    settings.ensure_dirs()
    # Database tables are created lazily here once the DB layer lands.
    try:
        from app.database.session import SessionLocal, init_db
        from app.services.user_service import ensure_default_admin

        init_db()
        with SessionLocal() as db:
            ensure_default_admin(db)
        log.info("Database initialised: %s", settings.database_url.split("@")[-1])
    except Exception as exc:  # pragma: no cover - DB layer optional at this stage
        log.warning("Database not initialised yet: %s", exc)
    yield
    log.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "Universal Document Intelligence Platform — OCR, search, AI analysis "
        "and document parsing. See the technical specification for details."
    ),
    lifespan=lifespan,
)

# CORS — open during development so the bundled frontend can call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the versioned API (e.g. /api/v1/...).
app.include_router(api_router, prefix=settings.api_prefix)

# Serve the web interface (TZ section 4: three-column UI).
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    """Serve the single-page web application."""
    index = WEB_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse({"app": settings.app_name, "version": __version__, "docs": "/docs"})


@app.get("/admin", include_in_schema=False)
async def admin_panel() -> FileResponse:
    """Serve the admin / management panel (TZ section 6)."""
    page = WEB_DIR / "admin.html"
    if page.exists():
        return FileResponse(page)
    return JSONResponse({"detail": "admin panel not found"}, status_code=404)


@app.get("/api", tags=["health"], summary="Service banner")
async def api_banner() -> dict[str, object]:
    """Machine-friendly banner with quick links."""
    return {
        "app": settings.app_name,
        "version": __version__,
        "status": "running",
        "docs": "/docs",
        "api_prefix": settings.api_prefix,
    }


@app.get("/health", tags=["health"], summary="Health check")
async def health() -> JSONResponse:
    """Readiness probe used by orchestrators / load balancers."""
    return JSONResponse({"status": "healthy", "version": __version__})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
