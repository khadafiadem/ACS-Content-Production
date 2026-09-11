"""
Notification service: Telegram & Email (stub).
Digirim saat draft TikTok siap direview.
"""

import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)


async def send_telegram(message: str) -> bool:
    """Kirim notifikasi via Telegram bot."""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.info("Telegram not configured, skipping notification")
        return False

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={
                    "chat_id": settings.telegram_chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
            )
            if resp.status_code == 200:
                logger.info("Telegram notification sent")
                return True
            else:
                logger.error(f"Telegram send failed: {resp.text}")
                return False
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False


async def notify_draft_ready(topic: str, content_id: int) -> None:
    """Notifikasi bahwa draft konten siap untuk review."""
    message = (
        f"🟢 <b>Draft Konten Siap</b>\n\n"
        f"📌 Topik: {topic}\n"
        f"🆔 ID: {content_id}\n\n"
        f"Buka dashboard untuk review:\nhttp://localhost:8000/"
    )
    await send_telegram(message)
