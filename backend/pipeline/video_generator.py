import asyncio
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import edge_tts
from PIL import Image, ImageDraw, ImageFont
from pipeline.llm_client import get_client, get_model, make_llm_kwargs
from pipeline.context_manager import max_content_chars

SLIDE_W, SLIDE_H = 1920, 1080
BG_COLOR = (15, 20, 40)
TITLE_COLOR = (100, 200, 255)
TEXT_COLOR = (220, 230, 245)
ACCENT_COLOR = (60, 120, 220)
PROGRESS_BG = (30, 40, 70)

# edge-tts voice (used first if online)
EDGE_VOICE = "en-US-AriaNeural"

# macOS neural voices tried in order — Zoe Premium is the most natural
MACOS_VOICES = ["Zoe (Premium)", "Ava (Premium)", "Evan (Premium)", "Samantha"]


def _ffmpeg() -> str:
    """Return the ffmpeg executable path, searching Homebrew locations."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    for candidate in ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"]:
        if Path(candidate).exists():
            return candidate
    raise FileNotFoundError("ffmpeg not found — install with: brew install ffmpeg")


def _ffprobe() -> str:
    path = shutil.which("ffprobe")
    if path:
        return path
    for candidate in ["/opt/homebrew/bin/ffprobe", "/usr/local/bin/ffprobe", "/usr/bin/ffprobe"]:
        if Path(candidate).exists():
            return candidate
    raise FileNotFoundError("ffprobe not found — install with: brew install ffmpeg")

SCRIPT_SYSTEM = """You output ONLY raw JSON. No prose, no markdown, no explanation.

Output a JSON object that exactly follows this schema:
{"slides":[{"type":"title","title":"...","content":["..."],"narration":"..."},{"type":"content","title":"...","content":["• point"],"narration":"..."}]}

Rules:
- 5 to 8 slides total
- First slide: type "title" with a subtitle in content array
- Remaining slides: type "content" with 3-5 bullet points starting with "• "
- narration: natural spoken text for that slide (15-30 seconds of speech)
- Cover introduction, core concepts, key findings, applications, conclusion
- YOUR ENTIRE RESPONSE MUST BE VALID JSON STARTING WITH { AND ENDING WITH }

