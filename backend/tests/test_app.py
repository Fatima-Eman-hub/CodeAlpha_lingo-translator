"""
Automated tests for backend/app.py

Run with:  pytest  (from inside backend/)

Design choice: these tests never make a real network call to Google Translate
and never touch a real database. Both are mocked:
  - GoogleTranslator.translate is monkeypatched per-test to return a canned value
    (or raise, to test error handling) — this keeps tests fast and deterministic,
    and means they pass with no internet connection at all.
  - app.get_db is monkeypatched to return a fake connection/cursor pair (MagicMock)
    so route logic can be tested without a live Postgres/Neon database.

This mirrors a standard testing practice: test YOUR code's logic (validation,
routing, error handling), not third-party services you don't control.
"""

import sys
import os
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as app_module  # noqa: E402


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def clear_translation_cache():
    # Without this, two tests using the same text/source/target (several do —
    # they all translate "hello" en->ur) would silently share a cached result,
    # and a test expecting a mocked FAILURE could instead get a cached SUCCESS
    # from an earlier test. Order-dependent test flakiness, avoided.
    app_module._translation_cache.clear()
    yield


@pytest.fixture
def fake_db(monkeypatch):
    """Replaces app.get_db() with a MagicMock db/cursor pair for the duration of a test."""
    cur = MagicMock()
    db = MagicMock()
    db.cursor.return_value = cur
    monkeypatch.setattr(app_module, "get_db", lambda: db)
    return db, cur


VALID_USER_ID = "a1b2c3d4-e5f6-4789-a1b2-c3d4e5f6a7b8"


# ---------------------------------------------------------------------------
# /api/health
# ---------------------------------------------------------------------------

