"""
Publisher worker: generate video -> upload ke TikTok (draft) -> update status.

Alur:
1. Konten status=scheduled & jadwalnya tiba (dipanggil scheduler/endpoint)
2. Generate video (audio + assembly) kalau belum ada
3. Upload ke TikTok sebagai draft/private (unaudited app) atau publik (jika audited)
4. Update status: published + tiktok_post_id | failed + error_log
5. Kirim notifikasi Telegram (opsional) draft siap direview
"""

import os
import logging
from datetime import datetime

from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models import Content, ContentStatus
from app.services.tiktok import upload_video
from app.services.video_assembly import VIDEO_DIR
from app.services.notification import notify_draft_ready

logger = logging.getLogger(__name__)


def tiktok_configured() -> bool:
    if settings.tiktok_dry_run:
        return True
    from app.services.tiktok_auth import store_status
    return store_status()["client_configured"] and (
        bool(settings.tiktok_access_token)
        or store_status()["has_access_token"]
        or store_status()["has_refresh_token"]
    )


async def _ensure_video(content: Content) -> str:
    """Generate video kalau belum ada. Return path ke mp4."""
    video_path = os.path.join(VIDEO_DIR, f"content_{content.id}.mp4")
    if settings.tiktok_dry_run:
        return video_path  # dry-run: tidak perlu video sungguhan
    if os.path.exists(video_path):
        return video_path

    from app.services.video_assembly import generate_video as build_video
    return await build_video(content)


async def publish_content(content_id: int, force: bool = False) -> dict:
    logger.info(f"Publishing content #{content_id} (force={force})...")
    async with async_session() as db:
        result = await db.execute(select(Content).where(Content.id == content_id))
        content = result.scalar_one_or_none()
        if not content:
            return {"success": False, "error": "Content not found", "id": content_id}

        if not force and content.status not in (ContentStatus.SCHEDULED, ContentStatus.PUBLISHED):
            return {"success": False, "error": f"Status {content.status.value} tidak bisa dipublish (harus scheduled)", "id": content_id}

    try:
        video_path = await _ensure_video(content)
        caption = f"{content.caption}\n\n{content.hashtags}"

        if not tiktok_configured():
            detail = "TikTok belum dikonfigurasi (TIKTOK_ACCESS_TOKEN kosong). Isi .env untuk aktifkan upload."
            logger.warning(detail)
            return {"success": False, "error": detail, "id": content_id}

        result = await upload_video(video_path, caption)

        async with async_session() as db:
            content = (await db.execute(select(Content).where(Content.id == content_id))).scalar_one_or_none()
            if not content:
                return {"success": False, "error": "Content not found", "id": content_id}

            if result.get("success"):
                content.status = ContentStatus.PUBLISHED
                content.published_at = datetime.now()
                content.tiktok_post_id = result.get("publish_id", "")
                content.error_log = None
                await db.commit()
                mode = "publik" if settings.auto_publish_public else "draft"
                await notify_draft_ready(content.topic, content.id)
                logger.info(f"Content #{content_id} published ({mode}). publish_id={result.get('publish_id')}")
                return {"success": True, "mode": mode, "publish_id": result.get("publish_id"), "id": content_id}
            else:
                content.status = ContentStatus.FAILED
                content.error_log = result.get("error", "Unknown TikTok error")
                await db.commit()
                logger.error(f"Content #{content_id} publish failed: {content.error_log}")
                return {"success": False, "error": content.error_log, "id": content_id}

    except Exception as e:
        logger.error(f"Publish content #{content_id} error: {e}")
        async with async_session() as db:
            content = (await db.execute(select(Content).where(Content.id == content_id))).scalar_one_or_none()
            if content:
                content.status = ContentStatus.FAILED
                content.error_log = str(e)
                await db.commit()
        return {"success": False, "error": str(e), "id": content_id}


async def publish_due_contents() -> dict:
    """Cari konten scheduled yang jadwalnya sudah lewat & publish."""
    now = datetime.now()
    async with async_session() as db:
        result = await db.execute(
            select(Content).where(
                Content.status == ContentStatus.SCHEDULED,
                Content.scheduled_at <= now,
            )
        )
        due = result.scalars().all()
        ids = [c.id for c in due]

    summary = []
    for cid in ids:
        summary.append(await publish_content(cid))
    logger.info(f"Publish sweep: {len(ids)} content due")
    return {"processed": len(ids), "results": summary}