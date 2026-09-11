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
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Step 1: Init upload
            init_resp = await client.post(
                f"{TIKTOK_BASE_URL}/post/publish/video/init/",
                headers=headers,
                json={
                    "post_info": {
                        "title": caption[:150],
                        "privacy_level": privacy_level,
                        "disable_duet": False,
                        "disable_comment": False,
                        "disable_stitch": False,
                    },
                    "source_info": {
                        "source": "FILE_UPLOAD",
                        "video_size": _file_size(video_path),
                    },
                },
            )

            if init_resp.status_code != 200:
                return {"success": False, "error": f"Init failed ({init_resp.status_code}): {init_resp.text}"}

            init_data = init_resp.json()
            if init_data.get("error"):
                return {"success": False, "error": f"TikTok error: {init_data['error'].get('message', init_data)}"}

            upload_url = init_data.get("data", {}).get("upload_url")
            publish_id = init_data.get("data", {}).get("publish_id")

            if not upload_url:
                return {"success": False, "error": "No upload URL returned"}

            # Step 2: Upload video file (direct POST ke upload_url)
            with open(video_path, "rb") as f:
                upload_resp = await client.post(
                    upload_url,
                    data=f.read(),
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Length": str(_file_size(video_path)),
                    },
                )

            if upload_resp.status_code in (200, 201):
                return {"success": True, "publish_id": publish_id}
            else:
                return {"success": False, "error": f"Upload failed ({upload_resp.status_code}): {upload_resp.text}"}

    except Exception as e:
        logger.error(f"TikTok upload error: {e}")
        return {"success": False, "error": str(e)}


def _file_size(path: str) -> int:
    import os
    return os.path.getsize(path)