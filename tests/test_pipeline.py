"""
Pipeline & API tests (pakai TIKTOK_DRY_RUN=true, tanpa kredensial TikTok).

Jalankan: pytest -v
"""

import asyncio
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import async_session, init_db
from app.models import Content, ContentStatus
from app.services.publisher import publish_content, publish_due_contents


# ---- Helpers ----

def _run(coro):
    """Jalankan coroutine di event loop baru (tidak butuh plugin pytest-asyncio)."""
    return asyncio.run(coro)


async def _make_content(topic="Test Topik", status=ContentStatus.DRAFT, scheduled_at=None):
    async with async_session() as db:
        c = Content(
            topic=topic,
            hook="Hook test",
            script="Script narasi test untuk konten kesehatan non-pengganti dokter.",
            caption="Caption test",
            hashtags="#Kesehatan #Sehat",
            visual_notes="Scene test",
            disclaimer="Konten ini bukan pengganti nasihat dokter.",
            status=status,
            scheduled_at=scheduled_at,
        )
        db.add(c)
        await db.commit()
        await db.refresh(c)
        return c.id


# ---- Fixtures ----

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_db():
    async def _clean():
        await init_db()
        async with async_session() as db:
            from sqlalchemy import delete
            await db.execute(delete(Content))
            await db.commit()
    _run(_clean())
    yield
    _run(_clean())


# ---- Health ----

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---- Contents CRUD + approve/reject ----

def test_create_and_list_content(client):
    r = client.post("/api/contents/", json={
        "topic": "Manfaat Jalan Kaki",
        "hook": "Berjalan 30 menit bisa mengubah hidup?",
        "script": "Jalan kaki rutin baik untuk kesehatan jantung.",
        "caption": "Yuk sehat",
        "hashtags": "#Sehat",
        "disclaimer": "Bukan pengganti dokter.",
    })
    assert r.status_code == 201
    cid = r.json()["id"]

    r = client.get("/api/contents/")
    assert r.status_code == 200
    body = r.json()
    items = body if isinstance(body, list) else body.get("value") or body
    assert any(x["id"] == cid for x in items)


