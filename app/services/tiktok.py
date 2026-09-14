"""
TikTok Content Posting API integration.

Status: UNAUDITED APP
- Hanya bisa upload draft/private ke akun tester
- Setelah audit disetujui + AUTO_PUBLISH_PUBLIC=true, baru bisa publish publik

Token: dikelola otomatis oleh tiktok_auth (exchange code, refresh, rotate).
"""

import httpx
import logging
import time
from urllib.parse import urlparse

from app.config import settings
from app.services.tiktok_auth import get_valid_access_token

logger = logging.getLogger(__name__)

TIKTOK_BASE_URL = "https://open.tiktokapis.com/v2"


async def upload_video(
    video_path: str,
    caption: str,
    privacy_level: str = "SELF_ONLY",
) -> dict:
    """
    Upload video ke TikTok via Content Posting API (auto-refresh token).

    Args:
        video_path: path ke file video
        caption: caption video
        privacy_level: SELF_ONLY (draft), FRIENDS_ONLY, PUBLIC_TO_EVERYONE

    Returns:
        dict dengan status dan tiktok_post_id atau error
    """
    if settings.tiktok_dry_run:
        logger.info("DRY RUN: simulasi upload TikTok (tanpa kredensial)")
        return {"success": True, "publish_id": f"DRYRUN-{int(time.time())}", "dry_run": True}

    token = await get_valid_access_token()
    if not token:
        return {"success": False, "error": "TikTok token tidak tersedia. Hubungkan via /auth/tiktok/login"}

    # Override privacy berdasarkan AUTO_PUBLISH_PUBLIC flag
    if settings.auto_publish_public:
        privacy_level = "PUBLIC_TO_EVERYONE"
    else:
        privacy_level = "SELF_ONLY"

    headers = {"Authorization": f"Bearer {token}"}

    try:
        size = _file_size(video_path)
        chunk_size = min(size, 10 * 1024 * 1024)
        total_chunk_count = max(1, size // chunk_size)

        async with httpx.AsyncClient(timeout=120.0) as client:
            # Step 1: Init upload
            init_resp = await client.post(
                f"{TIKTOK_BASE_URL}/post/publish/video/init/",
                headers={**headers, "Content-Type": "application/json; charset=UTF-8"},
                json={
                    "post_info": {
                        "title": caption[:150],
                        "privacy_level": privacy_level,
                        "video_cover_timestamp_ms": 0,
                        "disable_duet": False,
                        "disable_comment": False,
                        "disable_stitch": False,
                    },
                    "source_info": {
                        "source": "FILE_UPLOAD",
                        "video_size": size,
                        "chunk_size": chunk_size,
                        "total_chunk_count": total_chunk_count,
                    },
                },
            )

            if init_resp.status_code != 200:
                return {"success": False, "error": f"Init failed ({init_resp.status_code}): {init_resp.text}"}

            init_data = init_resp.json()
            if init_data.get("error") and init_data["error"].get("code") not in (None, "", "ok"):
                code = init_data["error"].get("code")
                msg = init_data["error"].get("message", init_data)
                return {"success": False, "error": f"TikTok error [{code}]: {msg}", "code": code}

            upload_url = init_data.get("data", {}).get("upload_url")
            publish_id = init_data.get("data", {}).get("publish_id")

            if not upload_url:
                return {"success": False, "error": "No upload URL returned"}

            # Step 2: Upload video file (PUT chunked + Content-Range)
            code, text = await _upload_chunks(client, upload_url, video_path, size)
            if code:
                return {"success": False, "error": f"Upload failed ({code}): {text}"}

            return {"success": True, "publish_id": publish_id, "mode": "direct"}

    except Exception as e:
        logger.error(f"TikTok upload error: {e}")
        return {"success": False, "error": str(e)}


async def upload_draft(video_path: str) -> dict:
    """
    Push video ke Inbox/Draft TikTok (sandbox-friendly).
    Caption tidak bisa otomatis (harus diisi manual di aplikasi TikTok).
    Hanya butuh scope video.upload.
    """
    if settings.tiktok_dry_run:
        return {"success": True, "publish_id": f"DRYRUN-{int(time.time())}", "dry_run": True, "mode": "draft"}

    token = await get_valid_access_token()
    if not token:
        return {"success": False, "error": "TikTok token tidak tersedia. Hubungkan via /auth/tiktok/login", "mode": "draft"}

    headers = {"Authorization": f"Bearer {token}"}

    try:
        size = _file_size(video_path)
        chunk_size = min(size, 10 * 1024 * 1024)
        total_chunk_count = max(1, size // chunk_size)

        async with httpx.AsyncClient(timeout=120.0) as client:
            init_resp = await client.post(
                f"{TIKTOK_BASE_URL}/post/publish/inbox/video/init/",
                headers={**headers, "Content-Type": "application/json; charset=UTF-8"},
                json={
                    "source_info": {
                        "source": "FILE_UPLOAD",
                        "video_size": size,
                        "chunk_size": chunk_size,
                        "total_chunk_count": total_chunk_count,
                    }
                },
            )

            if init_resp.status_code != 200:
                return {"success": False, "error": f"Init failed ({init_resp.status_code}): {init_resp.text}", "mode": "draft"}

            init_data = init_resp.json()
            if init_data.get("error") and init_data["error"].get("code") not in (None, "", "ok"):
                code = init_data["error"].get("code")
                msg = init_data["error"].get("message", init_data)
                return {"success": False, "error": f"TikTok error [{code}]: {msg}", "mode": "draft", "code": code}

            upload_url = init_data.get("data", {}).get("upload_url")
            publish_id = init_data.get("data", {}).get("publish_id")

            if not upload_url:
                return {"success": False, "error": "No upload URL returned", "mode": "draft"}

            code, text = await _upload_chunks(client, upload_url, video_path, size)
            if code:
                return {"success": False, "error": f"Upload failed ({code}): {text}", "mode": "draft"}

            return {"success": True, "publish_id": publish_id, "mode": "draft"}

    except Exception as e:
        logger.error(f"TikTok draft upload error: {e}")
        return {"success": False, "error": str(e), "mode": "draft"}


async def _upload_chunks(client, upload_url: str, video_path: str, size: int):
    """Upload file via PUT chunked + Content-Range. Return (None, None) jika sukses."""
    chunk_size = min(size, 10 * 1024 * 1024)
    with open(video_path, "rb") as f:
        off = 0
        while off < size:
            end = min(size, off + chunk_size) - 1
            f.seek(off)
            body = f.read(end - off + 1)
            up_resp = await client.put(
                upload_url,
                content=body,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(body)),
                    "Content-Range": f"bytes {off}-{end}/{size}",
                },
            )
            if up_resp.status_code not in (200, 201, 206):
                return up_resp.status_code, up_resp.text
            off = end + 1
    return None, None


def _file_size(path: str) -> int:
    import os
    return os.path.getsize(path)