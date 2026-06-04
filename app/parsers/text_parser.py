"""Plain-text & RTF parser (TZ section 1.2: TXT, RTF).

TXT is read directly (encoding auto-detected best-effort). RTF is converted to
plain text via ``striprtf``; if the library is missing the raw text is returned
with control words stripped by a minimal fallback.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.parsers.base import BaseParser, ParsedPage, ParseResult
from app.utils.logger import get_logger

log = get_logger("udip.parsers.text")

try:
    from striprtf.striprtf import rtf_to_text

    _HAS_STRIPRTF = True
except Exception:  # pragma: no cover
    _HAS_STRIPRTF = False

_ENCODINGS = ("utf-8", "utf-8-sig", "cp1251", "latin-1")


def _read_text(path: str) -> str:
    raw = Path(path).read_bytes()
    for enc in _ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


class TextParser(BaseParser):
    name = "text"
    extensions = ("txt", "rtf")

    def parse(self, file_path: str, **kwargs) -> ParseResult:
        ext = Path(file_path).suffix.lower().lstrip(".")
        content = _read_text(file_path)

        if ext == "rtf":
            if _HAS_STRIPRTF:
                content = rtf_to_text(content)
            else:  # pragma: no cover - minimal fallback
                content = re.sub(r"\\[a-z]+-?\d* ?|[{}]", "", content)

        text = content.strip()
        page = ParsedPage(page_number=1, text=text,
                          blocks=[{"type": "text", "text": text}] if text else [])
        meta = {
            "page_count": 1,
            "characters": len(text),
            "lines": text.count("\n") + 1 if text else 0,
        }
        log.info("Parsed %s %s: %d chars", ext.upper(), file_path, len(text))
        return ParseResult(parser=self.name, pages=[page], metadata=meta)


text_parser = TextParser()
