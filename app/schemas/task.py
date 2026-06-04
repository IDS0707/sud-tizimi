"""Task schemas (TZ section 7: GET /api/v1/task/{id})."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskOut(BaseModel):
    """Background task status as returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    status: str
    progress: int
    document_id: int | None = None
    result: dict | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
