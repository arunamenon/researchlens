import re
from pipeline.llm_client import get_client, get_model, make_llm_kwargs
from pipeline.context_manager import max_content_chars

SYSTEM_PROMPT = """You are a Mermaid.js flowchart generator. Output ONLY raw Mermaid.js syntax. No explanation.

STRICT RULES (parse errors will occur if violated):
1. Line 1 must be exactly: flowchart TD
2. Each node: SingleWordID["Short Label"]  — one label per node, NO commas inside brackets
3. Node IDs: ONE word, letters/numbers only. Examples: A, B, LLM, GPT, N1. NO spaces, NO hyphens
4. Edges: A --> B   or   A -->|"label"| B   (label under 20 chars, no commas or colons)
5. Never write A[unquoted] or A["x","y","z"] — one string only per node
6. 8–10 nodes and edges connecting them

CONTENT: Map ACTUAL concepts, models, or techniques from the provided content. Not article sections."""

MERMAID_PREFILL = "flowchart TD\n"

# Patterns that indicate the model output is Graphviz/DOT, not Mermaid
_GRAPHVIZ_RE = re.compile(
    r'(?:'
    r'\bnode\s+[A-Za-z\-]'
    r'|\bnote\s+(?:left|right)\s+of\b'
    r'|\[shape\s*='
    r'|Graphviz:'
    r'|\bend\s+subgraph\b'
    r'|\bdigraph\s*\w*\s*\{'
    r'|\bstrict\s+(?:di)?graph\b'
    r')',
    re.IGNORECASE,
)


def _compact_id(s: str) -> str:
    """Remove spaces and hyphens from a node ID: 'Key Concepts' → 'KeyConcepts'."""
    return re.sub(r'[\s\-]+', '', s)


# Matches a node ID that contains at least one space or hyphen
# (i.e. multi-word IDs the model shouldn't have written)
_BAD_ID_RE = re.compile(r'[A-Za-z]\w*(?:[\s\-]+\w+)+')


def _fix_node_ids(line: str) -> str:
    """Replace space/hyphen node IDs with compact equivalents."""
    # Fix source node ID at the start of a line: "Key Concepts[" or "Key Concepts -->"
    line = re.sub(
        r'^(\s*)([A-Za-z]\w*(?:[\s\-]+\w+)+)(\s*(?:\["|-->|\s*$))',
        lambda m: m.group(1) + _compact_id(m.group(2)) + m.group(3),
        line,
    )
    # Fix target node ID after --> or -->|label|: "--> Key Concepts" or "--> Key Concepts["
    line = re.sub(
        r'(-->\s*(?:\|[^|]+\|)?\s*)([A-Za-z]\w*(?:[\s\-]+\w+)+)',
        lambda m: m.group(1) + _compact_id(m.group(2)),
        line,
    )
    return line


def _sanitize_mermaid(code: str) -> str:
    lines = []
    for line in code.splitlines():
        stripped = line.strip()

        # Pass directive lines through unchanged
        if re.match(r'^(flowchart|graph)\s', stripped, re.IGNORECASE) or \
                stripped.lower() in ('end',) or stripped.startswith('%%'):
            lines.append(line)
            continue

        # 0. Fix node IDs that contain spaces or hyphens
        line = _fix_node_ids(line)

        # 1. Remove empty edge labels -->|""| or -->|''| → -->
        line = re.sub(r'-->\s*\|""\s*\|', '-->', line)
        line = re.sub(r"-->\s*\|''\s*\|", '-->', line)

        # 2. Fix -->|label|> → -->|label|
        line = re.sub(r'(\|[^|]*\|)>', r'\1', line)

        # 3. Fix stray |>
        line = re.sub(r'\|>', '|', line)

        # 3b. Fix missing closing pipe in edge labels:
        #     A -->|"label" B[...] → A -->|"label"| B[...]
        line = re.sub(
            r'(-->)\|("(?:[^"]*)")\s+([A-Za-z])',
            r'\1|\2| \3',
            line,
        )

        # 3c. Strip invalid trailing text after a bare target node:
        #     A --> NodeID: some long text... → A --> NodeID
        #     (safe: won't match A --> Node["label: text"] because Node is followed by [)
        line = re.sub(r'(--> *[A-Za-z]\w*): [^\[{(].*$', r'\1', line)

        # 4. Sanitize edge labels: strip special chars and truncate long ones
        def _clean_edge(m: re.Match) -> str:
            label = m.group(1).strip('"').strip("'").strip()
            label = re.sub(r'[&]', 'and', label)
            label = re.sub(r'[:<>]', '-', label)
            label = re.sub(r'[,;]', ' ', label)
            label = re.sub(r'\s+', ' ', label).strip()
            if not label:
                return '-->'
            if len(label) > 25:
                label = label[:22].rstrip() + '...'
            return f'-->|"{label}"|'
        line = re.sub(r'-->\s*\|([^|]+)\|', _clean_edge, line)

        # 5a. Fix multi-value node labels: A["x", "y", "z"] → A["x / y"]
        #     Mermaid only accepts a single string inside [...], not a list
        def _merge_labels(m: re.Match) -> str:
            nid = m.group(1)
            items = re.findall(r'"([^"]+)"', m.group(2))
            # Keep first two items joined — enough to be meaningful without being long
            merged = ' / '.join(items[:2])
            if len(merged) > 35:
                merged = items[0][:35]
            return f'{nid}["{merged}"]'
        line = re.sub(
            r'\b([A-Za-z0-9_]+)\[((?:"[^"]*")(?:\s*,\s*"[^"]*")+)\]',
            _merge_labels,
            line,
        )

        # 5b. Fix empty node brackets with optional trailing text:
        #     F[] → F["F"]   |   H[] "noisy", "toxic" data → H["noisy toxic data"]
        def _fix_empty_bracket(m: re.Match) -> str:
            nid = m.group(1)
            trailing = (m.group(2) or '').strip()
            trailing = re.sub(r'["\',;]', ' ', trailing)
            trailing = re.sub(r'\s+', ' ', trailing).strip()
            label = trailing[:30] if trailing else nid
            return f'{nid}["{label}"]'
        line = re.sub(
            r'\b([A-Za-z0-9_]+)\[\]\s*(.*)',
            _fix_empty_bracket,
            line,
        )

        # 5c. Convert rounded-node style A(text) → A["text"]
        line = re.sub(
            r'\b([A-Za-z0-9_]+)\(([^)]{1,60})\)',
            lambda m: f'{m.group(1)}["{m.group(2)}"]',
            line,
        )

        # 6. Quote unquoted square-bracket labels: A[text] → A["text"]
        line = re.sub(
            r'\b([A-Za-z0-9_]+)\[([^"\]\[]{1,80})\]',
            lambda m: f'{m.group(1)}["{m.group(2)}"]',
            line,
        )

        # 7. Strip characters that break Mermaid inside quoted node labels
        def _clean_node_label(m: re.Match) -> str:
            label = m.group(1)
            label = label.replace('&', 'and').replace('<', '').replace('>', '')
            label = label.replace('—', '-').replace('–', '-')
            label = label.replace(';', ' ')
            return f'["{label}"]'
        line = re.sub(r'\["([^"]+)"\]', _clean_node_label, line)

        line = line.rstrip(';')
        lines.append(line)
    return '\n'.join(lines)


