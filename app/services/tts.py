"""
Text-to-speech service (GRATIS).

Provider default: edge-tts (Microsoft Edge neural voices, gratis, tanpa API key).
-punya suara Indonesia: id-ID-GadisNeural (cewek), id-ID-ArdiNeural (cowok)
Alternatif: ElevenLabs (berbayar, kalau config ELEVENLABS_API_KEY terisi + TTS_PROVIDER=elevenlabs)

Output: mp3 di data/audio/
"""

import os
import re
import httpx
import logging

from app.config import settings

logger = logging.getLogger(__name__)

AUDIO_DIR = "data/audio"
VIDEO_DIR = "data/videos"

DISCLAIMER_SENTENCE = "Konten ini bukan pengganti nasihat dokter"

# Istilah/asal bahasa Inggris yang sering muncul dari AI, diterjemahkan sebelum dibacakan
# agar suara edge-tts Indonesia tidak terdengar aneh.
_ENGLISH_TO_INDONESIAN = [
    (r"\bbrain\s*fatigue\b", "kelelahan otak"),
    (r"\bmental\s*exhaustion\b", "kelelahan mental"),
    (r"\bmental\s*health\b", "kesehatan mental"),
    (r"\bnge[\s-]*judges?\b", "menghakimi"),
    (r"\bover\s?heat(?:ing|ed|s)?\b", "kepanasan"),
    (r"\bbrain\s*dump\b", "menuangkan isi pikiran"),
    (r"\bdigital\s*detox\b", "jeda dari gawai"),
    (r"\bbestie\b", "sahabat"),
    (r"\bscrolling\b", "menggulir layar"),
    (r"\bscroll(?:s|ed)?\b", "menggulir layar"),
    (r"\breels?\b", "video pendek"),
    (r"\bself[\s-]*care\b", "merawat diri"),
    (r"\bme[\s-]*time\b", "waktu untuk diri sendiri"),
    (r"\bstretching\b", "peregangan"),
    (r"\bstrech\b", "peregangan"),
    (r"\bwork\s?out\b", "olahraga"),
    (r"\bworkout\b", "olahraga"),
    (r"\bversus\b", "atau"),
    (r"\bvs\.?\b", "atau"),
    (r"\bhealth\b", "kesehatan"),
    (r"\bfitness\b", "kebugaran"),
    (r"\bnutrition\b", "nutrisi"),
    (r"\bstress\b", "stres"),
    (r"\btime\s*management\b", "mengatur waktu"),
    (r"\bexercise\b", "olahraga"),
    (r"\bhabit\b", "kebiasaan"),
    (r"\bwellness\b", "kesejahteraan"),
    (r"\bwellbeing\b", "kesejahteraan"),
    (r"\bdaily\b", "harian"),
    (r"\bgood\s*morning\b", "selamat pagi"),
]


def _indonesianize(text: str) -> str:
    """Ganti istilah bahasa Inggris yang umum supaya narasi dibaca natural oleh voice id-ID."""
    for pattern, repl in _ENGLISH_TO_INDONESIAN:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text


def _ensure_dirs():
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(VIDEO_DIR, exist_ok=True)


def strip_disclaimer(script: str) -> str:
    """Hapus kalimat disclaimer dari narasi yang dibacakan (disclaimer tetap tampil visual)."""
    if DISCLAIMER_SENTENCE.lower() in script.lower():
        parts = script.split(DISCLAIMER_SENTENCE, 1)
        return parts[0].strip()
    return script


async def generate_audio(content_id: int, script: str) -> str:
    """Generate narasi mp3 & return path."""
    _ensure_dirs()
    out_path = os.path.join(AUDIO_DIR, f"content_{content_id}.mp3")

    narration = _indonesianize(strip_disclaimer(script))

    if settings.tts_provider == "elevenlabs" and settings.elevenlabs_api_key:
        await _generate_elevenlabs(narration, out_path)
    else:
        await _generate_edge(narration, out_path)
    return out_path


async def _generate_edge(text: str, out_path: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(
        text,
        voice=settings.tts_voice,
        rate=settings.tts_rate,
        pitch=settings.tts_pitch,
    )
    await communicate.save(out_path)
    logger.info(f"TTS (edge-tts) saved: {out_path}")


async def _generate_elevenlabs(text: str, out_path: str) -> None:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"
    headers = {"xi-api-key": settings.elevenlabs_api_key, "Content-Type": "application/json"}
    payload = {"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(resp.content)
    logger.info(f"TTS (elevenlabs) saved: {out_path}")