def test_approve_and_reject_flow(client):
    cid_review = _run(_make_content(status=ContentStatus.REVIEW))
    r = client.post(f"/api/contents/{cid_review}/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "scheduled"

    cid_reject = _run(_make_content(status=ContentStatus.REVIEW))
    r = client.post(f"/api/contents/{cid_reject}/reject")
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


def test_approve_non_review_rejected(client):
    cid = _run(_make_content(status=ContentStatus.DRAFT))
    r = client.post(f"/api/contents/{cid}/approve")
    assert r.status_code == 400


def test_content_404(client):
    r = client.get("/api/contents/99999")
    assert r.status_code == 404


# ---- Video status ----

def test_video_status_ok(client):
    cid = _run(_make_content())
    r = client.get(f"/api/video/{cid}/status")
    assert r.status_code == 200
    body = r.json()
    assert "audio_exists" in body and "video_exists" in body


def test_video_status_not_found(client):
    r = client.get("/api/video/99999/status")
    assert r.status_code == 404


# ---- Dry-run publish pipeline ----

def test_publish_dry_run_sets_published():
    cid = _run(_make_content(status=ContentStatus.SCHEDULED, scheduled_at=datetime.now() - timedelta(hours=1)))
    result = _run(publish_content(cid, force=False))
    assert result["success"] is True
    assert "DRYRUN" in result.get("publish_id", "")

    async def _check():
        from sqlalchemy import select
        async with async_session() as db:
            c = (await db.execute(select(Content).where(Content.id == cid))).scalar_one()
            assert c.status == ContentStatus.PUBLISHED
            assert c.published_at is not None
            assert c.tiktok_post_id
    _run(_check())


def test_publish_wrong_status_blocked():
    cid = _run(_make_content(status=ContentStatus.REJECTED))
    result = _run(publish_content(cid, force=False))
    assert result["success"] is False


def test_publish_due_sweep_only_past():
    cid1 = _run(_make_content(status=ContentStatus.SCHEDULED, scheduled_at=datetime.now() - timedelta(hours=1)))
    cid2 = _run(_make_content(status=ContentStatus.SCHEDULED, scheduled_at=datetime.now() - timedelta(minutes=5)))
    cid3 = _run(_make_content(status=ContentStatus.SCHEDULED, scheduled_at=datetime.now() + timedelta(hours=5)))
    summary = _run(publish_due_contents())
    assert summary["processed"] == 2

    async def _check():
        from sqlalchemy import select
        async with async_session() as db:
            for cid in (cid1, cid2):
                c = (await db.execute(select(Content).where(Content.id == cid))).scalar_one()
                assert c.status == ContentStatus.PUBLISHED
            c3 = (await db.execute(select(Content).where(Content.id == cid3))).scalar_one()
            assert c3.status == ContentStatus.SCHEDULED
    _run(_check())


def test_publish_manual_via_api(client):
    cid = _run(_make_content(status=ContentStatus.SCHEDULED, scheduled_at=datetime.now() + timedelta(hours=1)))
    r = client.post(f"/api/contents/{cid}/publish")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "DRYRUN" in body.get("publish_id", "")


def test_draft_fallback_hint_matches_scope_and_unaudited():
    from app.services.publisher import _should_fallback_to_draft
    assert _should_fallback_to_draft({"success": False, "code": "scope_not_authorized", "error": "..."})
    assert _should_fallback_to_draft({"success": False, "error": "TikTok error [unaudited_app]: app not audited"})
    assert _should_fallback_to_draft({"success": False, "error": "Init failed (401): permission denied"})
    assert not _should_fallback_to_draft({"success": False, "error": "TikTok error [invalid_params]: video info empty"})


def test_publish_falls_back_to_draft_on_scope_error(monkeypatch):
    import app.services.publisher as publisher

    async def fake_upload_video(*args, **kwargs):
        return {"success": False, "code": "scope_not_authorized", "error": "TikTok error [scope_not_authorized]: not authorized"}

    async def fake_upload_draft(*args, **kwargs):
        return {"success": True, "publish_id": "inbox-123", "mode": "draft"}

    cid = _run(_make_content(status=ContentStatus.SCHEDULED, scheduled_at=datetime.now() - timedelta(hours=1)))
    monkeypatch.setattr(publisher, "upload_video", fake_upload_video)
    monkeypatch.setattr(publisher, "upload_draft", fake_upload_draft)

    result = _run(publisher.publish_content(cid, force=False))
    assert result["success"] is True
    assert result["mode"] == "draft"

    async def _check():
        from sqlalchemy import select
        async with async_session() as db:
            c = (await db.execute(select(Content).where(Content.id == cid))).scalar_one()
            assert c.status == ContentStatus.DRAFT
            assert c.tiktok_post_id == "inbox-123"
    _run(_check())


# ---- TTS ----

def test_disclaimer_stripped_from_narration():
    from app.services.tts import strip_disclaimer
    script = "Ini narasi. Konten ini bukan pengganti nasihat dokter atau tenaga medis profesional. Konsultasikan kondisi Anda."
    out = strip_disclaimer(script)
    assert "konsultasikan" not in out.lower()
    assert "Ini narasi" in out


def test_disclaimer_kept_if_absent():
    from app.services.tts import strip_disclaimer
    assert strip_disclaimer("Narasi bersih tanpa disclaimer.") == "Narasi bersih tanpa disclaimer."


# ---- TikTok auth helpers ----

def test_store_status_default():
    from app.services.tiktok_auth import store_status
    status = store_status()
    assert "has_access_token" in status
    assert "has_refresh_token" in status


def test_tiktok_login_redirects(client):
    r = client.get("/auth/tiktok/login", follow_redirects=False)
    assert r.status_code in (302, 303, 307)
    if "client_key=" not in r.headers["location"]:
        assert "tiktok=notconfigured" in r.headers["location"]
    else:
        assert "tiktok.com/v2/auth/authorize" in r.headers["location"]
        assert "response_type=code" in r.headers["location"]
        assert "code_challenge=" in r.headers["location"]