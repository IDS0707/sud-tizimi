"""Image pre-processing for OCR (TZ section 5: OpenCV, Pillow).

Clean-up steps (grayscale, denoise, threshold, deskew) noticeably improve OCR
accuracy on scans. Every step degrades gracefully: if OpenCV/NumPy are absent
the original image path is returned unchanged so the pipeline never breaks.
"""
from __future__ import annotations

from pathlib import Path

from app.utils.logger import get_logger

log = get_logger("udip.ocr.preprocess")

try:
    import cv2
    import numpy as np

    _HAS_CV2 = True
except Exception:  # pragma: no cover - optional dependency
    _HAS_CV2 = False


def available() -> bool:
    return _HAS_CV2


# Below this longest-side size (px) text is too small; upscale helps OCR.
_MIN_LONG_SIDE = 1500
_TARGET_LONG_SIDE = 1800


def preprocess_image(src_path: str | Path, out_path: str | Path | None = None) -> str:
    """Return a path to an image tuned for OCR.

    Testing on real screenshots showed that aggressive binarisation
    (adaptive threshold + denoise) *hurts* accuracy on clean/digital images.
    So the strategy is deliberately gentle:

      * Large, already-crisp images  -> used as-is (best results).
      * Small images                 -> upscaled (Tesseract reads big text
                                        far better than tiny text).

    If OpenCV is unavailable the source path is returned untouched.
    """
    src_path = Path(src_path)
    if not _HAS_CV2:
        return str(src_path)

    try:
        img = cv2.imread(str(src_path))
        if img is None:
            return str(src_path)

        h, w = img.shape[:2]
        longest = max(h, w)
        if longest >= _MIN_LONG_SIDE:
            # Clean / high-res image: leave it alone — preprocessing only hurts.
            return str(src_path)

        # Small image: upscale (cubic) and grayscale to help recognition.
        scale = _TARGET_LONG_SIDE / max(longest, 1)
        up = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)

        out = Path(out_path) if out_path else src_path.with_name(src_path.stem + "_pre.png")
        cv2.imwrite(str(out), gray)
        return str(out)
    except Exception as exc:  # pragma: no cover
        log.warning("Preprocess failed (%s); using original image", exc)
        return str(src_path)


def _deskew(image: "np.ndarray") -> "np.ndarray":
    """Rotate the image so text lines are horizontal."""
    try:
        coords = np.column_stack(np.where(image < 128))
        if coords.size == 0:
            return image
        angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + angle) if angle < -45 else -angle
        if abs(angle) < 0.5:
            return image
        (h, w) = image.shape[:2]
        m = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        return cv2.warpAffine(
            image, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )
    except Exception:  # pragma: no cover
        return image
