from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func

from app.config import settings
from app.database import init_db, async_session
from app.models import Content, ContentStatus
from app.api.contents import router as contents_router
from app.api.health import router as health_router
from app.api.video import router as video_router
from app.api.auth import router as auth_router
from app.services.scheduler import setup_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    setup_scheduler()
    yield
    # Shutdown
    shutdown_scheduler()


app = FastAPI(
    title="ACS Content Production",
    description="Health content generator + TikTok scheduler",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="data"), name="media")
templates = Jinja2Templates(directory="app/templates")

app.include_router(health_router)
app.include_router(contents_router)
app.include_router(video_router)
app.include_router(auth_router)


@app.get("/", name="dashboard")
async def dashboard(request: Request):
    async with async_session() as db:
        result = await db.execute(
            select(Content).order_by(Content.created_at.desc())
        )
        contents = result.scalars().all()

        stats = {}
        for status in ContentStatus:
            count_result = await db.execute(
                select(func.count(Content.id)).where(Content.status == status)
            )
            stats[status.value] = count_result.scalar() or 0

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "contents": contents,
            "stats": stats,
        },
    )


LEGAL_PAGE = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | ACS Content Production</title>
<style>
body{{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:0;background:#f4faf7;color:#223;line-height:1.65}}
main{{max-width:760px;margin:0 auto;padding:32px 20px}}
h1{{color:#0d745c}} h2{{color:#0d745c;margin-top:28px}}
.card{{background:#fff;border:1px solid #d9ece4;border-radius:14px;padding:28px}}
.foot{{color:#779;font-size:13px;margin-top:18px}}
</style>
</head>
<body>
<main><div class="card">
{topic}
</div><div class="foot">ACS Content Production - Terakhir diperbarui: 5 September 2026</div></main>
</body></html>
"""


def _legal_html(title: str, topic: str) -> str:
    return LEGAL_PAGE.format(title=title, topic=topic)


@app.get("/terms", name="terms")
async def terms():
    body = """
<h1>Ketentuan Layanan</h1>
<p>Dengan menggunakan aplikasi ACS Content Production ("Aplikasi"), Anda menyetujui ketentuan berikut:</p>
<h2>1. Layanan</h2>
<p>Aplikasi membantu menghasilkan konten edukasi kesehatan dan menjadwalkan unggahan video ke akun TikTok yang Anda otorisasi. Aplikasi tidak memberikan diagnosa medis.</p>
<h2>2. Akun dan Otorisasi</h2>
<p>Anda bertanggung jawab atas kredensial dan akun TikTok yang terhubung. Anda hanya dapat menghubungkan akun yang Anda miliki.</p>
<h2>3. Konten</h2>
<p>Seluruh materi edukasi bersifat informatif. Konten wajib sesuai peraturan kesehatan & obat (BPOM) serta kebijakan platform, termasuk larangan klaim penyembuhan tanpa bukti.</p>
<h2>4. Batasan Tanggung Jawab</h2>
<p>Aplikasi disediakan "apa adanya". Kami tidak bertanggung jawab atas kerugian akibat pemakaian konten yang dihasilkan.</p>
"""
    return HTMLResponse(_legal_html("Ketentuan Layanan", body))


@app.get("/privacy", name="privacy")
async def privacy():
    body = """
<h1>Kebijakan Privasi</h1>
<h2>1. Data yang Dikumpulkan</h2>
<p>Aplikasi menyimpan data konten yang dihasilkan dan token otorisasi TikTok di perangkat/server Anda. Aplikasi tidak menjual data Anda.</p>
<h2>2. Token OAuth</h2>
<p>Token hanya dipakai untuk mengunggah video yang Anda jadwalkan dan dapat dicabut kapan saja melalui halaman dashboard aplikasi.</p>
<h2>3. Penyimpanan</h2>
<p>Data disimpan secara lokal pada server aplikasi Anda. Keamanan bergantung pada perangkat yang Anda jalankan.</p>
<h2>4. Kontak</h2>
<p>Pertanyaan privasi dapat diajukan melalui kanal resmi Cipta Sehat.</p>
"""
    return HTMLResponse(_legal_html("Kebijakan Privasi", body))


@app.post("/api/generate-now")
async def generate_now():
    from app.services.ai_generator import generate_daily_contents

    try:
        contents = await generate_daily_contents(count=2)
        saved_ids = []
        async with async_session() as db:
            from datetime import datetime
            for data in contents:
                content = Content(
                    topic=data.get("topic", ""),
                    hook=data.get("hook", ""),
                    script=data.get("script", ""),
                    caption=data.get("caption", ""),
                    hashtags=data.get("hashtags", ""),
                    visual_notes=data.get("visual_notes", ""),
                    disclaimer=data.get("disclaimer", ""),
                    status=ContentStatus.REVIEW,
                )
                db.add(content)
                await db.flush()
                saved_ids.append(content.id)
            await db.commit()
        return {"success": True, "content_ids": saved_ids, "count": len(saved_ids)}
    except Exception as e:
        return {"success": False, "error": str(e)}
