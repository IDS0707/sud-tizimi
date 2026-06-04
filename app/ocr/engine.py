"""OCR engine (TZ section 2.1: Optical Character Recognition).

Recognises text — and its position on the page — from an image. Three backends
are tried in priority order so the platform works in as many environments as
possible:

    1. PaddleOCR   (best quality; TZ-recommended; heavy install)
    2. Tesseract   (via pytesseract; common, lighter)
    3. Stub        (always available; returns an explicit "not installed" note)

The engine is selected once, lazily, on first use. Output is normalised to a
single shape regardless of backend:

    {"text": str, "boxes": [{"text","bbox":[x1,y1,x2,y2],"confidence"}], "confidence": float}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings
from app.ocr.preprocess import preprocess_image
from app.utils.logger import get_logger

log = get_logger("udip.ocr.engine")


@dataclass
class OcrOutput:
    text: str = ""
    boxes: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    engine: str = "stub"
    lang: str | None = None

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "boxes": self.boxes,
            "confidence": self.confidence,
            "engine": self.engine,
            "lang": self.lang,
        }


class _PaddleBackend:
    name = "paddleocr"

    def __init__(self, lang: str) -> None:
        from paddleocr import PaddleOCR

        self.lang = lang
        self._ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)

    def run(self, image_path: str) -> OcrOutput:
        raw = self._ocr.ocr(image_path, cls=True)
        boxes: list[dict] = []
        texts: list[str] = []
        confs: list[float] = []
        # PaddleOCR returns [[ [box, (text, conf)], ... ]] (one list per image).
        for page in raw or []:
            for line in page or []:
                box, (text, conf) = line[0], line[1]
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                bbox = [min(xs), min(ys), max(xs), max(ys)]
                if conf >= settings.ocr_min_confidence:
                    boxes.append({"text": text, "bbox": bbox, "confidence": float(conf)})
                    texts.append(text)
                    confs.append(float(conf))
        return OcrOutput(
            text="\n".join(texts),
            boxes=boxes,
            confidence=(sum(confs) / len(confs)) if confs else 0.0,
            engine=self.name,
            lang=self.lang,
        )


# Common Windows install locations for the Tesseract binary.
_TESSERACT_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)
# Map short language codes to Tesseract's 3-letter codes (pass-through otherwise).
_TESS_LANG_MAP = {"en": "eng", "ru": "rus", "uz": "uzb", "ch": "chi_sim"}


def _resolve_tess_lang(lang: str) -> str:
    """Allow 'uzb+rus+eng' (pass-through) or short codes like 'en' -> 'eng'."""
    if "+" in lang or len(lang) > 3:
        return lang
    return _TESS_LANG_MAP.get(lang, lang)


class _TesseractBackend:
    name = "tesseract"

    def __init__(self, lang: str) -> None:
        import os

        import pytesseract

        # Point pytesseract at the binary (config, then common install paths).
        cmd = settings.tesseract_cmd
        if not cmd:
            cmd = next((p for p in _TESSERACT_PATHS if os.path.exists(p)), None)
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd

        # Point Tesseract at extra language packs via env var (handles paths
        # with spaces, unlike the space-split --tessdata-dir config option).
        if settings.tessdata_dir:
            os.environ["TESSDATA_PREFIX"] = settings.tessdata_dir

        # Verify the engine actually runs (raises if not installed).
        pytesseract.get_tesseract_version()

        self.lang = _resolve_tess_lang(lang)
        self._pt = pytesseract
        self._config = ""

    def run(self, image_path: str) -> OcrOutput:
        from PIL import Image

        img = Image.open(image_path)
        data = self._pt.image_to_data(
            img, lang=self.lang, config=self._config, output_type=self._pt.Output.DICT
        )
        boxes: list[dict] = []
        texts: list[str] = []
        confs: list[float] = []
        n = len(data.get("text", []))
        for i in range(n):
            text = (data["text"][i] or "").strip()
            conf = float(data["conf"][i]) / 100.0 if data["conf"][i] not in ("-1", -1) else 0.0
            if text and conf >= settings.ocr_min_confidence:
                x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
                boxes.append({"text": text, "bbox": [x, y, x + w, y + h], "confidence": conf})
                texts.append(text)
                confs.append(conf)
        return OcrOutput(
            text=" ".join(texts),
            boxes=boxes,
            confidence=(sum(confs) / len(confs)) if confs else 0.0,
            engine=self.name,
            lang=self.lang,
        )


class _StubBackend:
    name = "stub"

    def __init__(self, lang: str) -> None:
        self.lang = lang

    def run(self, image_path: str) -> OcrOutput:
        log.warning(
            "No OCR backend installed — returning stub. "
            "Install 'paddleocr' or 'pytesseract'+Tesseract for real OCR."
        )
        return OcrOutput(
            text="",
            boxes=[],
            confidence=0.0,
            engine=self.name,
            lang=self.lang,
        )


def _build_backend(lang: str):
    """Pick the best available OCR backend."""
    for builder in (_PaddleBackend, _TesseractBackend):
        try:
            backend = builder(lang)
            log.info("OCR backend: %s (lang=%s)", backend.name, lang)
            return backend
        except Exception as exc:  # backend not installed / failed to init
            log.debug("OCR backend %s unavailable: %s", builder.name, exc)
    log.info("OCR backend: stub (no real engine installed)")
    return _StubBackend(lang)


class OcrEngine:
    """Public OCR facade. Lazily initialises the chosen backend per language."""

    def __init__(self) -> None:
        self._backends: dict[str, object] = {}

    def _backend_for(self, lang: str):
        if lang not in self._backends:
            self._backends[lang] = _build_backend(lang)
        return self._backends[lang]

    def recognize(self, image_path: str | Path, *, lang: str | None = None,
                  preprocess: bool = True) -> OcrOutput:
        """Recognise text in a single image."""
        lang = lang or settings.ocr_lang
        path = str(image_path)
        if preprocess:
            path = preprocess_image(path)
        backend = self._backend_for(lang)
        try:
            return backend.run(path)
        except Exception as exc:  # pragma: no cover - runtime backend failure
            log.error("OCR run failed on %s: %s", path, exc)
            return OcrOutput(engine=getattr(backend, "name", "stub"), lang=lang)

    @property
    def is_real(self) -> bool:
        """True if a real (non-stub) backend is available for the default lang."""
        return not isinstance(self._backend_for(settings.ocr_lang), _StubBackend)


# Module-level singleton.
ocr_engine = OcrEngine()
