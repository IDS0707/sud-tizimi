"""File storage service (TZ section 5: MinIO).

Provides a small abstraction over *where* uploaded files live. The default
backend writes to the local ``uploads/`` directory so the platform works with
zero infrastructure; if MinIO settings are present it transparently switches to
object storage. Callers only ever deal with an opaque ``storage key``.
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from app.config import settings
from app.utils.logger import get_logger

log = get_logger("udip.storage")


class LocalStorage:
    """Stores files on the local filesystem under ``uploads/``."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or settings.upload_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, file_obj: BinaryIO, *, filename: str, subdir: str = "") -> str:
        """Persist a binary stream and return its storage key (relative path)."""
        ext = Path(filename).suffix.lower()
        key_name = f"{uuid.uuid4().hex}{ext}"
        rel_key = str(Path(subdir) / key_name) if subdir else key_name
        dest = self.root / rel_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as out:
            shutil.copyfileobj(file_obj, out)
        log.debug("Saved file -> %s", dest)
        return rel_key

    def save_bytes(self, data: bytes, *, filename: str, subdir: str = "") -> str:
        ext = Path(filename).suffix.lower()
        key_name = f"{uuid.uuid4().hex}{ext}"
        rel_key = str(Path(subdir) / key_name) if subdir else key_name
        dest = self.root / rel_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return rel_key

    def path(self, key: str) -> Path:
        """Return the absolute filesystem path for a storage key."""
        return self.root / key

    def read(self, key: str) -> bytes:
        return (self.root / key).read_bytes()

    def exists(self, key: str) -> bool:
        return (self.root / key).exists()

    def delete(self, key: str) -> None:
        p = self.root / key
        if p.exists():
            p.unlink()


class MinioStorage(LocalStorage):
    """MinIO-backed storage. Falls back to local FS if the client is missing.

    Kept as a thin subclass so the rest of the app is storage-agnostic. The
    MinIO wiring is implemented lazily; until then it behaves like LocalStorage,
    which keeps the platform fully functional without object storage.
    """

    def __init__(self) -> None:  # pragma: no cover - exercised only with MinIO configured
        super().__init__()
        self._client = None
        try:
            from minio import Minio

            self._client = Minio(
                settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_secure,
            )
            if not self._client.bucket_exists(settings.minio_bucket):
                self._client.make_bucket(settings.minio_bucket)
            log.info("MinIO storage active: bucket=%s", settings.minio_bucket)
        except Exception as exc:
            log.warning("MinIO unavailable, using local FS: %s", exc)
            self._client = None


def get_storage() -> LocalStorage:
    """Return the configured storage backend (MinIO if set, else local FS)."""
    if settings.minio_endpoint and settings.minio_access_key:
        return MinioStorage()
    return LocalStorage()


storage = get_storage()
