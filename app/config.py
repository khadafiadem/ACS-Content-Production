from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # AI Provider
    ai_provider: str = "gemini"  # gemini | ollama | anthropic
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"  # free tier

    # TikTok
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    tiktok_access_token: str = ""
    tiktok_refresh_token: str = ""
    tiktok_redirect_uri: str = ""  # kosong = auto http://localhost:{port}/auth/tiktok/callback
    tiktok_scopes: str = "user.info.basic,video.publish,video.upload"

    # TTS (gratis: edge-tts Microsoft; alternatif: ElevenLabs)
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    tts_provider: str = "edge"  # edge | elevenlabs
    tts_voice: str = "id-ID-GadisNeural"
    tts_rate: str = "-8%"  # kecepatan seimbang: natural tapi tidak melambat berlebihan
    tts_pitch: str = "+2Hz"  # sedikit hangat, kurang monoton

    # Telegram notification
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Scheduler
    schedule_slot_1: str = "10:00"
    schedule_slot_2: str = "19:00"
    publish_sweep_interval: int = 5  # menit: cek konten yang jadwalnya lewat
    timezone: str = "Asia/Jakarta"

    # TikTok publish mode
    auto_publish_public: bool = False
    tiktok_dry_run: bool = False  # true = simulasi upload tanpa TikTok

    # Background image via Pexels (gratis: https://www.pexels.com/api/)
    pexels_api_key: str = ""
    pexels_per_page: int = 1

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./data/contents.db"
    debug: bool = True
    ffmpeg_path: str = ""  # kosong = pakai binary ffmpeg dari imageio-ffmpeg

    # HTTPS (untuk OAuth TikTok dari localhost)
    ssl_enabled: bool = False
    ssl_certfile: str = "certs/localhost-cert.pem"
    ssl_keyfile: str = "certs/localhost-key.pem"


settings = Settings()
