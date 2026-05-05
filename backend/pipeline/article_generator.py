"""Article generation with map-reduce for documents that exceed model context.

Single pass  — content fits in one call → direct generation.
Multi-pass   — content too large → map (extract facts per chunk) then
               reduce (synthesize full article from all facts).
"""
from pipeline.llm_client import get_client, get_model, make_llm_kwargs
from pipeline.context_manager import max_content_chars, split_content

# ── Prompts ──────────────────────────────────────────────────────────────────

_SINGLE_SYSTEM = """You are an expert technical writer. Write a detailed, accurate article based STRICTLY on the provided content.

Structure (Markdown):
## Introduction — overview and significance
## Background & Context — prior work, motivation, problem
## Core Concepts & Methodology — techniques, algorithms, models; be specific
## Key Findings & Results — numbers, comparisons, conclusions; quote directly
## Implications & Applications — real-world uses from the content
## Critical Analysis — limitations, caveats, open questions
## Conclusion — key takeaways

Rules:
- 1500–2500 words; every claim grounded in the content
- Use actual names, numbers, terminology from the content
- If the content contains opening quotes, epigraphs, or attributions, include them verbatim with the author's name
- Output ONLY the article, starting with ## Introduction"""

_MAP_SYSTEM = """Extract ALL important information from this content chunk into a structured list.

Include:
- Main topics and their key points
- Specific methods, algorithms, models, datasets, techniques
- Quantitative results, metrics, benchmark scores, comparisons
- Named entities: people, organizations, tools, papers cited
- Direct quotes or notable statements (include the speaker/author if named)
- Limitations, open questions, caveats

Output as a clear bullet-point list. Be thorough — nothing important should be omitted."""

_REDUCE_SYSTEM = """You are an expert technical writer. Write a comprehensive article using ALL the extracted facts below.

Structure (Markdown):
## Introduction — overview and significance
## Background & Context — prior work, motivation, problem
## Core Concepts & Methodology — techniques, algorithms, models; be specific
## Key Findings & Results — numbers, comparisons, conclusions; quote directly
## Implications & Applications — real-world uses
## Critical Analysis — limitations, caveats, open questions
## Conclusion — key takeaways

Rules:
- 1500–2500 words; use ALL facts provided
- Include any direct quotes or named attributions verbatim
- Use actual names, numbers, terminology from the facts
- Do not invent anything not in the facts
- Output ONLY the article, starting with ## Introduction"""


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _call(messages: list[dict]) -> str:
    resp = await get_client().chat.completions.create(
        model=get_model(),
        messages=messages,
        **make_llm_kwargs(),
    )
    return (resp.choices[0].message.content or "").strip()


async def _single_pass(content: str, title: str, url_type: str) -> str:
    return await _call([
        {"role": "system", "content": _SINGLE_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Write a detailed summary article for this {url_type} content. "
                f"Use ONLY the information below.\n\n"
                f"Title: {title}\n\nContent:\n{content}"
            ),
        },
    ])


async def _map_chunk(chunk: str, title: str, chunk_num: int, total: int) -> str:
    return await _call([
        {"role": "system", "content": _MAP_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Source: '{title}' — chunk {chunk_num} of {total}\n\n"
                f"{chunk}"
            ),
        },
    ])


async def _reduce(facts: str, title: str, url_type: str) -> str:
    return await _call([
        {"role": "system", "content": _REDUCE_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Title: {title}\nSource type: {url_type}\n\n"
                f"Extracted facts from all sections of the source:\n\n{facts}"
            ),
        },
    ])


# ── Public API ────────────────────────────────────────────────────────────────

async def generate_article(content: str, title: str, url_type: str) -> str:
    """Generate article from full content, chunking if needed."""
    model = get_model()

    # Reserve ~600 tokens for prompt overhead and ~800 for the map output
    map_chunk_chars = max_content_chars(model, prompt_tokens=600, output_tokens=800)

    chunks = split_content(content, map_chunk_chars)

    if len(chunks) == 1:
        # Content fits in a single call — direct generation
        return await _single_pass(content, title, url_type)

    # Map: extract key facts from every chunk in parallel
    import asyncio
    fact_tasks = [
        _map_chunk(chunk, title, i + 1, len(chunks))
        for i, chunk in enumerate(chunks)
    ]
    fact_parts = await asyncio.gather(*fact_tasks)

    # Combine all facts
    all_facts = "\n\n---\n\n".join(
        f"[Section {i + 1}/{len(chunks)}]\n{facts}"
        for i, facts in enumerate(fact_parts)
    )

    # Reduce: if combined facts still exceed context, summarise facts first
    reduce_input_chars = max_content_chars(model, prompt_tokens=600, output_tokens=2_000)
    if len(all_facts) > reduce_input_chars:
        # Condense: ask model to merge the fact lists into one tighter list
        all_facts = await _call([
            {
                "role": "system",
                "content": "Merge the following fact lists into one comprehensive, non-redundant bullet list. Keep all unique facts.",
            },
            {"role": "user", "content": all_facts[:reduce_input_chars]},
        ])

    return await _reduce(all_facts, title, url_type)
