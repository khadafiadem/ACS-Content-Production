"""
Video assembly service (GRATIS, llocal).

Flow:
1. Render background 1080x1920 via Pillow (hook + script + disclaimer)
2. Compose video pakai ffmpeg: Ken Burns zoom + fade + audio narasi
3. Output: data/videos/content_{id}.mp4 (format TikTok vertical)

Tidak butuh internet / stock video. Template teks di-generate lokal.
"""

import os
import re
import subprocess
import logging

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

from app.config import settings

logger = logging.getLogger(__name__)

VIDEO_DIR = "data/videos"
FONT_BOLD = "C:/Windows/Fonts/arialbd.ttf"
FONT_REGULAR = "C:/Windows/Fonts/arial.ttf"

BORDER_ACS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "border_acs.png")

W, H = 1080, 1920


def get_ffmpeg() -> str:
    return settings.ffmpeg_path if getattr(settings, "ffmpeg_path", "") else imageio_ffmpeg.get_ffmpeg_exe()


def _draw_gradient(draw: ImageDraw.ImageDraw) -> None:
    """Gradient gelap (hijau teh -> navy) khas konten kesehatan (fallback tanpa foto)."""
    top = (13, 148, 136)
    bottom = (23, 37, 84)
    for y in range(H):
        ratio = y / H
        color = tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        draw.line([(0, y), (W, y)], fill=color)


