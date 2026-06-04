"""V6 tests: SaaS layer — API keys, auth, admin stats (TZ section 6)."""
from __future__ import annotations

import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/udip_test_v6.db"

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from app.database.session import init_db  # noqa: E402

init_db()
client = TestClient(main.app)


def _create_key(name="test") -> str:
    r = client.post("/api/v1/keys", json={"name": name})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["api_key"].startswith("udip_")
    return body["api_key"]


def test_create_key_returns_raw_once():
    raw = _create_key("ilova-1")
    assert len(raw) > 20


def test_list_keys_requires_auth():
    # No key -> 401.
    assert client.get("/api/v1/keys").status_code == 401
    # Valid key -> 200.
    key = _create_key("ilova-2")
    r = client.get("/api/v1/keys", headers={"X-API-Key": key})
    assert r.status_code == 200
    assert any(k["name"] == "ilova-2" for k in r.json())


def test_admin_stats_requires_auth():
    assert client.get("/api/v1/admin/stats").status_code == 401
    key = _create_key("admin-key")
    r = client.get("/api/v1/admin/stats", headers={"X-API-Key": key})
    assert r.status_code == 200
    body = r.json()
    assert "documents" in body and "api_keys" in body
    assert body["api_keys"] >= 1


def test_admin_stats_reflects_documents():
    key = _create_key("stats-key")
    client.post("/api/v1/upload",
                files={"file": ("d.txt", b"Salom dunyo statistika", "text/plain")})
    r = client.get("/api/v1/admin/stats", headers={"X-API-Key": key})
    body = r.json()
    assert body["documents"] >= 1
    assert "txt" in body["documents_by_type"]


def test_invalid_key_rejected():
    r = client.get("/api/v1/keys", headers={"X-API-Key": "udip_invalidkey123"})
    assert r.status_code == 401


def test_revoke_key():
    key = _create_key("to-revoke")
    # Find its id.
    keys = client.get("/api/v1/keys", headers={"X-API-Key": key}).json()
    kid = next(k["id"] for k in keys if k["name"] == "to-revoke")
    # Revoke it (using itself).
    r = client.delete(f"/api/v1/keys/{kid}", headers={"X-API-Key": key})
    assert r.status_code == 200
    # The revoked key no longer authenticates.
    assert client.get("/api/v1/keys", headers={"X-API-Key": key}).status_code == 401


def test_admin_panel_served():
    r = client.get("/admin")
    assert r.status_code == 200
    assert "Boshqaruv paneli" in r.text
