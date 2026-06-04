"""End-to-end smoke tests for the V1 pipeline: upload → parse → OCR → task.

Run with:  pytest tests/test_v1_pipeline.py -v
The OCR backend is the stub here (no PaddleOCR/Tesseract in CI), so we assert
on pipeline *mechanics* rather than recognised text quality.
"""
from __future__ import annotations

import io
import os
import tempfile

# Isolate the test database before importing the app.
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/udip_test.db"

import fitz  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

import main  # noqa: E402
from app.database.session import init_db  # noqa: E402

# TestClient is not used as a context manager, so trigger schema creation here
# (the app's lifespan/init_db only runs under `with TestClient(app)`).
init_db()

client = TestClient(main.app)


def _make_png_bytes(text: str = "Salom dunyo") -> bytes:
    img = Image.new("RGB", (400, 120), "white")
    ImageDraw.Draw(img).text((20, 40), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_pdf_bytes(text: str = "Salom talabalar") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=14)
    data = doc.tobytes()
    doc.close()
    return data


def test_health():
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/ping").json()["message"] == "pong"


def test_upload_image_creates_document():
    files = {"file": ("hello.png", _make_png_bytes(), "image/png")}
    r = client.post("/api/v1/upload", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["document"]["file_type"] == "png"
    assert body["document"]["category"] == "image"
    assert body["document"]["status"] in {"ocr_done", "parsed"}


def test_upload_text_pdf_extracts_text():
    files = {"file": ("doc.pdf", _make_pdf_bytes("Salom talabalar"), "application/pdf")}
    r = client.post("/api/v1/upload", files=files)
    assert r.status_code == 200, r.text
    public_id = r.json()["document"]["public_id"]

    detail = client.get(f"/api/v1/documents/{public_id}").json()
    assert detail["page_count"] == 1
    assert "Salom talabalar" in (detail["pages"][0]["text"] or "")


def test_unsupported_format_rejected():
    files = {"file": ("evil.exe", b"MZ\x90\x00", "application/octet-stream")}
    r = client.post("/api/v1/upload", files=files)
    assert r.status_code == 415


def test_async_upload_creates_task():
    files = {"file": ("async.pdf", _make_pdf_bytes(), "application/pdf")}
    r = client.post("/api/v1/upload?async_mode=true", files=files)
    assert r.status_code == 200, r.text
    task_id = r.json()["task_id"]
    assert task_id
    # Background task runs in the TestClient's thread pool; poll the status.
    status = client.get(f"/api/v1/task/{task_id}")
    assert status.status_code == 200
    assert status.json()["status"] in {"pending", "running", "success"}


def test_ocr_engine_status():
    r = client.get("/api/v1/ocr/engine")
    assert r.status_code == 200
    assert "real_engine" in r.json()


def test_documents_list():
    r = client.get("/api/v1/documents")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
