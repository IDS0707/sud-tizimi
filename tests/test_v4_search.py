"""V4 tests: smart search (TZ 2.9 / 3) and formula OCR status (TZ 2.8)."""
from __future__ import annotations

import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/udip_test_v4.db"

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from app.database.session import init_db  # noqa: E402

init_db()
client = TestClient(main.app)


def _upload_txt(name: str, text: str) -> dict:
    r = client.post("/api/v1/upload",
                    files={"file": (name, text.encode("utf-8"), "text/plain")})
    assert r.status_code == 200, r.text
    return r.json()["document"]


def _setup_corpus():
    _upload_txt("a.txt", "Salom dunyo. Bu birinchi hujjat. To'lov muddati 30 kun.")
    _upload_txt("b.txt", "Salom talabalar, darsga xush kelibsiz.")
    _upload_txt("c.txt", "Hisob-faktura raqami 12345, summa 500000 so'm.")


def test_search_finds_keyword():
    _setup_corpus()
    r = client.post("/api/v1/search", json={"query": "salom"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 2
    files = {h["filename"] for h in body["results"]}
    assert "a.txt" in files and "b.txt" in files


def test_search_highlights_match():
    r = client.post("/api/v1/search", json={"query": "talabalar"})
    body = r.json()
    assert body["total"] >= 1
    top = body["results"][0]
    assert "<mark>" in top["snippet"].lower()
    assert top["filename"] == "b.txt"
    assert top["page_number"] == 1


def test_search_scoped_to_document():
    doc = _upload_txt("scoped.txt", "Maxsus kalit so'z: qwerty topildi.")
    r = client.post("/api/v1/search", json={"query": "qwerty", "document_id": doc["id"]})
    body = r.json()
    assert body["total"] == 1
    assert body["results"][0]["public_id"] == doc["public_id"]


def test_search_no_results():
    r = client.post("/api/v1/search", json={"query": "zzxqwnonexistent"})
    assert r.json()["total"] == 0
    assert r.json()["results"] == []


def test_search_ranking_phrase_first():
    # A doc containing the exact phrase should outrank scattered-token docs.
    _upload_txt("phrase.txt", "Mukammal hujjat tahlili platformasi haqida.")
    _upload_txt("scatter.txt", "Hujjat bu yerda. Tahlil alohida joyda.")
    r = client.post("/api/v1/search", json={"query": "hujjat tahlili"})
    body = r.json()
    assert body["total"] >= 1
    assert body["results"][0]["filename"] == "phrase.txt"


def test_formula_status():
    r = client.get("/api/v1/formula/status")
    assert r.status_code == 200
    assert "available" in r.json()