def _is_valid_mermaid(code: str) -> bool:
    first = code.strip().lower().split('\n')[0].rstrip(';')
    if not any(first.startswith(kw) for kw in ('flowchart', 'graph td', 'graph lr', 'graph tb', 'graph rl')):
        return False
    if _GRAPHVIZ_RE.search(code):
        return False
    # A diagram with no edges is useless — reject so the next attempt runs
    if not re.search(r'-->', code):
        return False
    return True


def _build_fallback_diagram(title: str, source: str) -> str:
    """Always-valid fallback diagram built from the article/source text."""
    candidates: list[str] = []
    for sentence in re.split(r'[.\n!?]', source[:6000]):
        s = sentence.strip()
        s = re.sub(r'[^a-zA-Z0-9 \-]', '', s).strip()
        if 12 < len(s) < 40:
            candidates.append(s)
        if len(candidates) >= 9:
            break
    if len(candidates) < 3:
        candidates = ["Background", "Core Method", "Key Results", "Applications", "Conclusion"]

    safe_title = re.sub(r'[^a-zA-Z0-9 ]', '', title)[:40]
    lines = ["flowchart TD", f'    ROOT["{safe_title}"]']
    groups = [candidates[i:i+3] for i in range(0, len(candidates), 3)]
    for gi, group in enumerate(groups[:3]):
        gid = f"G{gi}"
        glabel = re.sub(r'[^a-zA-Z0-9 ]', '', group[0])[:30]
        lines.append(f'    {gid}["{glabel}"]')
        lines.append(f'    ROOT --> {gid}')
        for ni, phrase in enumerate(group[1:], 1):
            nid = f"N{gi}{ni}"
            nlabel = re.sub(r'[^a-zA-Z0-9 ]', '', phrase)[:30]
            lines.append(f'    {nid}["{nlabel}"]')
            lines.append(f'    {gid} --> {nid}')
    return '\n'.join(lines)


async def generate_diagram(content: str, title: str, url_type: str, article: str = "") -> str:
    # Use the article as the primary source — it's already the full-content
    # synthesis produced by the map-reduce article generator.
    # Fall back to raw content if the article isn't available.
    model = get_model()
    src_chars = max_content_chars(model, prompt_tokens=500, output_tokens=500)
    source = (article.strip() or content)[:src_chars]

    base_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Create a Mermaid.js flowchart. First line must be: flowchart TD\n\n"
                f"Title: {title}\n\nContent:\n{source}"
            ),
        },
    ]
    kwargs = make_llm_kwargs()

    # Attempt 1 — plain request
    resp = await get_client().chat.completions.create(model=get_model(), messages=base_messages, **kwargs)
    raw = (resp.choices[0].message.content or "").strip()
    raw = re.sub(r'^```(?:mermaid)?\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
    fixed = _sanitize_mermaid(raw)
    if _is_valid_mermaid(fixed):
        return fixed.strip()

    # Attempt 2 — prefill forces model to start with "flowchart TD"
    prefill_msgs = base_messages + [{"role": "assistant", "content": MERMAID_PREFILL}]
    resp2 = await get_client().chat.completions.create(model=get_model(), messages=prefill_msgs, **kwargs)
    raw2 = MERMAID_PREFILL + (resp2.choices[0].message.content or "")
    raw2 = re.sub(r'^```(?:mermaid)?\s*', '', raw2, flags=re.MULTILINE)
    raw2 = re.sub(r'\s*```$', '', raw2, flags=re.MULTILINE)
    fixed2 = _sanitize_mermaid(raw2)
    if _is_valid_mermaid(fixed2):
        return fixed2.strip()

    # Attempt 3 — guaranteed-valid fallback built from the article/source
    return _build_fallback_diagram(title, source)
