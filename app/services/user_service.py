"""User management (TZ section 8: users).

Minimal for now — enough to anchor ownership and the SaaS model. A default
admin user is created on first boot so the ``users`` table is populated and API
keys can be associated with an account.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.models import User
from app.utils.logger import get_logger

log = get_logger("udip.users")

DEFAULT_ADMIN_EMAIL = "admin@udip.local"


def ensure_default_admin(db: Session) -> User:
    """Create the default admin user if no users exist yet."""
    existing = db.query(User).filter(User.email == DEFAULT_ADMIN_EMAIL).first()
    if existing:
        return existing
    admin = User(
        email=DEFAULT_ADMIN_EMAIL,
        username="admin",
        is_active=True,
        is_admin=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    log.info("Created default admin user (%s)", DEFAULT_ADMIN_EMAIL)
    return admin


def get_or_create_admin(db: Session) -> User:
    return ensure_default_admin(db)
