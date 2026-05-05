import asyncio
import traceback
from pathlib import Path

from pipeline.content_extractor import extract_content
from pipeline.article_generator import generate_article
from pipeline.diagram_generator import generate_diagram
from pipeline.video_generator import generate_video

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

jobs: dict = {}


async def _emit(job_id: str, event: dict) -> None:
    job = jobs.get(job_id)
    if job:
        await job["events"].put(event)
        if "progress" in event:
            job["progress"] = event["progress"]
        if "stage" in event:
            job["stage"] = event["stage"]


async def run_pipeline(job_id: str, url: str) -> None:
    try:
        # --- Content Extraction ---
        await _emit(job_id, {
            "type": "progress", "stage": "extracting", "progress": 5,
            "message": "Detecting URL type and extracting content...",
        })
        extracted = await extract_content(url)
        content = extracted["content"]
        title = extracted["title"]
        url_type = extracted["url_type"]
        chunks = extracted["chunks"]

        jobs[job_id]["content"] = content
        jobs[job_id]["chunks"] = chunks
        jobs[job_id]["url_type"] = url_type

        await _emit(job_id, {
            "type": "progress", "stage": "extracting", "progress": 20,
            "message": f"Extracted content from {url_type} source: {title}",
        })

        # --- Article Generation ---
        from pipeline.context_manager import max_content_chars, split_content
        from pipeline.llm_client import get_model
        chunk_chars = max_content_chars(get_model(), prompt_tokens=600, output_tokens=800)
        n_chunks = len(split_content(content, chunk_chars))
        mode_msg = (
            f"Analysing content in {n_chunks} passes (map-reduce)..."
            if n_chunks > 1 else
            "Generating comprehensive explanation article..."
        )
        await _emit(job_id, {
            "type": "progress", "stage": "article", "progress": 25,
            "message": mode_msg,
        })
        article = await generate_article(content, title, url_type)
        jobs[job_id]["article"] = article
        await _emit(job_id, {
            "type": "progress", "stage": "article", "progress": 50,
            "message": "Article generation complete.",
        })

        # --- Diagram Generation ---
        # Pass the generated article so the diagram is based on the same
        # structured summary — NOT the raw extracted text which can be
        # 15k+ tokens and overflow llama3's context window.
        await _emit(job_id, {
            "type": "progress", "stage": "diagram", "progress": 55,
            "message": "Generating flow diagram...",
        })
        diagram_code = await generate_diagram(content, title, url_type, article=article)
        jobs[job_id]["diagram_code"] = diagram_code
        await _emit(job_id, {
            "type": "progress", "stage": "diagram", "progress": 70,
            "message": "Flow diagram generation complete.",
        })

        # --- Video Generation (non-fatal — requires ffmpeg) ---
        video_url: str | None = None
        video_error: str | None = None
        await _emit(job_id, {
            "type": "progress", "stage": "video", "progress": 75,
            "message": "Generating animated explainer video...",
        })
        try:
            video_path = await generate_video(content, title, url_type, OUTPUT_DIR, job_id, article=article)
            jobs[job_id]["video_path"] = str(video_path)
            video_url = f"/api/video/{job_id}"
            await _emit(job_id, {
                "type": "progress", "stage": "video", "progress": 95,
                "message": "Video generation complete.",
            })
        except FileNotFoundError as e:
            missing = str(e).split("'")[1] if "'" in str(e) else str(e)
            video_error = f"'{missing}' not found — run: brew install ffmpeg"
            await _emit(job_id, {
                "type": "progress", "stage": "video", "progress": 95,
                "message": f"Video skipped: {video_error}",
            })
        except Exception as e:
            video_error = str(e)
            await _emit(job_id, {
                "type": "progress", "stage": "video", "progress": 95,
                "message": f"Video generation failed: {video_error}",
            })

        # --- Complete ---
        jobs[job_id]["status"] = "complete"
        await _emit(job_id, {
            "type": "complete",
            "stage": "complete",
            "progress": 100,
            "message": "Analysis complete!",
            "article": article,
            "diagram_code": diagram_code,
            "video_url": video_url,
            "video_error": video_error,
            "url_type": url_type,
            "source_url": url,
        })

    except Exception as e:
        error_msg = str(e)
        tb = traceback.format_exc()
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = error_msg
        await _emit(job_id, {
            "type": "error",
            "stage": "error",
            "message": f"Pipeline failed: {error_msg}",
            "detail": tb,
        })
