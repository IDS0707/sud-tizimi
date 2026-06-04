"""Parser registry — dispatch a file to the right parser by extension.

New parsers register themselves here as they are implemented across the roadmap
(PDF + images in V1; DOCX/XLSX/PPTX/TXT/RTF in V2).
"""
from __future__ import annotations

from app.parsers.base import BaseParser, ParseResult
from app.parsers.image_parser import image_parser
from app.parsers.pdf_parser import pdf_parser
from app.utils.logger import get_logger

log = get_logger("udip.parsers.registry")

# extension -> parser instance
_REGISTRY: dict[str, BaseParser] = {}


def register(parser: BaseParser) -> None:
    for ext in parser.extensions:
        _REGISTRY[ext] = parser


# --- V1 parsers ---
register(pdf_parser)
register(image_parser)


def get_parser(extension: str) -> BaseParser | None:
    return _REGISTRY.get(extension.lower().lstrip("."))


def supported_extensions() -> list[str]:
    return sorted(_REGISTRY.keys())


def parse_file(file_path: str, extension: str, **kwargs) -> ParseResult:
    """Parse a file with the parser registered for ``extension``."""
    parser = get_parser(extension)
    if parser is None:
        log.warning("No parser registered for .%s", extension)
        return ParseResult(parser="none", metadata={"error": f"unsupported: {extension}"})
    return parser.parse(file_path, **kwargs)
