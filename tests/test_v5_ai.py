"""V5 tests: AI analysis, entities, chat (RAG) and export (TZ 2.10-2.12)."""
from __future__ import annotations

import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/udip_test_v5.db"

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from app.database.session import init_db  # noqa: E402

init_db()
client = TestClient(main.app)

_DOC_TEXT = (
    "Shartnoma 12.05.2024 sanasida tuzildi. "
    "To'lov summasi 1 500 000 so'm qilib belgilandi. "
    "Aloqa uchun: ali@example.com yoki +998 90 123 45 67. "
    "Chegirma 15% miqdorida. To'lov muddati 30 kun deb kelishildi."
)


def _upload(name="shartnoma.txt", text=_DOC_TEXT) -> dict:
    r = client.post("/api/v1/upload", files={"file": (name, text.encode("utf-8"), "text/plain")})
    assert r.status_code == 200, r.text
    return r.json()["document"]


# ---- entities ------------------------------------------------------
def test_entities_auto_extracted_on_upload():
    doc = _upload()
    r = client.get(f"/api/v1/ai/entities/{doc['id']}")
    assert r.status_code == 200
    types = {e["entity_type"] for e in r.json()["entities"]}
    assert {"date", "money", "email", "phone", "percent"} <= types


def test_entities_values():
    doc = _upload("e.txt")
    ents = client.post(f"/api/v1/ai/entities/{doc['id']}").json()["entities"]
    by_type = {e["entity_type"]: e["value"] for e in ents}
    assert by_type["email"] == "ali@example.com"
    assert "%" in by_type["percent"]
    assert "so'm" in by_type["money"].lower() or "so’m" in by_type["money"]


# ---- summary -------------------------------------------------------
def test_summarize_returns_text():
    doc = _upload("s.txt")
    r = client.post("/api/v1/ai/summarize", json={"document_id": doc["id"], "max_sentences": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["model"] == "stub"
    assert len(body["summary"]) > 0


# ---- chat (RAG) ----------------------------------------------------
def test_chat_grounded_answer():
    doc = _upload("c.txt")
    r = client.post("/api/v1/chat", json={"question": "To'lov summasi qancha?",
                                          "document_id": doc["id"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "1 500 000" in body["answer"]      # grounded in the document
    assert len(body["sources"]) >= 1


def test_chat_unknown_question():
    doc = _upload("c2.txt", "Bu juda qisqa hujjat.")
    r = client.post("/api/v1/chat", json={"question": "Marsgacha masofa qancha?",
                                          "document_id": doc["id"]})
    assert r.status_code == 200


# ---- export --------------------------------------------------------
def test_export_all_formats():
    doc = _upload("exp.txt")
    for fmt in ("txt", "json", "md", "docx"):
        r = client.post("/api/v1/export", json={"document_id": doc["id"], "format": fmt})
        assert r.status_code == 200, f"{fmt}: {r.text}"
        body = r.json()
        assert body["format"] == fmt
        # The exported file is downloadable.
        dl = client.get(body["download_url"])
        assert dl.status_code == 200
        assert len(dl.content) > 0


def test_export_invalid_format():
    doc = _upload("bad.txt")
    r = client.post("/api/v1/export", json={"document_id": doc["id"], "format": "xml"})
    assert r.status_code == 400
