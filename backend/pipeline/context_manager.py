"""Context window management: knows each model's token limit, splits content to fit."""
import re

# Tokens available in each model's context window.
# Sorted longest-key-first so prefix matching finds the most specific entry.
_LIMITS: dict[str, int] = {
    # Anthropic — all recent Claude models: 200K
    "claude-opus-4-7":    200_000,
    "claude-opus-4-6":    200_000,
    "claude-sonnet-4-6":  200_000,
    "claude-haiku-4-5":   200_000,
    "claude-3-5-sonnet":  200_000,
    "claude-3-5-haiku":   200_000,
    "claude-3-opus":      200_000,
    "claude":             200_000,  # catch-all for any claude model
    # OpenAI
    "gpt-4o":             128_000,
    "gpt-4o-mini":        128_000,
    "gpt-4-turbo":        128_000,
    "gpt-4":                8_192,
    "gpt-3.5-turbo":       16_385,
    "o1":                 200_000,
    "o3":                 200_000,
    # Ollama / local models
    "llama3.3":           131_072,
    "llama3.2":           131_072,
    "llama3.1":           131_072,
    "llama3":               8_192,
    "llama2":               4_096,
    "mistral-nemo":       131_072,
    "mistral":             32_768,
    "mixtral":             32_768,
    "codellama":           16_384,
    "phi4":                16_384,
    "phi3.5":             131_072,
    "phi3":               131_072,
    "gemma3":             131_072,
    "gemma2":               8_192,
    "gemma":                8_192,
    "qwen2.5":            131_072,
    "qwen2":               32_768,
    "deepseek-r1":         65_536,
    "deepseek":            32_768,
    "command-r-plus":     128_000,
    "command-r":          128_000,
}


def get_context_limit(model: str) -> int:
    """Return context window size in tokens for the given model name."""
    m = model.lower().strip()
    # Exact match first
    if m in _LIMITS:
        return _LIMITS[m]
    # Prefix match — longest key wins (dict is already ordered)
    for key in sorted(_LIMITS, key=len, reverse=True):
        if m.startswith(key):
            return _LIMITS[key]
    # Conservative default for unknown models
    return 4_096


def max_content_chars(model: str, prompt_tokens: int = 600, output_tokens: int = 2_000) -> int:
    """Max characters of document content that can be sent in one call.

    Leaves room for the system prompt, user-message framing, and the model's
    response.  Uses ~4 chars-per-token as a conservative estimate."""
    limit = get_context_limit(model)
    available = max(500, limit - prompt_tokens - output_tokens)
    return available * 4   # 4 chars ≈ 1 token


def split_content(text: str, max_chars: int) -> list[str]:
    """Split text into chunks at double-newline (paragraph) boundaries.

    Each chunk is at most max_chars characters.  If a single paragraph
    exceeds the limit it is split on sentence boundaries."""
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""

    for para in re.split(r'\n{2,}', text):
        para = para.strip()
        if not para:
            continue
        candidate = (current + "\n\n" + para).strip() if current else para
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = para
        else:
            current = candidate

    if current:
        chunks.append(current)

    # Safety: split any chunk that's still too large on sentence boundaries
    result: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            result.append(chunk)
        else:
            sub = ""
            for sent in re.split(r'(?<=[.!?])\s+', chunk):
                cand = (sub + " " + sent).strip() if sub else sent
                if len(cand) > max_chars and sub:
                    result.append(sub)
                    sub = sent
                else:
                    sub = cand
            if sub:
                result.append(sub)

    return result or [text[:max_chars]]
