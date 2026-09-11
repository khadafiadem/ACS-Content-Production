"""
TikTok OAuth helper: login URL, exchange code, refresh token (rotating), token store.

Alur:
1. Buka /auth/tiktok/login → redirect ke TikTok authorize
2. User login TikTok & approve scope → TikTok redirect ke /auth/tiktok/callback?code=..
3. Echange code → access_token (+refresh_token, open_id, scope). Disimpan ke data/tiktok_tokens.json
4. Access token ±24 jam → saat expired auto-refresh via refresh_token (rotated, ±365 hari)

Token store priority: file data/tiktok_tokens.json > env (fallback bootstrap).
"""

import base64
import hashlib
import json
import os
import secrets
import time
import logging
from datetime import datetime, timezone

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

TOKEN_FILE = "data/tiktok_tokens.json"
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize"
TOKEN_API = "https://open.tiktokapis.com/v2/oauth/token/"

DEFAULT_SCOPES = "user.info.basic,video.publish,video.upload"


def _pkce_pair() -> tuple[str, str]:
    """Generate code_verifier (43-128 chars) + base64url(SHA256) code_challenge (S256)."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def default_redirect_uri() -> str:
    scheme = "https" if getattr(settings, "ssl_enabled", False) else "http"
    return f"{scheme}://localhost:{settings.app_port}/auth/tiktok/callback"


def _redirect_uri() -> str:
    return settings.tiktok_redirect_uri or default_redirect_uri()


def client_configured() -> bool:
    return bool(settings.tiktok_client_key and settings.tiktok_client_secret)


# ---------- Token store ----------

def _store_path() -> str:
    return os.path.join(os.getcwd(), TOKEN_FILE)


def _read_store() -> dict:
    try:
        with open(_store_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_store(store: dict) -> None:
    os.makedirs(os.path.dirname(_store_path()), exist_ok=True)
    with open(_store_path(), "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)


def save_tokens(access_token, refresh_token, expires_in, open_id=None, scope=None) -> None:
    store = _read_store()
    store.update(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": time.time() + int(expires_in),
            "open_id": open_id or store.get("open_id"),
            "scope": scope or store.get("scope"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    _write_store(store)


def store_status() -> dict:
    store = _read_store()
    expires = float(store.get("expires_at", 0)) if store.get("expires_at") else 0
    return {
        "client_configured": client_configured(),
        "has_access_token": bool(store.get("access_token")),
        "has_refresh_token": bool(store.get("refresh_token")),
        "open_id": store.get("open_id"),
        "expires_at": datetime.fromtimestamp(expires, timezone.utc).isoformat() if expires else None,
        "expired": bool(expires) and time.time() > expires,
        "updated_at": store.get("updated_at"),
    }


def _stored_refresh_token() -> str:
    return _read_store().get("refresh_token", "") or settings.tiktok_refresh_token


def _stored_access_token() -> str:
    store = _read_store()
    if store.get("access_token") and not store.get("expired", False):
        expires = float(store.get("expires_at", 0))
        if not expires or time.time() < expires:
            return store["access_token"]
    return settings.tiktok_access_token


# ---------- OAuth flow ----------

def build_authorize_url() -> str:
    state = secrets.token_urlsafe(16)
    code_verifier, code_challenge = _pkce_pair()
    _write_store(_read_store() | {"state": state, "code_verifier": code_verifier})
    params = {
        "client_key": settings.tiktok_client_key,
        "response_type": "code",
        "scope": settings.tiktok_scopes or DEFAULT_SCOPES,
        "redirect_uri": _redirect_uri(),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    from urllib.parse import urlencode
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, state: str) -> dict:
    store = _read_store()
    if store.get("state") and store.get("state") != state:
        return {"success": False, "error": "State mismatch (kemungkinan CSRF). Coba login lagi."}

    if not client_configured():
        return {"success": False, "error": "TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET belum diisi di .env"}

    data = {
        "client_key": settings.tiktok_client_key,
        "client_secret": settings.tiktok_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": _redirect_uri(),
    }
    verifier = store.get("code_verifier")
    if verifier:
        data["code_verifier"] = verifier

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(TOKEN_API, data=data)

    if resp.status_code != 200:
        return {"success": False, "error": f"Exchange failed ({resp.status_code}): {resp.text}"}

    data_resp = resp.json()
    if "access_token" not in data_resp:
        return {"success": False, "error": f"TikTok error: {resp.text}"}

    # code_verifier hanya berlaku sekali pakai
    store.pop("code_verifier", None)
    _write_store(store)

    save_tokens(
        access_token=data_resp["access_token"],
        refresh_token=data_resp.get("refresh_token", ""),
        expires_in=data_resp.get("expires_in", 0),
        open_id=data_resp.get("open_id"),
        scope=data_resp.get("scope"),
    )
    logger.info("TikTok tokens saved.")
    return {"success": True, "open_id": data_resp.get("open_id")}


# ---------- Token management ----------

async def refresh_access_token() -> dict:
    refresh_token = _stored_refresh_token()
    if not refresh_token:
        return {"success": False, "error": "Refresh token tidak ada. Login ulang via /auth/tiktok/login"}

    if not client_configured():
        return {"success": False, "error": "TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET belum diisi"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            TOKEN_API,
            data={
                "client_key": settings.tiktok_client_key,
                "client_secret": settings.tiktok_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )

    if resp.status_code != 200:
        return {"success": False, "error": f"Refresh failed ({resp.status_code}): {resp.text}"}

    data = resp.json()
    if "access_token" not in data:
        return {"success": False, "error": f"TikTok error: {resp.text}"}

    save_tokens(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", refresh_token),
        expires_in=data.get("expires_in", 0),
        open_id=data.get("open_id"),
        scope=data.get("scope"),
    )
    logger.info("TikTok access token refreshed.")
    return {"success": True}


async def get_valid_access_token() -> str | None:
    """Return token yang masih valid; auto-refresh kalau expired."""
    store = _read_store()

    if store.get("access_token"):
        expires = float(store.get("expires_at", 0)) if store.get("expires_at") else 0
        if not expires or time.time() < expires:
            return store["access_token"]

    if settings.tiktok_access_token:
        return settings.tiktok_access_token

    if _stored_refresh_token():
        result = await refresh_access_token()
        if result.get("success"):
            return _read_store().get("access_token")

    return None