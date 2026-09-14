# ACS Content Production

Sistem otomatis untuk menghasilkan konten kesehatan TikTok menggunakan AI, menjadwalkan, dan mem-publish (draft/otomatis) ke TikTok.

## Tech Stack

| Komponen | Teknologi |
|----------|-----------|
| Backend | Python 3.11+ / FastAPI |
| Database | SQLite + SQLAlchemy (async) |
| Scheduler | APScheduler |
| AI Generator | Google Gemini API (free tier) |
| TikTok | Content Posting API (developers.tiktok.com) |
| Frontend | Jinja2 + Tailwind CSS (server-rendered) |
| Notification | Telegram Bot API (opsional) |
| TTS | edge-tts (gratis, suara neural Indonesia) |
| Video | ffmpeg via imageio-ffmpeg (bundle, tanpa install) + Pillow |

## Quick Start

```bash
# 1. Clone & buat virtual environment
cd ACS-Content-Production
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy & isi .env
cp .env.example .env
# Edit .env → isi minimal GEMINI_API_KEY (gratis dari aistudio.google.com/apikey)

# 4. Jalankan
python run.py
```

Dashboard tersedia di: http://localhost:8000

## API Endpoints

| Method | Endpoint | Fungsi |
|--------|----------|--------|
| GET | `/` | Dashboard |
| GET | `/health` | Health check |
| GET | `/api/contents/` | List semua konten |
| GET | `/api/contents/{id}` | Detail konten |
| POST | `/api/contents/` | Buat konten manual |
| PATCH | `/api/contents/{id}` | Update konten |
| POST | `/api/contents/{id}/approve` | Setujui konten |
| POST | `/api/contents/{id}/reject` | Tolak konten |
| POST | `/api/contents/{id}/publish` | Upload ke TikTok sekarang |
| POST | `/api/generate-now` | Generate konten sekarang |
| POST | `/api/video/{id}/generate` | Buat audio narasi + video mp4 |
| GET | `/api/video/{id}/status` | Cek status audio/video |
| GET | `/api/video/watch/{id}` | Lihat/donwload video |
| GET | `/media/videos/{file}` | Serve file video mp4 |

## Fitur Video (TTS + Assembly)

Tiap konten bisa di-"Generate Video" dari dashboard:

1. **TTS** → narasi mp3 (default `edge-tts`, voice `id-ID-GadisNeural` perempuan Indonesia — gratis tanpa API key)
2. **Background** → Pillow render 1080x1920: gradient tema kesehatan + hook besar + script + disclaimer
3. **Assembly** → ffmpeg: Ken Burns zoom + fade in/out + narasi → mp4 vertical TikTok (± 30-60 detik)

Semua tanpa instalasi ffmpeg manual (binary dibundel imageio-ffmpeg).

Pilihan suara: `id-ID-GadisNeural` (cewek), `id-ID-ArdiNeural` (cowok) → ubah `TTS_VOICE` di .env.
Alternatif: set `TTS_PROVIDER=elevenlabs` + isi `ELEVENLABS_API_KEY` (berbayar).

**Background foto sesuai topik** (opsional): isi `PEXELS_API_KEY` → video otomatis memakai
foto Pexels portrait yang dicari dari topik konten (contoh: "tips tidur" → foto tidur).
Foto di-cache di `data/backgrounds/` (tidak ke-research ulang). Tanpa key/internet →
fallback ke gradient hijau-navy seperti sebelumnya.

Output tersimpan di `data/audio/` dan `data/videos/`.

## Workflow

```
Generate → Review → Scheduled → Published
   │          │
   │          └── Rejected (ditolak)
   │
   └── Draft (otomatis dari scheduler harian)
```

### Alur Kerja:
1. **Scheduler** berjalan setiap hari → generate 2 konten via Gemini AI
2. Konten masuk status `review` → muncul di dashboard
3. User **approve/reject** konten melalui dashboard
4. Konten yang di-approve → status `scheduled` dengan waktu publish yang sudah diatur
5. Pada waktu yang ditentukan → upload ke TikTok (draft/private untuk app unaudited)
6. User dapat **manual publish** dari TikTok app, atau otomatis jika sudah audit disetujui

