"""Q&A engine with automatic routing between two answer modes.

Holistic mode  — question needs the full article (explain, summarise, overview, etc.)
               → send the entire article to the LLM and ask for a free-form answer.

Retrieval mode — question needs specific facts or details
               → BM25-rank article sections + content chunks, feed top-K to the LLM.
"""
import json
import math
import re
from collections import Counter

from pipeline.llm_client import get_client, get_model, make_llm_kwargs
from pipeline.context_manager import max_content_chars

TOP_K = 8

# ── Question classifier ────────────────────────────────────────────────────

_HOLISTIC_RE = re.compile(
    r'\b('
    r'summari[sz]e?|summary|summarise'
    r'|overview|outline|recap|rundown'
    r'|explain(\s+this)?(\s+(paper|article|research|work|study|content))?'
    r'|describe(\s+this)?(\s+(paper|article|research|work|study|content))?'
    r'|what(\s+is|\s+does|\s+are)?\s+this\s+(paper|article|research|about)'
    r'|tell\s+me\s+about'
    r'|walk\s+(me\s+)?through'
    r'|break(\s+it)?\s+down'
    r'|eli5|eli\s*5'
    r'|5[\s-]year[\s-]old|five[\s-]year[\s-]old'
    r'|simple\s+terms?|plain\s+(english|language|terms?)'
    r'|layman|beginner|non[\s-]technical|non[\s-]expert'
    r'|high[\s-]level|big[\s-]picture|gist|essence|takeaway|tldr|tl[;,\s]?dr'
    r'|like\s+i.?m|as\s+if\s+i'
    r')',
    re.IGNORECASE,
)

def _is_holistic(question: str) -> bool:
    """True when the question calls for a full-paper answer rather than fact retrieval."""
    return bool(_HOLISTIC_RE.search(question))


# ── BM25 retrieval ─────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    return re.findall(r'\b\w{2,}\b', text.lower())


def _bm25_rank(question: str, pool: list[dict], k1: float = 1.5, b: float = 0.75) -> list[dict]:
    query_tokens = set(_tokenize(question))
    if not query_tokens or not pool:
        return pool

    tokenized_docs = [_tokenize(item["text"]) for item in pool]
    avg_dl = sum(len(t) for t in tokenized_docs) / max(len(tokenized_docs), 1)
    N = len(pool)

    idf: dict[str, float] = {}
    for term in query_tokens:
        df = sum(1 for t in tokenized_docs if term in t)
        idf[term] = math.log((N - df + 0.5) / (df + 0.5) + 1)

    scored: list[tuple[float, dict]] = []
    for item, tokens in zip(pool, tokenized_docs):
        dl = len(tokens)
        counter = Counter(tokens)
        score = sum(
            idf[term] * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avg_dl))
            for term in query_tokens
            if (f := counter.get(term, 0)) > 0
        )
        scored.append((score, item))

    scored.sort(key=lambda x: -x[0])
    return [item for _, item in scored]


# ── Article helpers ────────────────────────────────────────────────────────

def _article_to_units(article: str) -> list[dict]:
    """Split article into section-level units (## headings), sub-split large sections."""
    units: list[dict] = []
    sections = re.split(r'\n(?=#{1,3} )', article.strip())
    idx = 0
    for section in sections:
        text = section.strip()
        if len(text) < 40:
            continue
        if len(text) > 1200:
            for para in [p.strip() for p in text.split('\n\n') if len(p.strip()) > 40]:
                units.append({"text": para, "chunk_index": f"a{idx}", "source": "article"})
                idx += 1
        else:
            units.append({"text": text, "chunk_index": f"a{idx}", "source": "article"})
            idx += 1
    return units


def _build_context(units: list[dict]) -> str:
    lines = []
    for unit in units:
        label = f"[ARTICLE SECTION {unit['chunk_index']}]" if unit.get("source") == "article" else f"[CHUNK {unit['chunk_index']}]"
        lines.append(f"{label}\n{unit['text']}")
    return "\n\n".join(lines)


# ── JSON parsing ───────────────────────────────────────────────────────────

def _parse_qa_json(raw: str) -> dict | None:
    cleaned = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r'\s*```$', '', cleaned.strip(), flags=re.MULTILINE)
    for candidate in [cleaned, re.search(r'\{[\s\S]*\}', cleaned)]:
        if candidate is None:
            continue
        text = candidate if isinstance(candidate, str) else candidate.group(0)
        try:
            return json.loads(text)
        except (json.JSONDecodeError, AttributeError):
            pass
    try:
        return json.loads('{"answer": "' + cleaned)
    except json.JSONDecodeError:
        pass
    return None


