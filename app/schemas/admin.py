"""API-key & admin schemas (TZ section 6: SaaS, boshqaruv paneli)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---- API keys ------------------------------------------------------ #
class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime | None = None


class ApiKeyCreated(ApiKeyOut):
    """Returned only at creation — includes the raw key, shown once."""

    api_key: str


# ---- OCR provider config ------------------------------------------- #
class OcrConfig(BaseModel):
    ocr_provider: str            # tesseract | gemini
    gemini_model: str
    has_key: bool                # whether a Gemini key is saved (key itself hidden)
    active_engine: str           # currently active backend


class OcrConfigUpdate(BaseModel):
    ocr_provider: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str | None = None


# ---- admin stats --------------------------------------------------- #
class AdminStats(BaseModel):
    documents: int
    pages: int
    ocr_results: int
    entities: int
    ai_results: int
    tasks: int
    api_keys: int
    users: int
    documents_by_type: dict[str, int]
    documents_by_status: dict[str, int]
    total_storage_bytes: int
