"""
Background image service (GRATIS) untuk video TikTok.

- Auto-cari foto pexels sesuai topik konten (keyword bahasa Indonesia di-map ke Inggris)
- Download + cache lokal di data/backgrounds/
- Jika tidak ada key / offline / gagal → return None (fallback ke gradient)
- License Pexels: bebas dipakai tanpa atribusi.
"""

import hashlib
import logging
import os
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BG_DIR = "data/backgrounds"
SEARCH_URL = "https://api.pexels.com/v1/search"

_STOPWORDS = {
    "mitos", "fakta", "pake", "pakai", "bikin", "membuat", "sering", "untuk",
    "dengan", "dan", "vs", "atau", "kenapa", "cara", "mau", "agar", "supaya",
    "jangan", "harus", "tidak", "itu", "ini", "anda", "kamu", "kita", "yang",
    "saat", "dari", "pada", "ke", "di", "mengatasi", "seputar", "wajib", "tahan",
    "tentang", "tanpa", "dll", "contoh", "basah", "minum", "tips", "tip", "lagi",
}

_WORD_MAP = {
    "ac": "air conditioner",
    "paru": "lungs",
    "stres": "work stress",
    "stress": "work stress",
    "kerja": "work",
    "brain": "mental",
    "fatigue": "burnout",
    "exhaustion": "burnout",
    "mental": "mental health",
    "es": "iced drink",
    "buncit": "stomach",
    "perut": "stomach",
    "tidur": "sleep",
    "nutrisi": "nutrition",
    "harian": "daily",
    "stretching": "stretching",
    "kantor": "office",
    "kesehatan": "wellness",
    "makanan": "healthy food",
    "sehat": "healthy lifestyle",
    "olahraga": "fitness",
    "air": "water",
    "mata": "eyes",
    "gadget": "screen",
    "laptop": "workspace",
    "rekreasi": "relax",
    "rehat": "relax",
    "istirahat": "rest",
    "vitamin": "vitamins",
    "obat": "medicine",
}


def build_keywords(topic: str, limit: int = 4) -> str:
    """Ubah topik konten (bahasa Indonesia) jadi query Pexels (bahasa Inggris)."""
    topic = (topic or "").lower()
    topic = re.sub(r"[^a-z0-9\s\-]", " ", topic)
    terms = [t.strip(" -") for t in re.split(r"[\s\-+:]+", topic) if t.strip(" -")]
    mapped = []
    for t in terms:
        e = _WORD_MAP.get(t, t)
        if t in _STOPWORDS:
            continue
        if not e or not re.search(r"[a-z]", e):
            continue
        if not any(e in m or m in e for m in mapped):
            mapped.append(e)
    if not mapped:
        mapped = ["healthy lifestyle"]
    return " ".join(mapped[:limit])


def _cache_path(query: str) -> str:
    h = hashlib.md5(query.encode()).hexdigest()[:12]
    return os.path.join(BG_DIR, f"{h}.jpg")


async def fetch_topic_background(topic: str) -> str | None:
    """Cari + download background foto Pexels untuk topik. Return path file, atau None."""
    if not settings.pexels_api_key:
        return None

    os.makedirs(BG_DIR, exist_ok=True)
    query = build_keywords(topic)
    cached = _cache_path(query)
    if os.path.exists(cached) and os.path.getsize(cached) > 0:
        return cached

    headers = {"Authorization": settings.pexels_api_key}
    params = {
        "query": query,
        "per_page": settings.pexels_per_page,
        "orientation": "portrait",
        "size": "medium",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(SEARCH_URL, params=params, headers=headers)
            r.raise_for_status()
            photos = r.json().get("photos", [])
            if not photos:
                logger.warning("Pexels: tidak ada foto untuk query '%s'", query)
                return None
            src = photos[0].get("src", {})
            img_url = src.get("large2x") or src.get("large") or src.get("medium")
            if not img_url:
                return None
            img = await client.get(img_url, timeout=60.0)
            img.raise_for_status()
            with open(cached, "wb") as f:
                f.write(img.content)
            logger.info("Pexels: background '%s' -> %s", query, cached)
            return cached
    except Exception as e:
        logger.warning("Pexels gagal: %s", e)
        return None