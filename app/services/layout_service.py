"""Layout analysis (TZ section 2.6) and heuristic table detection (TZ 2.7).

Two paths:

  * **PP-Structure** — if PaddleOCR's structure engine is installed it is used
    for high-quality region/table detection (via ``app.ocr.structure``).
  * **Heuristic** — otherwise OCR text-boxes are grouped into lines and
    classified (heading vs body) by relative height, with consecutive
    multi-column lines merged into tables. This needs no extra dependencies.

Both produce the same ``blocks`` shape stored in ``Page.layout``:
    {"type": "heading"|"text"|"table", "text"|"rows": ..., "bbox": [...]}
"""
from __future__ import annotations

from statistics import median

from app.parsers.base import ParsedTable
from app.utils.logger import get_logger

log = get_logger("udip.layout")


def _box_center_y(b: dict) -> float:
    y1, y2 = b["bbox"][1], b["bbox"][3]
    return (y1 + y2) / 2


def _box_height(b: dict) -> float:
    return abs(b["bbox"][3] - b["bbox"][1])


def group_into_lines(boxes: list[dict]) -> list[list[dict]]:
    """Group OCR boxes that sit on the same horizontal line."""
    if not boxes:
        return []
    heights = [_box_height(b) for b in boxes if _box_height(b) > 0]
    line_tol = (median(heights) if heights else 10) * 0.6

    ordered = sorted(boxes, key=_box_center_y)
    lines: list[list[dict]] = []
    current: list[dict] = [ordered[0]]
    cur_y = _box_center_y(ordered[0])

    for b in ordered[1:]:
        y = _box_center_y(b)
        if abs(y - cur_y) <= line_tol:
            current.append(b)
        else:
            lines.append(sorted(current, key=lambda x: x["bbox"][0]))
            current = [b]
        cur_y = y
    lines.append(sorted(current, key=lambda x: x["bbox"][0]))
    return lines


def _line_bbox(line: list[dict]) -> list[float]:
    xs1 = [b["bbox"][0] for b in line]
    ys1 = [b["bbox"][1] for b in line]
    xs2 = [b["bbox"][2] for b in line]
    ys2 = [b["bbox"][3] for b in line]
    return [min(xs1), min(ys1), max(xs2), max(ys2)]


def analyze_boxes(boxes: list[dict]) -> tuple[list[dict], list[ParsedTable]]:
    """Turn OCR boxes into layout blocks + detected tables (heuristic)."""
    lines = group_into_lines(boxes)
    if not lines:
        return [], []

    median_h = median([_box_height(b) for ln in lines for b in ln if _box_height(b) > 0] or [10])
    heading_threshold = median_h * 1.4

    blocks: list[dict] = []
    tables: list[ParsedTable] = []
    pending_rows: list[list[str]] = []

    def flush_table():
        nonlocal pending_rows
        # A table needs >= 2 rows that each have >= 2 columns.
        if len(pending_rows) >= 2 and all(len(r) >= 2 for r in pending_rows):
            tables.append(ParsedTable(page_number=1, rows=pending_rows.copy()))
            blocks.append({"type": "table", "rows": pending_rows.copy()})
        elif pending_rows:
            # Not enough structure — emit as plain text lines.
            for r in pending_rows:
                blocks.append({"type": "text", "text": " ".join(r)})
        pending_rows = []

    for line in lines:
        texts = [b["text"] for b in line if b.get("text")]
        if not texts:
            continue
        is_row = len(line) >= 2 and _has_column_gaps(line)
        if is_row:
            pending_rows.append(texts)
            continue
        flush_table()

        line_h = max(_box_height(b) for b in line)
        text = " ".join(texts)
        btype = "heading" if line_h >= heading_threshold else "text"
        blocks.append({"type": btype, "text": text, "bbox": _line_bbox(line)})

    flush_table()
    return blocks, tables


def _has_column_gaps(line: list[dict]) -> bool:
    """True if boxes in a line are separated by gaps wider than typical spaces."""
    if len(line) < 2:
        return False
    widths = [abs(b["bbox"][2] - b["bbox"][0]) for b in line]
    avg_w = sum(widths) / len(widths)
    gaps = []
    for prev, nxt in zip(line, line[1:]):
        gaps.append(nxt["bbox"][0] - prev["bbox"][2])
    # A column boundary is a gap noticeably larger than an average word width.
    return any(g > max(avg_w * 0.8, 25) for g in gaps)


def analyze_page_from_ocr(boxes: list[dict], page_number: int = 1) -> dict:
    """Public entry: produce a layout dict for a page from its OCR boxes."""
    blocks, tables = analyze_boxes(boxes)
    for t in tables:
        t.page_number = page_number
    return {
        "blocks": blocks,
        "table_count": len(tables),
        "_tables": [t.rows for t in tables],
        "source": "heuristic",
    }
