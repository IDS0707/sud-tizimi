"""File type detection (TZ section 6, stage 3: File Detector).

Determines a file's logical type and category from its name and, where useful,
its magic bytes. This drives which parser / OCR path a document takes.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.database.models import FileCategory

# Extension -> (category, mime type)
_EXT_MAP: dict[str, tuple[str, str]] = {
    # images
    "jpg": (FileCategory.IMAGE, "image/jpeg"),
    "jpeg": (FileCategory.IMAGE, "image/jpeg"),
    "png": (FileCategory.IMAGE, "image/png"),
    "webp": (FileCategory.IMAGE, "image/webp"),
    # documents
    "pdf": (FileCategory.DOCUMENT, "application/pdf"),
    "docx": (FileCategory.DOCUMENT,
             "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "xlsx": (FileCategory.DOCUMENT,
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "pptx": (FileCategory.DOCUMENT,
             "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    "txt": (FileCategory.DOCUMENT, "text/plain"),
    "rtf": (FileCategory.DOCUMENT, "application/rtf"),
}

# A few magic-byte signatures for sanity-checking declared extensions.
_MAGIC: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
    (b"%PDF", "pdf"),
    (b"PK\x03\x04", "zip"),   # docx/xlsx/pptx are zip containers
    (b"RIFF", "webp"),        # followed by 'WEBP' at offset 8
    (b"{\\rtf", "rtf"),
]


@dataclass(slots=True)
class FileInfo:
    """Result of detecting a file."""

    extension: str           # normalised, no dot, lowercase
    category: str            # image | document | special
    mime_type: str
    is_supported: bool


def detect_extension(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def sniff_magic(head: bytes) -> str | None:
    """Best-effort detection from the first bytes of a file."""
    for sig, name in _MAGIC:
        if head.startswith(sig):
            if name == "zip":
                return "zip"  # caller resolves to docx/xlsx/pptx via extension
            if name == "webp" and head[8:12] != b"WEBP":
                continue
            return name
    return None


def detect(filename: str, head: bytes | None = None) -> FileInfo:
    """Detect a file's type from its name (and optional leading bytes)."""
    ext = detect_extension(filename)
    category, mime = _EXT_MAP.get(ext, (FileCategory.SPECIAL, "application/octet-stream"))
    supported = ext in _EXT_MAP

    # Optional: validate the extension against magic bytes for common spoofs.
    if head:
        magic = sniff_magic(head)
        if magic and magic not in {"zip"} and ext in {"png", "jpg", "jpeg", "pdf"}:
            # Normalise jpeg/jpg equivalence.
            expected = "jpg" if magic == "jpg" else magic
            actual = "jpg" if ext in {"jpg", "jpeg"} else ext
            if expected != actual:
                # Trust magic bytes over a wrong extension.
                category, mime = _EXT_MAP.get(expected, (category, mime))

    return FileInfo(extension=ext, category=category, mime_type=mime, is_supported=supported)


def is_allowed(filename: str) -> bool:
    """Whether the file extension is on the allow-list (TZ section 1.2)."""
    return detect_extension(filename) in _EXT_MAP