def _cover_resize(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Resize + center-crop agar foto mengisi penuh 1080x1920 (tanpa distorsi)."""
    tw, th = size
    w, h = img.size
    scale = max(tw / w, th / h)
    img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    x = (img.width - tw) // 2
    y = (img.height - th) // 2
    return img.crop((x, y, x + tw, y + th))


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split(" ")
        line = ""
        for word in words:
            test = f"{line} {word}".strip()
            w = draw.textbbox((0, 0), test, font=font)[2]
            if w > max_width and line:
                lines.append(line)
                line = word
            else:
                line = test
        lines.append(line)
    return lines


def _fit_script(
    draw: ImageDraw.ImageDraw, text: str, max_width: int, area_h: int
) -> tuple[int, list[str], int]:
    """Pilih ukuran font terbesar sehingga SELURUH script muat di area yang tersedia."""
    for size in range(44, 26, -1):
        fnt = ImageFont.truetype(FONT_REGULAR, size)
        lines = _wrap_text(draw, text, fnt, max_width)
        line_h = int(size * 1.45)
        if len(lines) * line_h <= area_h:
            return size, lines, line_h
    size = 26
    fnt = ImageFont.truetype(FONT_REGULAR, size)
    return size, _wrap_text(draw, text, fnt, max_width), int(size * 1.45)


M = 36        # jarak bingkai ACS dari tepi video
X = M + 58    # indent teks isi (di dalam bingkai)
MAX_W = W - 2 * X


def render_background(content: dict, out_path: str, bg_source: str | None = None) -> None:
    if bg_source and os.path.exists(bg_source):
        raw = Image.open(bg_source)
        img = _cover_resize(raw, (W, H)).convert("RGB")
        overlay = Image.new("RGBA", (W, H), (6, 12, 28, 160))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    else:
        img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    if not (bg_source and os.path.exists(bg_source)):
        _draw_gradient(draw)

    def font(size: int, bold: bool = True):
        path = FONT_BOLD if bold else FONT_REGULAR
        return ImageFont.truetype(path, size)

    # Branding luar dipegang oleh border_acs.png (logo atas + bar bawah)

    # Hook (atas, besar) - diberi jarak aman dari logo border di atas
    hook_font = font(64)
    hook_lines = _wrap_text(draw, content.hook, hook_font, MAX_W)[:3]
    y = 230
    for line in hook_lines:
        draw.text((X, y), line, font=hook_font, fill=(255, 255, 255))
        y += 78

    # Garis pemisah
    draw.rectangle([X, y + 10, W - X, y + 16], fill=(46, 204, 113))

    # Disclaimer hitung dulu (untuk tahu batas atas area script)
    disc_font = font(36, bold=False)
    disc_lines = _wrap_text(draw, content.disclaimer, disc_font, MAX_W)
    disc_line_h = 48
    disc_bottom = H - 260
    disc_top = disc_bottom - (len(disc_lines) * disc_line_h) - 24

    # Script (tengah) — font disesuaikan agar SELURUH teks muat, tidak terpotong
    script_top = y + 70
    script_area_h = disc_top - script_top - 24
    script_size, script_lines, script_line_h = _fit_script(
        draw, content.script, MAX_W, script_area_h
    )
    script_font = font(script_size, bold=False)
    max_visible = max(script_area_h // script_line_h, 0)
    cy = script_top
    for line in script_lines[:max_visible]:
        draw.text((X, cy), line, font=script_font, fill=(235, 245, 245))
        cy += script_line_h
    if len(script_lines) > max_visible:
        draw.text((X, cy + 4), "...", font=script_font, fill=(120, 230, 220))

    # Disclaimer (bawah, selalu di atas bingkai — jarak aman 260px dari dasar)
    draw.rectangle([X - 34, disc_top, W - X + 34, disc_bottom], fill=(10, 30, 40))
    for line in disc_lines:
        draw.text((X, disc_top + 10), line, font=disc_font, fill=(160, 210, 210))
        disc_top += disc_line_h

    img.save(out_path)


def _parse_audio_duration(ffmpeg: str, audio_path: str) -> float:
    cmd = [ffmpeg, "-i", audio_path, "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stderr = proc.stderr
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", stderr)
    if not match:
        raise RuntimeError(f"Failed to read audio duration: {stderr[-500:]}")
    h, m, s = match.groups()
    return float(h) * 3600 + float(m) * 60 + float(s)


def compose_video(content: dict, audio_path: str, out_path: str, bg_source: str | None = None) -> str:
    ffmpeg = get_ffmpeg()
    bg_path = os.path.join(VIDEO_DIR, f"content_{content.id}_bg.png")
    render_background(content, bg_path, bg_source)

    duration = _parse_audio_duration(ffmpeg, audio_path)
    pad_duration = duration + 1.2  # sedikit jeda di akhir
    fade_out_start = max(pad_duration - 0.9, 1.0)

    has_border = os.path.exists(BORDER_ACS)
    if has_border:
        filter_complex = (
            f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"zoompan=z='min(zoom+0.0014,1.16)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d=1:fps=30:s={W}x{H},"
            f"fade=t=in:st=0:d=0.5,fade=t=out:st={fade_out_start:.2f}:d=0.9[vz];"
            f"[2:v]scale={W}:{H}[bd];"
            f"[vz][bd]overlay=0:0[v]"
        )
    else:
        filter_complex = (
            f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"zoompan=z='min(zoom+0.0014,1.16)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d=1:fps=30:s={W}x{H},"
            f"fade=t=in:st=0:d=0.5,fade=t=out:st={fade_out_start:.2f}:d=0.9[v]"
        )

    cmd = [
        ffmpeg, "-y",
        "-loop", "1", "-framerate", "30", "-i", bg_path,
        "-i", audio_path,
    ]
    if has_border:
        cmd += ["-i", BORDER_ACS]
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-t", f"{pad_duration:.2f}",
        "-movflags", "+faststart",
        out_path,
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr[-1000:]}")

    os.remove(bg_path)
    logger.info(f"Video composed: {out_path} ({pad_duration:.1f}s)")
    return out_path


async def generate_video(content: dict) -> str:
    """Generate audio + video untuk suatu konten. Return path video mp4."""
    os.makedirs(VIDEO_DIR, exist_ok=True)
    from app.services.background import fetch_topic_background
    from app.services.tts import generate_audio, AUDIO_DIR
    audio_path = await generate_audio(content.id, content.script)
    bg_source = await fetch_topic_background(content.topic)
    return compose_video(
        content, audio_path,
        os.path.join(VIDEO_DIR, f"content_{content.id}.mp4"),
        bg_source=bg_source,
    )