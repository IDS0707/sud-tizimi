"""Formula recognition (TZ section 2.8).

Reads a mathematical formula from an image and returns its textual form
(LaTeX). Uses ``pix2tex`` (LaTeX-OCR) if installed; otherwise returns a stub
result with a clear note — the platform keeps working without the heavy model.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.utils.logger import get_logger

log = get_logger("udip.ocr.formula")

_model = None
_tried = False


@dataclass
class FormulaResult:
    latex: str = ""
    engine: str = "stub"

    def to_dict(self) -> dict:
        return {"latex": self.latex, "engine": self.engine}


def _get_model():
    global _model, _tried
    if _tried:
        return _model
    _tried = True
    try:
        from pix2tex.cli import LatexOCR

        _model = LatexOCR()
        log.info("Formula OCR backend: pix2tex")
    except Exception as exc:  # pragma: no cover - optional dependency
        log.debug("pix2tex unavailable: %s", exc)
        _model = None
    return _model


def is_available() -> bool:
    return _get_model() is not None


def recognize_formula(image_path: str) -> FormulaResult:
    """Recognise a formula image, returning LaTeX (or an empty stub)."""
    model = _get_model()
    if model is None:
        log.warning("Formula OCR not installed (pip install pix2tex) — returning stub")
        return FormulaResult(latex="", engine="stub")
    try:  # pragma: no cover - exercised only when pix2tex is installed
        from PIL import Image

        latex = model(Image.open(image_path))
        return FormulaResult(latex=str(latex), engine="pix2tex")
    except Exception as exc:  # pragma: no cover
        log.warning("Formula OCR failed: %s", exc)
        return FormulaResult(latex="", engine="stub")
