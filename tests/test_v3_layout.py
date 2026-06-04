"""V3 tests: layout analysis (TZ 2.6) and table recognition (TZ 2.7)."""
from __future__ import annotations

import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/udip_test_v3.db"

import fitz  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from app.database.session import init_db  # noqa: E402
from app.services import layout_service  # noqa: E402

init_db()
client = TestClient(main.app)


# ---- heuristic layout from OCR boxes -------------------------------
def _box(text, x1, y1, x2, y2, conf=0.9):
    return {"text": text, "bbox": [x1, y1, x2, y2], "confidence": conf}


def test_group_into_lines():
    boxes = [
        _box("Salom", 10, 10, 80, 30),
        _box("dunyo", 90, 12, 160, 32),   # same line
        _box("ikkinchi", 10, 60, 120, 80),  # next line
    ]
    lines = layout_service.group_into_lines(boxes)
    assert len(lines) == 2
    assert [b["text"] for b in lines[0]] == ["Salom", "dunyo"]


def test_heading_detected_by_height():
    boxes = [
        _box("KATTA SARLAVHA", 10, 10, 300, 50),   # height 40 -> heading
        _box("oddiy matn qatori", 10, 70, 200, 85),  # height 15 -> text
        _box("yana oddiy matn", 10, 95, 200, 110),
    ]
    blocks, _ = layout_service.analyze_boxes(boxes)
    types = [b["type"] for b in blocks]
    assert "heading" in types
    assert blocks[0]["type"] == "heading"


def test_table_detected_from_columns():
    # Two rows, two columns separated by a wide gap -> table.
    boxes = [
        _box("Mahsulot", 10, 10, 90, 28), _box("Narx", 250, 10, 320, 28),
        _box("Kitob", 10, 40, 70, 58),    _box("50000", 250, 40, 330, 58),
    ]
    blocks, tables = layout_service.analyze_boxes(boxes)
    assert len(tables) == 1
    assert tables[0].rows[0] == ["Mahsulot", "Narx"]
    assert any(b["type"] == "table" for b in blocks)


# ---- PDF heading detection -----------------------------------------
def _make_pdf_with_heading() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Katta Sarlavha", fontsize=26)
    page.insert_text((72, 120), "Bu oddiy matn qatori, kichik shrift bilan yozilgan.",
                     fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def test_pdf_heading_block():
    files = {"file": ("h.pdf", _make_pdf_with_heading(), "application/pdf")}
    pid = client.post("/api/v1/upload", files=files).json()["document"]["public_id"]
    detail = client.get(f"/api/v1/documents/{pid}").json()
    blocks = detail["pages"][0]["layout"]["blocks"]
    types = [b["type"] for b in blocks]
    assert "heading" in types
    assert any("Sarlavha" in b.get("text", "") and b["type"] == "heading" for b in blocks)


# ---- PDF table recognition (ruled table) ---------------------------
def _make_pdf_with_table() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    xs = [72, 220, 360]
    ys = [100, 130, 160, 190]
    for y in ys:
        page.draw_line((xs[0], y), (xs[-1], y))
    for x in xs:
        page.draw_line((x, ys[0]), (x, ys[-1]))
    cells = [["Oy", "Summa"], ["Yanvar", "1000"], ["Fevral", "2000"]]
    for r, row in enumerate(cells):
        for c, val in enumerate(row):
            page.insert_text((xs[c] + 6, ys[r] + 20), val, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def test_pdf_table_extracted():
    files = {"file": ("t.pdf", _make_pdf_with_table(), "application/pdf")}
    doc = client.post("/api/v1/upload", files=files).json()["document"]
    r = client.post("/api/v1/parse", json={"document_id": doc["id"]})
    tables = r.json()["tables"]
    assert len(tables) >= 1, "PDF jadval topilmadi"
    flat = [c for row in tables[0]["rows"] for c in row]
    assert "Oy" in flat and "Summa" in flat
