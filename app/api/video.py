import asyncio
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Content
from app.services.tts import AUDIO_DIR
from app.services.video_assembly import VIDEO_DIR

router = APIRouter(prefix="/api/video", tags=["video"])


def _cache_buster(rel_url: str, fs_path: str) -> str:
    """Append ?v=mtime supaya browser tidak menampilkan video lama yang sudah di-replace."""
    if not os.path.exists(fs_path):
        return None
    return f"{rel_url}?v={int(os.path.getmtime(fs_path))}"


@router.get("/{content_id}/status")
async def video_status(content_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    audio_path = os.path.join(AUDIO_DIR, f"content_{content_id}.mp3")
    video_path = os.path.join(VIDEO_DIR, f"content_{content_id}.mp4")
    return {
        "audio_exists": os.path.exists(audio_path),
        "video_exists": os.path.exists(video_path),
        "audio_url": _cache_buster(f"/media/audio/content_{content_id}.mp3", audio_path),
        "video_url": _cache_buster(f"/media/videos/content_{content_id}.mp4", video_path),
    }


@router.post("/{content_id}/generate")
async def generate_video(content_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    video_path = await _build(content)
    rel = f"/media/videos/{os.path.basename(video_path)}"
    return {"success": True, "video_url": _cache_buster(rel, video_path)}


async def _build(content: Content) -> str:
    from app.services.video_assembly import compose_video
    from app.services.background import fetch_topic_background
    from app.services.tts import generate_audio

    audio_path = await generate_audio(content.id, content.script)
    video_path = os.path.join(VIDEO_DIR, f"content_{content.id}.mp4")
    bg_source = await fetch_topic_background(content.topic)
    return compose_video(content, audio_path, video_path, bg_source=bg_source)


@router.get("/watch/{content_id}")
async def watch(content_id: int):
    video_path = os.path.join(VIDEO_DIR, f"content_{content_id}.mp4")
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video belum ada. Generate dulu.")
    return FileResponse(video_path, media_type="video/mp4")


COVER_DIR = "data/covers"


@router.get("/{content_id}/cover")
async def video_cover(content_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    from app.services.video_assembly import render_background
    from app.services.background import fetch_topic_background

    os.makedirs(COVER_DIR, exist_ok=True)
    cover_path = os.path.join(COVER_DIR, f"content_{content_id}.png")
    bg_source = await fetch_topic_background(content.topic)
    render_background(content, cover_path, bg_source=bg_source)
    return FileResponse(
        cover_path,
        media_type="image/png",
        filename=f"cover_{content_id}_tiktok.png",
    )