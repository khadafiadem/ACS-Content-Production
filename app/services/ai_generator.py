import json
from google import genai
from google.genai import types

from app.config import settings

client = genai.Client(api_key=settings.gemini_api_key)

SYSTEM_PROMPT = """\
Kamu adalah penulis konten kesehatan untuk TikTok yang ditujukan untuk audiens umum Indonesia.
Ketentuan MUTLAK:
1. Setiap konten HARUS menyertakan disclaimer: "Konten ini bukan pengganti nasihat dokter atau tenaga medis profesional. Konsultasikan kondisi Anda ke tenaga medis."
2. Jangan membuat klaim medis yang tidak berdasar atau menyesatkan.
3. Gaya bahasa: santai, mudah dipahami orang awam, gunakan bahasa Indonesia sehari-hari.
4. Topik harus bermanfaat dan aman (nutrisi, kebugaran, kesehatan mental, mitos vs fakta, tips harian).
5. JANGAN memberikan diagnosis, resep obat, atau pengobatan spesifik.
6. VARIASI ANTI-HOMOGEN: setiap konten wajib UNIK dalam pilihan kata dan struktur kalimat.
   - Jangan membuka dengan frasa yang sama (misal jangan semuanya "Halo teman-teman, pernahkah...").
   - Variasikan gaya pembukaan, diksi, analogi, dan penutup antar konten.
   - Hindari mengulang kalimat atau frasa yang identik antara konten yang satu dengan yang lain, maupun dengan konten yang pernah dibuat sebelumnya.
7. BAHASA MURNI INDONESIA: narasi ("script") HARUS 100% bahasa Indonesia sehari-hari.
   - Terjemahkan semua istilah asing ke bahasa Indonesia, contoh: "brain fatigue" → "kelelahan otak", "stretching" → "peregangan", "vs" → "atau", "workout" → "olahraga", "stress" → "stres", "time management" → "mengatur waktu".
   - JANGAN menulis kata bahasa Inggris di dalam script, termasuk pada topik dan hook.
   - Hindari simbol/angka yang aneh saat dibacakan suara (misal tulis "seratus persen" bukan "100%").
"""

TOPIC_SUGGESTIONS = """\
Suggest 2 topik kesehatan yang menarik dan relevan untuk audiens Indonesia hari ini.
Format JSON array: [{"topic": "...", "hook": "..."}]

Contoh topik: nutrisi harian, mitos atau fakta medis, tips tidur, manfaat jalan kaki, kesehatan mental, stres kerja, minum air putih, peregangan kantor.

Tulis topik dan hook DALAM BAHASA INDONESIA MURNI (jangan gunakan kata bahasa Inggris seperti "stretching", "health", "vs").

HANYA output JSON array, tanpa teks tambahan.
"""

CONTENT_TEMPLATE = """\
Buat konten TikTok kesehatan dengan topik berikut:
Topik: {topic}
Hook: {hook}

Output JSON dengan format:
{{
  "topic": "judul topik",
  "hook": "kalimat pembuka 3 detik pertama video",
  "script": "narasi lengkap 30-60 detik",
  "caption": "caption untuk TikTok",
  "hashtags": "hashtag dipisah spasi",
  "visual_notes": "saran visual/b-roll per adegan",
  "disclaimer": "disclaimer kesehatan (wajib ada)"
}}

HANYA output JSON, tanpa teks tambahan.
"""


async def _generate(prompt: str, system: str, max_tokens: int = 2048) -> dict | list:
    response = await client.aio.models.generate_content(
        model=settings.gemini_model,
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            max_output_tokens=max_tokens,
        ),
        contents=prompt,
    )
    text = response.text.strip()
    return json.loads(text)


async def generate_topics(exclude: list[str] | None = None) -> list[dict]:
    prompt = TOPIC_SUGGESTIONS
    if exclude:
        prompt += (
            "\n\nJANGAN pilih topik atau hook yang sudah pernah dipakai sebelumnya "
            "(jangan mengulang maupun terlalu mirip dengan daftar berikut):\n"
            + "\n".join(f"- {e}" for e in exclude)
        )
    return await _generate(prompt, "Kamu adalah content planner untuk konten kesehatan TikTok.", max_tokens=512)


async def generate_content(topic: str, hook: str) -> dict:
    prompt = CONTENT_TEMPLATE.format(topic=topic, hook=hook)
    return await _generate(prompt, SYSTEM_PROMPT)


async def generate_daily_contents(count: int = 2) -> list[dict]:
    from sqlalchemy import select

    from app.database import async_session
    from app.models import Content

    async with async_session() as db:
        result = await db.execute(
            select(Content.topic, Content.hook).order_by(Content.created_at.desc()).limit(40)
        )
        exclude = [f"{topic} | {hook}" for topic, hook in result.all()]

    topics = await generate_topics(exclude)
    results = []
    for t in topics[:count]:
        content = await generate_content(t["topic"], t["hook"])
        results.append(content)
    return results
