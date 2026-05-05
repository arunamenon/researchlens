import asyncio
import json
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from pipeline.orchestrator import jobs, run_pipeline
from pipeline.qa_engine import answer_question
from pipeline.llm_client import update_config, get_config

app = FastAPI(title="Research Paper Analyzer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


class AnalyzeRequest(BaseModel):
    url: str


class AskRequest(BaseModel):
    question: str


class SettingsRequest(BaseModel):
    provider: str           # "ollama" | "openai" | "anthropic"
    model: str
    api_key: str = ""
    base_url: str = ""      # custom base URL (used for ollama)


@app.post("/api/analyze")
async def analyze(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "pending",
        "progress": 0,
        "stage": "queued",
        "article": None,
        "diagram_code": None,
        "video_path": None,
        "content": None,
        "chunks": None,
        "url_type": None,
        "source_url": request.url,
        "error": None,
        "events": asyncio.Queue(),
    }
    background_tasks.add_task(run_pipeline, job_id, request.url)
    return {"job_id": job_id}


@app.get("/api/stream/{job_id}")
async def stream(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        queue = jobs[job_id]["events"]
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield {"data": json.dumps(event)}
                if event.get("type") in ("complete", "error"):
                    break
            except asyncio.TimeoutError:
                yield {"data": json.dumps({"type": "heartbeat"})}

    return EventSourceResponse(event_generator())


@app.post("/api/ask/{job_id}")
async def ask(job_id: str, request: AskRequest):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "complete":
        raise HTTPException(status_code=400, detail="Analysis not yet complete")
    if not job.get("chunks"):
        raise HTTPException(status_code=400, detail="No content chunks available")

    result = await answer_question(
        question=request.question,
        chunks=job["chunks"],
        url_type=job["url_type"],
        article=job.get("article") or "",
    )
    return result


@app.get("/api/video/{job_id}")
async def get_video(job_id: str):
    job = jobs.get(job_id)
    if not job or not job.get("video_path"):
        raise HTTPException(status_code=404, detail="Video not ready")
    video_path = Path(job["video_path"])
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(str(video_path), media_type="video/mp4")


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "stage": job["stage"],
        "error": job.get("error"),
    }


@app.get("/api/settings")
async def get_settings():
    return get_config()


@app.post("/api/settings")
async def save_settings(request: SettingsRequest):
    valid_providers = {"ollama", "openai", "anthropic"}
    if request.provider not in valid_providers:
        raise HTTPException(status_code=400, detail=f"Provider must be one of: {', '.join(valid_providers)}")
    if not request.model.strip():
        raise HTTPException(status_code=400, detail="Model name is required")
    if request.provider in ("openai", "anthropic") and not request.api_key.strip():
        raise HTTPException(status_code=400, detail=f"API key is required for {request.provider}")
    update_config(
        provider=request.provider,
        model=request.model.strip(),
        api_key=request.api_key.strip(),
        base_url=request.base_url.strip(),
    )
    return {"status": "ok", **get_config()}


@app.get("/health")
async def health():
    return {"status": "ok"}