def test_health_ok(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_health_reports_database_configured_flag(client, monkeypatch):
    monkeypatch.setattr(app_module, "DATABASE_URL", "")
    assert client.get("/api/health").get_json()["database_configured"] is False

    monkeypatch.setattr(app_module, "DATABASE_URL", "postgresql://fake")
    assert client.get("/api/health").get_json()["database_configured"] is True


# ---------------------------------------------------------------------------
# /api/translate — validation
# ---------------------------------------------------------------------------

def test_translate_rejects_empty_text(client):
    res = client.post("/api/translate", json={"text": "", "source": "en", "target": "ur"})
    assert res.status_code == 400
    assert "text is required" in res.get_json()["error"]


def test_translate_rejects_malformed_json(client):
    res = client.post("/api/translate", data="not json", content_type="application/json")
    assert res.status_code == 400
    assert "valid JSON" in res.get_json()["error"]


def test_translate_rejects_text_too_long(client):
    long_text = "a" * (app_module.MAX_TEXT_LENGTH + 1)
    res = client.post("/api/translate", json={"text": long_text, "source": "en", "target": "ur"})
    assert res.status_code == 400
    assert "too long" in res.get_json()["error"]


def test_translate_rejects_unsupported_target(client):
    res = client.post("/api/translate", json={"text": "hi", "source": "en", "target": "xx"})
    assert res.status_code == 400
    assert "unsupported target language" in res.get_json()["error"]


def test_translate_rejects_unsupported_source(client):
    res = client.post("/api/translate", json={"text": "hi", "source": "xx", "target": "en"})
    assert res.status_code == 400
    assert "unsupported source language" in res.get_json()["error"]


# ---------------------------------------------------------------------------
# /api/translate — behavior
# ---------------------------------------------------------------------------

def test_translate_same_source_and_target_skips_the_api_call(client):
    with patch.object(app_module, "GoogleTranslator") as mock_gt:
        res = client.post("/api/translate", json={"text": "hello", "source": "en", "target": "en"})
        assert res.status_code == 200
        assert res.get_json()["translation"] == "hello"
        mock_gt.assert_not_called()  # the whole point: no wasted request


def test_translate_success(client):
    with patch.object(app_module, "GoogleTranslator") as mock_gt:
        mock_gt.return_value.translate.return_value = "ہیلو"
        res = client.post("/api/translate", json={"text": "hello", "source": "en", "target": "ur"})
        assert res.status_code == 200
        body = res.get_json()
        assert body["translation"] == "ہیلو"
        assert body["alternatives"] == []


def test_translate_upstream_failure_returns_502(client):
    # Both providers must fail for this to actually be a 502 now that there's
    # a fallback — this test specifically covers "everything is down".
    with patch.object(app_module, "GoogleTranslator") as mock_gt, \
         patch.object(app_module, "MyMemoryTranslator") as mock_mm:
        mock_gt.return_value.translate.side_effect = Exception("network exploded")
        mock_mm.return_value.translate.side_effect = Exception("fallback also down")
        res = client.post("/api/translate", json={"text": "hello", "source": "en", "target": "ur"})
        assert res.status_code == 502
        assert "error" in res.get_json()


def test_translate_falls_back_to_mymemory_when_google_fails(client):
    with patch.object(app_module, "GoogleTranslator") as mock_gt, \
         patch.object(app_module, "MyMemoryTranslator") as mock_mm:
        mock_gt.return_value.translate.side_effect = Exception("Google is having a bad day")
        mock_mm.return_value.translate.return_value = "ہیلو (via fallback)"
        res = client.post("/api/translate", json={"text": "hello", "source": "en", "target": "ur"})
        assert res.status_code == 200
        assert res.get_json()["translation"] == "ہیلو (via fallback)"


def test_translate_result_is_cached_on_second_identical_request(client):
    with patch.object(app_module, "GoogleTranslator") as mock_gt:
        mock_gt.return_value.translate.return_value = "ہیلو"
        res1 = client.post("/api/translate", json={"text": "hello", "source": "en", "target": "ur"})
        assert res1.status_code == 200
        assert mock_gt.return_value.translate.call_count == 1

        # Second identical request should hit the cache, not call the translator again
        res2 = client.post("/api/translate", json={"text": "hello", "source": "en", "target": "ur"})
        assert res2.status_code == 200
        assert res2.get_json()["translation"] == "ہیلو"
        assert mock_gt.return_value.translate.call_count == 1  # still 1, not 2


def test_translate_empty_result_returns_502(client):
    with patch.object(app_module, "GoogleTranslator") as mock_gt:
        mock_gt.return_value.translate.return_value = ""
        res = client.post("/api/translate", json={"text": "hello", "source": "en", "target": "ur"})
        assert res.status_code == 502


def test_translate_auto_detects_source_language(client):
    with patch.object(app_module, "GoogleTranslator") as mock_gt, \
         patch.object(app_module, "detect", return_value="en"):
        mock_gt.return_value.translate.return_value = "بہت خوب"
        res = client.post("/api/translate", json={"text": "great job", "source": "auto", "target": "ur"})
        assert res.status_code == 200
        assert res.get_json()["detectedLanguage"] == "English"


# ---------------------------------------------------------------------------
# /api/history — GET
# ---------------------------------------------------------------------------

def test_get_history_rejects_invalid_user_id(client):
    res = client.get("/api/history?user_id=ab")  # too short
    assert res.status_code == 400


def test_get_history_returns_rows_for_valid_user(client, fake_db):
    db, cur = fake_db
    cur.fetchall.return_value = [
        {"id": 1, "source_code": "en", "target_code": "ur", "src_text": "hi",
         "tgt_text": "ہائے", "favorited": False, "created_at": 123.0}
    ]
    res = client.get(f"/api/history?user_id={VALID_USER_ID}")
    assert res.status_code == 200
    assert len(res.get_json()["history"]) == 1
    # confirm the query was scoped to this specific user
    args, _ = cur.execute.call_args
    assert VALID_USER_ID in args[1]


# ---------------------------------------------------------------------------
# /api/history — POST
# ---------------------------------------------------------------------------

def test_save_history_rejects_invalid_user_id(client):
    res = client.post("/api/history", json={"user_id": "x"})
    assert res.status_code == 400


def test_save_history_rejects_missing_fields(client):
    res = client.post("/api/history", json={"user_id": VALID_USER_ID, "src_text": "hi"})
    assert res.status_code == 400
    assert "required" in res.get_json()["error"]


def test_save_history_success(client, fake_db):
    db, cur = fake_db
    cur.fetchone.return_value = {"id": 42}
    res = client.post("/api/history", json={
        "user_id": VALID_USER_ID, "source_code": "en", "target_code": "ur",
        "src_text": "hi", "tgt_text": "ہائے",
    })
    assert res.status_code == 201
    assert res.get_json()["id"] == 42
    assert db.commit.called


# ---------------------------------------------------------------------------
# /api/history/<id> — PATCH (favorite toggle)
# ---------------------------------------------------------------------------

def test_toggle_favorite_not_found(client, fake_db):
    db, cur = fake_db
    cur.fetchone.return_value = None
    res = client.patch("/api/history/999", json={"user_id": VALID_USER_ID})
    assert res.status_code == 404


def test_toggle_favorite_success(client, fake_db):
    db, cur = fake_db
    cur.fetchone.return_value = {"id": 1, "favorited": False}
    res = client.patch("/api/history/1", json={"user_id": VALID_USER_ID})
    assert res.status_code == 200
    assert res.get_json()["favorited"] is True


def test_toggle_favorite_wrong_user_cannot_access_row(client, fake_db):
    # Simulates the ownership check: querying WHERE id=X AND user_id=Y with the
    # WRONG user_id should behave exactly like the row not existing.
    db, cur = fake_db
    cur.fetchone.return_value = None  # DB layer returns nothing for a mismatched owner
    res = client.patch("/api/history/1", json={"user_id": "someone-elses-id-1234"})
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# /api/history/<id> — DELETE
# ---------------------------------------------------------------------------

def test_delete_history_rejects_invalid_user_id(client):
    res = client.delete("/api/history/1?user_id=x")
    assert res.status_code == 400


def test_delete_history_success(client, fake_db):
    db, cur = fake_db
    res = client.delete(f"/api/history/1?user_id={VALID_USER_ID}")
    assert res.status_code == 200
    assert res.get_json()["deleted"] is True


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_missing_database_url_returns_json_not_html(client, monkeypatch):
    def raise_runtime_error():
        raise RuntimeError("DATABASE_URL is not set.")
    monkeypatch.setattr(app_module, "get_db", raise_runtime_error)

    res = client.get(f"/api/history?user_id={VALID_USER_ID}")
    assert res.status_code == 500
    assert res.content_type == "application/json"
    assert "DATABASE_URL" in res.get_json()["error"]
