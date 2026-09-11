import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models import Content, ContentStatus
from app.services.ai_generator import generate_daily_contents
from app.services.publisher import publish_due_contents

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.timezone)


async def generate_and_schedule_job():
    """Generate 2 konten baru & schedule ke slot waktu yang sudah dikonfigurasi."""
    logger.info("Running daily content generation job...")
    try:
        contents = await generate_daily_contents(count=2)
        now = datetime.now()

        slot1_h, slot1_m = map(int, settings.schedule_slot_1.split(":"))
        slot2_h, slot2_m = map(int, settings.schedule_slot_2.split(":"))

        schedules = [
            now.replace(hour=slot1_h, minute=slot1_m, second=0, microsecond=0),
            now.replace(hour=slot2_h, minute=slot2_m, second=0, microsecond=0),
        ]

        async with async_session() as db:
            for i, data in enumerate(contents):
                sched_at = schedules[i] if i < len(schedules) else schedules[-1]
                if sched_at <= now:
                    sched_at = now.replace(hour=0, minute=0, second=0) + timedelta(days=1)

                content = Content(
                    topic=data.get("topic", ""),
                    hook=data.get("hook", ""),
                    script=data.get("script", ""),
                    caption=data.get("caption", ""),
                    hashtags=data.get("hashtags", ""),
                    visual_notes=data.get("visual_notes", ""),
                    disclaimer=data.get("disclaimer", ""),
                    status=ContentStatus.SCHEDULED,
                    scheduled_at=sched_at,
                )
                db.add(content)
                logger.info(f"Scheduled content #{i+1}: {data.get('topic')} at {sched_at}")

            await db.commit()
        logger.info("Daily content generation completed.")
    except Exception as e:
        logger.error(f"Content generation job failed: {e}")


def setup_scheduler():
    if scheduler.running:
        return
    slot1_h, slot1_m = map(int, settings.schedule_slot_1.split(":"))
    slot2_h, slot2_m = map(int, settings.schedule_slot_2.split(":"))

    scheduler.add_job(
        generate_and_schedule_job,
        CronTrigger(hour=slot1_h, minute=slot1_m),
        id="daily_content_generator",
        replace_existing=True,
        name="Generate daily health contents",
    )
    scheduler.add_job(
        publish_due_contents,
        IntervalTrigger(minutes=settings.publish_sweep_interval),
        id="publish_due_contents",
        replace_existing=True,
        name="Publish due TikTok contents",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        f"Scheduler started. Daily generation at {settings.schedule_slot_1} & {settings.schedule_slot_2}; publish sweep every {settings.publish_sweep_interval} min"
    )


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
