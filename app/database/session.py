"""Database engine, session factory and declarative base.

The platform targets PostgreSQL in production (TZ section 5) but defaults to a
zero-config SQLite file so it runs out of the box. Both are supported through
SQLAlchemy with no code changes — only ``DATABASE_URL`` differs.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings
from app.utils.logger import get_logger

log = get_logger("udip.database")

# SQLite needs a special flag to be usable across threads (FastAPI workers).
_connect_args = {}
if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""


def init_db() -> None:
    """Create all tables that do not yet exist.

    Models are imported here (not at module top) to avoid circular imports and
    to guarantee they are registered on ``Base.metadata`` before ``create_all``.
    """
    from app.database import models  # noqa: F401  (registers mappers)

    Base.metadata.create_all(bind=engine)
    log.info("Ensured %d tables exist", len(Base.metadata.tables))


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a scoped session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