# ── Holistic mode ──────────────────────────────────────────────────────────

async def _answer_holistic(question: str, article: str, url_type: str) -> dict:
    """Answer using the full article as context — no chunk retrieval."""
    max_chars = max_content_chars(get_model(), prompt_tokens=600, output_tokens=1_500)
    source = article.strip()[:max_chars]

    system_prompt = (
        f"You are a knowledgeable assistant explaining a {url_type} to the user. "
        "Use the full article content provided below. "
        "Answer clearly, thoroughly, and in well-structured Markdown. "
        "Adapt your language and depth to exactly what the user asked for — "
        "if they want a simple explanation, use plain language and analogies; "
        "if they want a high-level overview, be concise and structured."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Article:\n{source}\n\nQuestion: {question}"},
    ]
    resp = await get_client().chat.completions.create(
        model=get_model(), messages=messages, **make_llm_kwargs()
    )
    answer = (resp.choices[0].message.content or "").strip()
    return {"answer": answer, "references": [], "mode": "holistic"}


# ── Retrieval mode ─────────────────────────────────────────────────────────

async def _answer_retrieval(question: str, chunks: list[dict], article: str, url_type: str) -> dict:
    """BM25-retrieve the most relevant passages then answer with citations."""
    pool: list[dict] = []
    if article.strip():
        pool.extend(_article_to_units(article))
    pool.extend(chunks)

    ranked = _bm25_rank(question, pool)
    top_units = ranked[:TOP_K]

    context = _build_context(top_units)
    max_chars = max_content_chars(get_model(), prompt_tokens=800, output_tokens=1_000)
    context = context[:max_chars]

    system_prompt = (
        f"You are a helpful Q&A assistant for a {url_type}.\n"
        "You have the most relevant passages from the source below.\n\n"
        "RULES:\n"
        "1. Answer using ONLY the information in the provided passages.\n"
        "2. Report specific names, numbers, quotes, and findings when present.\n"
        "3. Only say the information is absent if you genuinely cannot find anything relevant.\n"
        "4. Do NOT invent facts not present in the passages.\n\n"
        'Respond with a JSON object:\n'
        '{"answer": "<markdown answer>", "cited_chunks": [<indices used, e.g. "a0", 2>]}\n\n'
        "Start your response with {."
    )
    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Passages:\n\n{context}\n\nQuestion: {question}"},
    ]
    kwargs = make_llm_kwargs()

    resp = await get_client().chat.completions.create(model=get_model(), messages=base_messages, **kwargs)
    raw = resp.choices[0].message.content or ""
    result = _parse_qa_json(raw)

    if not result:
        prefill = '{"answer": "'
        resp2 = await get_client().chat.completions.create(
            model=get_model(),
            messages=base_messages + [{"role": "assistant", "content": prefill}],
            **kwargs,
        )
        raw2 = prefill + (resp2.choices[0].message.content or "")
        result = _parse_qa_json(raw2)

    if not result:
        return {"answer": raw.strip() or "Could not generate an answer.", "references": [], "mode": "retrieval"}

    answer = result.get("answer", "").strip() or raw.strip()

    # Resolve cited indices to source objects
    article_units = _article_to_units(article) if article.strip() else []
    article_map = {u["chunk_index"]: u for u in article_units}
    chunk_map = {str(c["chunk_index"]): c for c in chunks}

    references: list[dict] = []
    seen: set[str] = set()
    for idx in result.get("cited_chunks", []):
        key = str(idx)
        if key in seen:
            continue
        seen.add(key)
        if key in chunk_map:
            references.append(chunk_map[key])
        elif key in article_map:
            references.append(article_map[key])

    # Fallback: if model cited nothing, show top retrieved units
    if not references:
        for unit in top_units[:3]:
            key = str(unit["chunk_index"])
            if key not in seen:
                seen.add(key)
                references.append(unit)

    return {"answer": answer, "references": references, "mode": "retrieval"}


# ── Public API ─────────────────────────────────────────────────────────────

async def answer_question(
    question: str,
    chunks: list[dict],
    url_type: str,
    article: str = "",
) -> dict:
    """Route the question to holistic or retrieval mode, then answer it."""
    if _is_holistic(question) and article.strip():
        return await _answer_holistic(question, article, url_type)
    return await _answer_retrieval(question, chunks, article, url_type)
