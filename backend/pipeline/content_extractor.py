import re
import httpx
import arxiv
import pypdf
import trafilatura
from io import BytesIO


def detect_url_type(url: str) -> str:
    if re.search(r'arxiv\.org/(abs|pdf)/', url):
        return "arxiv"
    return "general"


def _make_text_chunks(text: str) -> list[dict]:
    """Split text into paragraph/sentence chunks for Q&A references.
    Threshold is low (30 chars) so short quotes, attributions, and epigraphs are included."""
    paragraphs = re.split(r'\n{1,}', text)  # split on single newlines too
    chunks = []
    buffer = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            if len(buffer) >= 30:
                chunks.append({"text": buffer, "chunk_index": len(chunks)})
                buffer = ""
            continue
        buffer = (buffer + " " + para).strip() if buffer else para
        # Flush when buffer is long enough
        if len(buffer) >= 200:
            chunks.append({"text": buffer, "chunk_index": len(chunks)})
            buffer = ""
    if len(buffer) >= 30:
        chunks.append({"text": buffer, "chunk_index": len(chunks)})
    return chunks


def _extract_arxiv_id(url: str) -> str:
    match = re.search(r'arxiv\.org/(?:abs|pdf)/([0-9]+\.[0-9]+)', url)
    if not match:
        raise ValueError(f"Could not extract arXiv ID from URL: {url}")
    return match.group(1)


async def _fetch_arxiv_metadata_from_abs(arxiv_id: str) -> tuple[str, str]:
    """Fallback: scrape title + abstract directly from the arXiv abs page."""
    abs_url = f"https://arxiv.org/abs/{arxiv_id}"
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as http:
        resp = await http.get(abs_url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        html = resp.text

    # Title: inside <h1 class="title mathjax">
    title = arxiv_id
    tm = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h1>', html, re.DOTALL)
    if tm:
        title = re.sub(r'<[^>]+>', '', tm.group(1)).replace('Title:', '').strip()

    # Abstract: inside <blockquote class="abstract mathjax">
    abstract = ""
    am = re.search(r'<blockquote[^>]*class="[^"]*abstract[^"]*"[^>]*>(.*?)</blockquote>', html, re.DOTALL)
    if am:
        abstract = re.sub(r'<[^>]+>', '', am.group(1)).replace('Abstract:', '').strip()

    return title, abstract


async def extract_arxiv(url: str) -> dict:
    arxiv_id = _extract_arxiv_id(url)

    # Try the arxiv API library with retries; fall back to scraping the abs page on failure
    title, abstract = "", ""
    pdf_url: str | None = None
    try:
        import asyncio as _asyncio
        client = arxiv.Client(num_retries=3, delay_seconds=2.0)
        search = arxiv.Search(id_list=[arxiv_id])
        results = await _asyncio.to_thread(lambda: list(client.results(search)))
        if results:
            paper = results[0]
            title = paper.title
            abstract = paper.summary
            pdf_url = paper.pdf_url
    except Exception:
        pass

    if not title:
        # API is rate-limited or down — scrape the abs page directly
        title, abstract = await _fetch_arxiv_metadata_from_abs(arxiv_id)

    pdf_text = ""
    target_pdf = pdf_url or f"https://arxiv.org/pdf/{arxiv_id}"
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http:
            resp = await http.get(target_pdf)
            resp.raise_for_status()
            reader = pypdf.PdfReader(BytesIO(resp.content))
            pages = min(len(reader.pages), 30)
            pdf_text = "\n\n".join(
                reader.pages[i].extract_text() or "" for i in range(pages)
            )
    except Exception:
        pass

    content = f"Title: {title}\n\nAbstract:\n{abstract}"
    if pdf_text.strip():
        content += f"\n\nFull Paper Text:\n{pdf_text}"

    return {
        "content": content,
        "title": title,
        "url_type": "arxiv",
        "chunks": _make_text_chunks(content),
    }


async def extract_general(url: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ResearchAnalyzer/1.0)"},
        )
        resp.raise_for_status()
        html = resp.text

    content = trafilatura.extract(html, include_comments=False, include_tables=True) or ""
    if not content.strip():
        raise ValueError("Could not extract meaningful text from the URL.")

    title = "Web Article"
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = re.sub(r'\s+', ' ', title_match.group(1)).strip()

    return {
        "content": content,
        "title": title,
        "url_type": "general",
        "chunks": _make_text_chunks(content),
    }


async def extract_content(url: str) -> dict:
    url_type = detect_url_type(url)
    if url_type == "arxiv":
        return await extract_arxiv(url)
    else:
        return await extract_general(url)
