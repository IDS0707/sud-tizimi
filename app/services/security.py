"""API-key security primitives (TZ section 6: SaaS / api_keys).

Keys are shown to the user exactly once at creation; only a salted SHA-256
hash is stored. Lookups are by ``key_prefix`` (indexed) then constant-time hash
comparison, so the raw key never needs to live in the database.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import ApiKey
from app.utils.logger import get_logger

log = get_logger("udip.security")

_KEY_BYTES = 24          # -> 48 hex chars of entropy
_PREFIX = "udip"


@dataclass
class GeneratedKey:
    raw: str             # full key, shown to the user once
    prefix: str          # stored + used for fast lookup
    hashed: str          # stored


def _hash(raw: str) -> str:
    """Salted SHA-256 of the raw key (salt = app secret)."""
    return hmac.new(
        settings.secret_key.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def generate_key() -> GeneratedKey:
    body = secrets.token_hex(_KEY_BYTES)
    raw = f"{_PREFIX}_{body}"
    prefix = raw[: len(_PREFIX) + 1 + 8]   # e.g. "udip_1a2b3c4d"
    return GeneratedKey(raw=raw, prefix=prefix, hashed=_hash(raw))


def create_api_key(db: Session, *, name: str, user_id: int | None = None,
                   expires_at: datetime | None = None) -> tuple[ApiKey, str]:
    """Create and store an API key; return (row, raw_key_shown_once)."""
    gen = generate_key()
    row = ApiKey(
        user_id=user_id,
        name=name,
        key_prefix=gen.prefix,
        hashed_key=gen.hashed,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log.info("Created API key '%s' (prefix=%s)", name, gen.prefix)
    return row, gen.raw


def verify_api_key(db: Session, raw: str) -> ApiKey | None:
    """Return the matching active key (and touch ``last_used_at``), else None."""
    if not raw or "_" not in raw:
        return None
    prefix = raw[: len(_PREFIX) + 1 + 8]
    candidates = db.query(ApiKey).filter(
        ApiKey.key_prefix == prefix, ApiKey.is_active.is_(True)
    ).all()
    target = _hash(raw)
    now = datetime.now(timezone.utc)
    for key in candidates:
        if hmac.compare_digest(key.hashed_key, target):
            if key.expires_at and key.expires_at < now.replace(tzinfo=None):
                return None
            key.last_used_at = now
            db.commit()
            return key
    return None


def revoke_api_key(db: Session, key_id: int) -> bool:
    key = db.get(ApiKey, key_id)
    if key is None:
        return False
    key.is_active = False
    db.commit()
    log.info("Revoked API key id=%d", key_id)
    return True
