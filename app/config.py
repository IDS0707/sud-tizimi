"""Central application configuration.

All settings are read from environment variables (optionally via a ``.env``
file). Sensible zero-config defaults are chosen so the platform runs locally
without PostgreSQL/Redis/MinIO installed — those are swapped in via env vars
in production, exactly as described in the TZ (section 5: Technologies).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = directory that contains this ``app`` package's parent.
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- General ---
    app_name: str = "Universal Document Intelligence Platform"
    app_env: str = Field(default="development")  # development | production
    debug: bool = True
    api_prefix: str = "/api/v1"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- Database ---
    # Default: zero-config SQLite file in the project root.
    # Production (per TZ): postgresql+psycopg2://user:pass@host:5432/udip
    database_url: str = Field(default=f"sqlite:///{(BASE_DIR / 'udip.db').as_posix()}")

    # --- Cache (Redis) — optional, falls back to in-memory ---
    redis_url: str | None = Field(default=None)  # e.g. redis://localhost:6379/0

    # --- Object storage (MinIO) — optional, falls back to local FS ---
    minio_endpoint: str | None = None
    minio_access_key: str | None = None
    minio_secret_key: str | None = None
    minio_bucket: str = "udip-files"
    minio_secure: bool = False

    # --- Filesystem paths (used by the local-FS storage fallback) ---
    upload_dir: Path = BASE_DIR / "uploads"
    output_dir: Path = BASE_DIR / "outputs"
    log_dir: Path = BASE_DIR / "logs"

    # --- Upload limits ---
    max_upload_mb: int = 100
    allowed_extensions: set[str] = {
        # images
        "jpg", "jpeg", "png", "webp",
        # documents
        "pdf", "docx", "xlsx", "pptx", "txt", "rtf",
    }

    # --- OCR ---
    # Language(s) for OCR. For Tesseract you can combine with "+",
    # e.g. "uzb+rus+eng". For PaddleOCR use a single code like "en"/"ru".
    ocr_lang: str = "uzb+rus+eng"
    ocr_use_gpu: bool = False
    ocr_min_confidence: float = 0.3
    # Optional explicit paths (auto-detected if left None). A project-local
    # ``.tessdata`` directory (extra language packs) is picked up automatically.
    tesseract_cmd: str | None = None
    tessdata_dir: str | None = (
        str(BASE_DIR / ".tessdata") if (BASE_DIR / ".tessdata").exists() else None
    )

    # --- AI / RAG ---
    ai_provider: str = "stub"     # stub | anthropic | openai
    ai_api_key: str | None = None
    ai_model: str = "claude-sonnet-4-6"
    rag_top_k: int = 5

    # --- Security ---
    secret_key: str = "change-me-in-production"  # noqa: S105 (dev default)
    api_key_header: str = "X-API-Key"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def ensure_dirs(self) -> None:
        """Create runtime directories if they do not yet exist."""
        for d in (self.upload_dir, self.output_dir, self.log_dir):
            Path(d).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton ``Settings`` instance."""
    return Settings()


settings = get_settings()
