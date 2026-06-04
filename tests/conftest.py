"""Shared pytest configuration.

``app.config.Settings`` is cached (lru_cache) and the DB engine is created at
import time, so the database URL must be fixed *before any app module loads* —
i.e. here, in conftest, which pytest imports first. A single test database is
used and its schema is recreated fresh for each test module, giving every
module a clean slate while still allowing intra-module data accumulation
(which the per-file tests rely on).
"""
from __future__ import annotations

import os
import tempfile

# Must run before the app's settings are cached.
_TEST_DB = os.path.join(tempfile.gettempdir(), "udip_pytest.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"

import pytest  # noqa: E402

from app.database.session import Base, engine, init_db  # noqa: E402

init_db()


@pytest.fixture(autouse=True, scope="module")
def _fresh_schema_per_module():
    """Drop & recreate all tables at the start of each test module."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