CRITICAL: Every bullet point and ALL narration text MUST use SPECIFIC information from the provided content.
Use real names, actual numbers, real findings, direct terminology, and genuine quotes from the source.
Do NOT write generic descriptions like "overview of the topic", "the author discusses", "key findings are explored".
Write the ACTUAL specific concepts, names, results, and insights present in the content."""


def _get_font(size: int, bold: bool = False):
    font_names = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            # Catches IOError, OSError, and ImportError (_imagingft missing on some builds)
            continue
    # load_default supports size= in Pillow >= 10.1
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    try:
        return draw.textbbox((0, 0), text, font=font)[2]
    except Exception:
        return len(text) * 10  # rough fallback: ~10px per char


def _wrap_text(text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    for word in words:
        test = (current + " " + word).strip()
        if _text_width(draw, test, font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def create_slide(slide: dict, index: int, total: int) -> Image.Image:
    img = Image.new("RGB", (SLIDE_W, SLIDE_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    draw.rectangle([(0, 0), (SLIDE_W, 6)], fill=ACCENT_COLOR)

    bar_y = SLIDE_H - 30
    draw.rectangle([(0, bar_y), (SLIDE_W, SLIDE_H)], fill=PROGRESS_BG)
    progress_w = int(SLIDE_W * (index + 1) / total)
    draw.rectangle([(0, bar_y), (progress_w, SLIDE_H)], fill=ACCENT_COLOR)

    num_font = _get_font(24)
    draw.text((SLIDE_W - 100, bar_y + 4), f"{index + 1}/{total}", font=num_font, fill=TEXT_COLOR)

    title = slide.get("title", "")
    content_lines = slide.get("content", [])
    slide_type = slide.get("type", "content")

    if slide_type == "title":
        title_font = _get_font(80, bold=True)
        sub_font = _get_font(42)
        bbox = draw.textbbox((0, 0), title, font=title_font)
        tw = bbox[2] - bbox[0]
        tx = (SLIDE_W - tw) // 2
        ty = 340
        draw.text((tx, ty), title, font=title_font, fill=TITLE_COLOR)
        draw.rectangle([(SLIDE_W // 2 - 200, ty + 110), (SLIDE_W // 2 + 200, ty + 116)], fill=ACCENT_COLOR)
        if content_lines:
            sub_text = content_lines[0]
            bbox2 = draw.textbbox((0, 0), sub_text, font=sub_font)
            sw = bbox2[2] - bbox2[0]
            draw.text(((SLIDE_W - sw) // 2, ty + 140), sub_text, font=sub_font, fill=TEXT_COLOR)
    else:
        title_font = _get_font(60, bold=True)
        body_font = _get_font(38)
        wrapped_title = _wrap_text(title, title_font, SLIDE_W - 160)
        ty = 80
        for line in wrapped_title[:2]:
            draw.text((80, ty), line, font=title_font, fill=TITLE_COLOR)
            bbox = draw.textbbox((0, 0), line, font=title_font)
            ty += bbox[3] - bbox[1] + 10
        draw.rectangle([(80, ty + 10), (80 + 600, ty + 14)], fill=ACCENT_COLOR)
        ty += 50
        for line in content_lines:
            wrapped = _wrap_text(line, body_font, SLIDE_W - 160)
            for wl in wrapped:
                if ty + 50 > SLIDE_H - 80:
                    break
                draw.text((80, ty), wl, font=body_font, fill=TEXT_COLOR)
                bbox = draw.textbbox((0, 0), wl, font=body_font)
                ty += bbox[3] - bbox[1] + 16
            ty += 8

    return img


def _tts_macos_say(text: str, output_path: Path, voice: str = "Zoe (Premium)") -> None:
    """macOS built-in TTS via `say`."""
    aiff_path = output_path.with_suffix(".aiff")
    subprocess.run(
        ["say", "-v", voice, "-o", str(aiff_path), text],
        check=True, capture_output=True, timeout=60,
    )
    subprocess.run(
        [_ffmpeg(), "-y", "-i", str(aiff_path), str(output_path)],
        check=True, capture_output=True, timeout=30,
    )
    aiff_path.unlink(missing_ok=True)


def _tts_silence(output_path: Path, duration: float = 5.0) -> None:
    """Generate a silent audio file as a last-resort fallback."""
    subprocess.run(
        [
            _ffmpeg(), "-y",
            "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
            "-t", str(duration),
            str(output_path),
        ],
        check=True, capture_output=True, timeout=30,
    )


async def text_to_speech(text: str, output_path: Path) -> None:
    # Attempt 1 — edge-tts (online, natural neural voice)
    try:
        communicate = edge_tts.Communicate(text, EDGE_VOICE)
        await communicate.save(str(output_path))
        return
    except Exception:
        pass

    # Attempt 2 — macOS neural/premium voices (offline, natural)
    for voice in MACOS_VOICES:
        try:
            await asyncio.to_thread(_tts_macos_say, text, output_path, voice)
            return
        except Exception:
            continue

    # Attempt 3 — silent audio so the video pipeline never crashes
    await asyncio.to_thread(_tts_silence, output_path)


def get_audio_duration(audio_path: Path) -> float:
    result = subprocess.run(
        [
            _ffprobe(), "-v", "quiet", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path),
        ],
        capture_output=True, text=True, timeout=30,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 5.0


def create_video_segment(slide_path: Path, audio_path: Path, output_path: Path, duration: float) -> None:
    subprocess.run(
        [
            _ffmpeg(), "-y",
            "-loop", "1", "-i", str(slide_path),
            "-i", str(audio_path),
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "128k",
            "-t", str(duration + 0.5),
            "-pix_fmt", "yuv420p",
            "-vf", f"scale={SLIDE_W}:{SLIDE_H}",
            str(output_path),
        ],
        check=True, capture_output=True, timeout=120,
    )


def concat_segments(segment_paths: list[Path], output_path: Path) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for p in segment_paths:
            f.write(f"file '{p.resolve()}'\n")
        concat_file = Path(f.name)

    subprocess.run(
        [
            _ffmpeg(), "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(output_path),
        ],
        check=True, capture_output=True, timeout=300,
    )
    concat_file.unlink(missing_ok=True)


def _build_fallback_slides(title: str, content: str) -> list[dict]:
    """Build a minimal slide deck from raw content when the model refuses JSON."""
    paras = [p.strip() for p in re.split(r'\n{2,}', content) if len(p.strip()) > 60][:20]
    section_titles = ["Introduction", "Core Concepts", "Key Findings", "Applications", "Conclusion"]
    slides: list[dict] = [
        {
            "type": "title",
            "title": title[:70],
            "content": ["An in-depth analysis"],
            "narration": f"Welcome. Today we explore: {title[:120]}.",
        }
    ]
    chunk = max(1, len(paras) // 5)
    for i, section in enumerate(section_titles):
        block = paras[i * chunk: (i + 1) * chunk]
        text = " ".join(block)[:400] if block else f"Details about {section.lower()}."
        bullets = [f"• {s.strip()}" for s in re.split(r'[.!?]', text) if len(s.strip()) > 20][:4]
        if not bullets:
            bullets = [f"• {text[:120]}"]
        slides.append({
            "type": "content",
            "title": section,
            "content": bullets,
            "narration": text[:250],
        })
    return slides


def _parse_script(raw: str) -> list[dict]:
    """Try multiple strategies to extract slides from a model response."""
    # Strip markdown fences
    cleaned = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r'\s*```$', '', cleaned.strip(), flags=re.MULTILINE)

    # Attempt 1: direct parse
    try:
        return json.loads(cleaned).get("slides", [])
    except (json.JSONDecodeError, AttributeError):
        pass

    # Attempt 2: find the outermost JSON object
    m = re.search(r'\{[\s\S]*\}', cleaned)
    if m:
        try:
            return json.loads(m.group(0)).get("slides", [])
        except (json.JSONDecodeError, AttributeError):
            pass

    # Attempt 3: model started mid-object (prefill was consumed) — wrap it
    try:
        return json.loads('{"slides":[' + cleaned).get("slides", [])
    except (json.JSONDecodeError, AttributeError):
        pass

    return []


async def generate_video(content: str, title: str, url_type: str, output_dir: Path, job_id: str, article: str = "") -> Path:
    # Use the article (complete content synthesis) as the video script source.
    # Fall back to raw content if no article is available.
    src_chars = max_content_chars(get_model(), prompt_tokens=600, output_tokens=800)
    source = (article.strip() or content)[:src_chars]

    user_msg = (
        f"Title: {title}\n\nContent:\n{source}\n\n"
        "Output the JSON slide script now. Start your response with { and end with }."
    )
    base_messages = [
        {"role": "system", "content": SCRIPT_SYSTEM},
        {"role": "user", "content": user_msg},
    ]

    slides: list[dict] = []
    kwargs = make_llm_kwargs()

    # Attempt 1 — plain request
    resp = await get_client().chat.completions.create(model=get_model(), messages=base_messages, **kwargs)
    raw = resp.choices[0].message.content or ""
    slides = _parse_script(raw)

    # Attempt 2 — assistant prefill: nudge the model to continue from the opening brace
    if not slides:
        prefill_messages = base_messages + [{"role": "assistant", "content": '{"slides":['}]
        resp2 = await get_client().chat.completions.create(model=get_model(), messages=prefill_messages, **kwargs)
        raw2 = '{"slides":[' + (resp2.choices[0].message.content or "")
        slides = _parse_script(raw2)

    # Attempt 3 — give up on the model, build slides directly from the source
    if not slides:
        slides = _build_fallback_slides(title, source)

    job_dir = output_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    segment_paths: list[Path] = []

    for i, slide in enumerate(slides):
        slide_img = await asyncio.to_thread(create_slide, slide, i, len(slides))
        slide_path = job_dir / f"slide_{i:02d}.png"
        await asyncio.to_thread(slide_img.save, str(slide_path))

        audio_path = job_dir / f"audio_{i:02d}.mp3"
        await text_to_speech(slide["narration"], audio_path)

        duration = await asyncio.to_thread(get_audio_duration, audio_path)

        seg_path = job_dir / f"segment_{i:02d}.mp4"
        await asyncio.to_thread(create_video_segment, slide_path, audio_path, seg_path, duration)
        segment_paths.append(seg_path)

    final_path = output_dir / f"{job_id}.mp4"
    await asyncio.to_thread(concat_segments, segment_paths, final_path)
    return final_path
