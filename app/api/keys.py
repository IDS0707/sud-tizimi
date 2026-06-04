"""API-key management (TZ section 6 / 8: api_keys).

Flow:
  * ``POST /keys``        — create a key; the raw value is returned **once**.
  * ``GET /keys``         — list keys (requires a valid key).
  * ``DELETE /keys/{id}`` — revoke a key (requires a valid key).

Creation is intentionally open so the very first key can be bootstrapped; in a
hardened deployment you would gate it behind an admin login.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.database.models import ApiKey
from app.database.session import get_db
from app.schemas.admin import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from app.services import security

router = APIRouter(prefix="/keys", tags=["api-keys"])


@router.post("", response_model=ApiKeyCreated, summary="API kalit yaratish")
def create_key(req: ApiKeyCreate, db: Session = Depends(get_db)) -> ApiKeyCreated:
    expires_at = None
    if req.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=req.expires_in_days)
    row, raw = security.create_api_key(db, name=req.name, expires_at=expires_at)
    return ApiKeyCreated(**ApiKeyOut.model_validate(row).model_dump(), api_key=raw)


@router.get("", response_model=list[ApiKeyOut], summary="API kalitlar ro'yxati")
def list_keys(db: Session = Depends(get_db), _=Depends(require_api_key)) -> list[ApiKeyOut]:
    keys = db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()
    return [ApiKeyOut.model_validate(k) for k in keys]


@router.delete("/{key_id}", summary="API kalitni bekor qilish")
def revoke_key(key_id: int, db: Session = Depends(get_db),
               _=Depends(require_api_key)) -> dict:
    if not security.revoke_api_key(db, key_id):
        raise HTTPException(status_code=404, detail="Kalit topilmadi")
    return {"detail": "Kalit bekor qilindi"}
