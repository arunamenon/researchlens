# ResearchLens

Deep-dive any research paper or web article. Paste an arXiv link or URL and get:

- **Article** — long-form summary written like a blog post
- **Diagram** — auto-generated Mermaid.js concept map
- **Video** — narrated explainer with text-to-speech and slides
- **Q&A** — chat with the paper using holistic or retrieval-based answering

Runs entirely on local AI (Ollama) by default. Swap to OpenAI or Anthropic from the settings panel.

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Mermaid.js |
| Backend | Python 3.11+, FastAPI, SSE streaming |
| AI (default) | Ollama (llama3) — runs locally, no API key needed |
| AI (optional) | OpenAI GPT-4o, Anthropic Claude |
| TTS | Microsoft Edge TTS (`edge-tts`) |
| Video | ffmpeg |

---

## Prerequisites

### Required

- **Node.js** 18+ — [nodejs.org](https://nodejs.org)
- **Python** 3.11+ — [python.org](https://python.org)
- **Ollama** — [ollama.com](https://ollama.com)

```bash
# Install and start Ollama
brew install ollama          # macOS
ollama serve                 # start the server
ollama pull llama3           # download the default model (~4 GB)
```

### Optional (for video generation)

```bash
brew install ffmpeg
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/researchlens.git
cd researchlens
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Frontend

```bash
cd frontend
npm install
```

---

## Running

Open two terminal tabs from the project root.

**Terminal 1 — Backend**

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend**

```bash
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Configuration

Click the **⚙ settings icon** (top-right) to switch AI provider and model at runtime — no restart needed.

| Provider | Model examples | API key required |
|---|---|---|
| Ollama (default) | `llama3`, `mistral`, `gemma2` | No |
| OpenAI | `gpt-4o`, `gpt-4o-mini` | Yes |
| Anthropic | `claude-opus-4-7`, `claude-sonnet-4-6` | Yes |

For cloud providers, paste your API key directly in the settings panel — it is never stored to disk.

---

## Project Structure

```
researchlens/
├── backend/
│   ├── main.py                  # FastAPI app, SSE endpoints
│   ├── requirements.txt
│   ├── .env.example
│   └── pipeline/
│       ├── orchestrator.py      # job runner, SSE progress events
│       ├── content_extractor.py # arXiv API + PDF + web scraping
│       ├── article_generator.py # map-reduce long-form article
│       ├── diagram_generator.py # Mermaid.js flowchart + sanitizer
│       ├── video_generator.py   # TTS + slide images + ffmpeg
│       ├── qa_engine.py         # holistic / BM25 retrieval Q&A
│       ├── llm_client.py        # Ollama / OpenAI / Anthropic adapter
│       └── context_manager.py   # token budget helpers
└── frontend/
    ├── index.html
    ├── vite.config.ts
    └── src/
        ├── App.tsx
        ├── components/
        │   ├── URLInput.tsx
        │   ├── ProgressTracker.tsx
        │   ├── ArticleViewer.tsx
        │   ├── DiagramViewer.tsx
        │   ├── VideoPlayer.tsx
        │   ├── QAPanel.tsx
        │   └── AdminPanel.tsx
        ├── hooks/
        │   ├── useAnalysis.ts
        │   └── useQA.ts
        └── types.ts
```

---

## Supported URLs

- **arXiv** — `https://arxiv.org/abs/2303.18223` or `https://arxiv.org/pdf/2303.18223`
- **Web articles** — any publicly accessible blog post, news article, or documentation page

---

## Troubleshooting

**Ollama connection refused**
Make sure `ollama serve` is running in a separate terminal before starting the backend.

**arXiv rate limit (HTTP 429)**
The backend automatically falls back to scraping the abstract page. If the full PDF is unavailable, the summary will be based on the abstract only.

**Video tab shows "generation failed"**
Install ffmpeg: `brew install ffmpeg`, then re-analyze.

**Diagram render error**
The sanitizer handles most model output quirks automatically. If errors persist, switch to a stronger model (GPT-4o or Claude) in the settings panel for more reliable Mermaid syntax.
