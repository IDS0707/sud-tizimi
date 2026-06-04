"""Shared API dependencies — API-key authentication (TZ section 6: SaaS).

Protected routes depend on ``require_api_key``: the caller must send a valid key
in the ``X-API-Key`` header. ``optional_api_key`` returns the key if present but
never blocks, for routes that adapt to authenticated vs anonymous callers.
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database.models import ApiKey
from app.database.session import get_db
from app.services import security


def optional_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> ApiKey | None:
    if not x_api_key:
        return None
    return security.verify_api_key(db, x_api_key)


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> ApiKey:
    key = security.verify_api_key(db, x_api_key) if x_api_key else None
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yaroqli API kalit kerak (X-API-Key sarlavhasi)",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return key