## Konfigurasi

### Environment Variables

| Variable | Required | Default | Keterangan |
|----------|----------|---------|------------|
| `GEMINI_API_KEY` | Ya | - | API key Gemini (gratis dari Google AI Studio) |
| `GEMINI_MODEL` | Opsional | `gemini-3.5-flash-lite` | Model Gemini free tier |
| `PEXELS_API_KEY` | Opsional | - | Background foto sesuai topik (gratis dari [pexels.com/api](https://www.pexels.com/api/)); kosong = fallback gradient |
| `TIKTOK_CLIENT_KEY` | Untuk TikTok | - | Client key dari TikTok Developers (**app yang dipakai: "App konten dekstop", App ID `7684154418485102612`** — jangan tertukar dengan app "Aplikasi penjadwalan & publish otomatis konten") |
| `TIKTOK_CLIENT_SECRET` | Untuk TikTok | - | Client secret |
| `TIKTOK_ACCESS_TOKEN` | Untuk TikTok | - | OAuth access token |
| `TIKTOK_REFRESH_TOKEN` | Untuk TikTok | - | OAuth refresh token |
| `ELEVENLABS_API_KEY` | Opsional | - | Untuk text-to-speech |
| `ELEVENLABS_VOICE_ID` | Opsional | - | Voice ID ElevenLabs |
| `TELEGRAM_BOT_TOKEN` | Opsional | - | Notifikasi Telegram |
| `TELEGRAM_CHAT_ID` | Opsional | - | Chat ID Telegram |
| `SCHEDULE_SLOT_1` | Opsional | `10:00` | Slot publish pertama |
| `SCHEDULE_SLOT_2` | Opsional | `19:00` | Slot publish kedua |
| `TIMEZONE` | Opsional | `Asia/Jakarta` | Zona waktu |
| `AUTO_PUBLISH_PUBLIC` | Opsional | `false` | `true` = publish publik langsung |
| `APP_PORT` | Opsional | `8000` | Port server |
| `TTS_PROVIDER` | Opsional | `edge` | edge (gratis) / elevenlabs |
| `TTS_VOICE` | Opsional | `id-ID-GadisNeural` | Suara Indonesian edge-tts |
| `FFMPEG_PATH` | Opsional | - | Path ffmpeg custom (default: bundel imageio-ffmpeg) |
| `PUBLISH_SWEEP_INTERVAL` | Opsional | `5` | Menit cek konten due untuk auto-publish |
| `TIKTOK_DRY_RUN` | Opsional | `false` | `true` = tes pipeline tanpa upload sungguhan (ID berprefix `DRYRUN-`) |

## Testing

Semua test tidak butuh API key/Gemini/TikTok asli (AI di-mock + TikTok dry-run):

```bash
pip install -r requirements.txt
pytest tests/ -v
```

Coverage:
- API: health, CRUD konten, approve/reject, 404
- Pipeline publish: dry-run → `published` + `tiktok_post_id`, salah status → ditolak, sweep hanya konten yang jadwalnya lewat
- TTS: disclaimer dihapus dari narasi
- Auth: status token, redirect login saat belum dikonfigurasi

Test menggunakan DB terpisah (`data/test_contents.db`) agar tidak mengganggu data produksi.

### Alur Auto-Publish TikTok

```
Scheduler harian  →  Generate 2 konten (SCHEDULED)
        ↓
Publish sweep (tiap PUBLISH_SWEEP_INTERVAL menit) cek konten due
        ↓
Generate video (kalau belum ada)  →  Upload ke TikTok
        ↓
AUTO_PUBLISH_PUBLIC=false  →  draft (SELF_ONLY) + notif Telegram "siap direview"
AUTO_PUBLISH_PUBLIC=true   →  publish publik langsung
        ↓
Update status: published + tiktok_post_id  |  failed + error_log
```

Jika TikTok belum dikonfigurasi (token kosong), konten tetap `scheduled` (tidak gagal) sampai kredensial diisi.
Manual publish kapan saja via tombol **📤 TikTok** di dashboard atau `POST /api/contents/{id}/publish`.

### TikTok API Setup

1. Daftar di [developers.tiktok.com](https://developers.tiktok.com)
2. Buat aplikasi baru → dapatkan `Client Key` & `Client Secret`
3. Atur `redirect_uri` di Developer Portal persis `http://localhost:8000/auth/tiktok/callback`
4. Buka dashboard → klik **🔗 Hubungkan TikTok** → login → token disimpan otomatis
5. **PENTING**: Aplikasi yang belum diaudit hanya bisa upload sebagai **draft/private** ke akun tester

### OAuth & Token Management (otomatis)

| Endpoint | Fungsi |
|----------|--------|
| `GET /auth/tiktok/login` | Redirect ke halaman login/approve TikTok |
| `GET /auth/tiktok/callback` | Exchange code → simpan access+refresh token |
| `GET /auth/tiktok/status` | Status koneksi TikTok |
| `POST /auth/tiktok/refresh` | Refresh access token manual |
| `POST /auth/tiktok/logout` | Hapus token tersimpan |

- Access token valid ±24 jam → **auto-refresh** saat expired (tokenn rotated)
- Refresh token valid ±365 hari (dirotate setiap refresh)
- Token disimpan di `data/tiktok_tokens.json` (aman, tidak di git)
- Indikator status TikTok ada di navbar dashboard (hijau = siap, kuning = perlu aksi, merah = belum diatur)

### Mode Publish TikTok

| `AUTO_PUBLISH_PUBLIC` | Behavior |
|------------------------|----------|
| `false` (default) | Upload sebagai draft/private → perlu manual publish dari TikTok app |
| `true` | Publish publik langsung → **HANYA setelah audit TikTok disetujui** |

## Catatan Penting

### Keterbatasan TikTok API
- Aplikasi **unaudited** hanya bisa upload draft ke akun yang terdaftar sebagai tester
- Setelah audit disetujui, ubah `AUTO_PUBLISH_PUBLIC=true` untuk publish otomatis ke publik
- Access token perlu di-refresh berkala (sudah di-handle di service)

### Disclaimer Kesehatan
- **SEMUA** konten yang dihasilkan otomatis menyertakan disclaimer:
  > "Konten ini bukan pengganti nasihat dokter atau tenaga medis profesional."
- Review layer wajib sebelum publish → tidak ada konten yang publish tanpa persetujuan

### Audit Trail
- Semua konten tercatat di database dengan status dan timestamp
- Error log tersimpan untuk debugging
- Semua action (generate, approve, reject, publish) tercatat

## Struktur Project

```
ACS-Content-Production/
├── app/
│   ├── main.py              # FastAPI app + lifespan
│   ├── config.py             # Settings dari env vars
│   ├── database.py           # SQLAlchemy + SQLite
│   ├── models.py             # Content model
│   ├── schemas.py            # Pydantic schemas
│   ├── api/
│   │   ├── contents.py       # CRUD endpoints
│   │   ├── video.py          # Video/audio generate endpoints
│   │   ├── auth.py           # TikTok OAuth endpoints
│   │   └── health.py         # Health check
│   ├── services/
│   │   ├── ai_generator.py   # Google Gemini AI integration
│   │   ├── scheduler.py      # APScheduler harian
│   │   ├── tiktok.py         # TikTok Content Posting API
│   │   ├── tiktok_auth.py    # OAuth login + token refresh/store
│   │   ├── tts.py            # Text-to-speech (edge-tts, gratis)
│   │   ├── video_assembly.py # Video composition (ffmpeg + Pillow)
│   │   ├── publisher.py      # Publish worker (video → TikTok → DB)
│   │   └── notification.py   # Telegram notifications
│   └── templates/
│       ├── base.html          # Base template
│       └── dashboard.html     # Dashboard UI
├── static/
├── tests/
├── data/                     # SQLite DB + audio/ + videos/ + tokens (auto-created)
├── .env.example
├── .gitignore
├── requirements.txt
├── run.py
└── README.md
```

## License

Internal - PT Cipta Sehat
