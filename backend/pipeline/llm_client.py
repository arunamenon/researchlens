from openai import AsyncOpenAI

# Mutable config — updated at runtime via /api/settings
_config: dict = {
    "provider": "ollama",
    "model": "llama3",
    "api_key": "",
    "base_url": "http://localhost:11434/v1",
}


def update_config(provider: str, model: str, api_key: str = "", base_url: str = "") -> None:
    _config["provider"] = provider
    _config["model"] = model
    _config["api_key"] = api_key
    if base_url:
        _config["base_url"] = base_url
    elif provider == "ollama":
        _config["base_url"] = "http://localhost:11434/v1"


def get_config() -> dict:
    return {k: v for k, v in _config.items() if k != "api_key"}


def get_model() -> str:
    return _config["model"]


# ---------------------------------------------------------------------------
# Anthropic adapter — wraps anthropic SDK to look like an OpenAI client
# so all pipeline code can use the same client.chat.completions.create() call
# ---------------------------------------------------------------------------

class _FakeChoice:
    def __init__(self, text: str):
        self.message = type("M", (), {"content": text})()


class _FakeResponse:
    def __init__(self, text: str):
        self.choices = [_FakeChoice(text)]


class _AnthropicCompletions:
    def __init__(self, api_key: str):
        from anthropic import AsyncAnthropic  # lazy import
        self._ac = AsyncAnthropic(api_key=api_key)

    async def create(self, model: str, messages: list, **kwargs) -> _FakeResponse:
        kwargs.pop("stream", None)  # adapter is non-streaming
        system = ""
        user_msgs: list[dict] = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                user_msgs.append({"role": m["role"], "content": m["content"]})
        response = await self._ac.messages.create(
            model=model,
            max_tokens=4096,
            **({"system": system} if system else {}),
            messages=user_msgs,
        )
        text = response.content[0].text if response.content else ""
        return _FakeResponse(text)


class _AnthropicChat:
    def __init__(self, api_key: str):
        self.completions = _AnthropicCompletions(api_key)


class _AnthropicAdapter:
    def __init__(self, api_key: str):
        self.chat = _AnthropicChat(api_key)


# ---------------------------------------------------------------------------
# Public factory + provider-specific kwargs
# ---------------------------------------------------------------------------

def make_llm_kwargs() -> dict:
    """Extra kwargs for chat.completions.create() — provider-specific.
    For Ollama this extends the context window from the 2048-token default to
    8192, which is critical for sending real document content."""
    if _config["provider"] == "ollama":
        return {"extra_body": {"options": {"num_ctx": 8192}}}
    return {}


def get_client():
    provider = _config["provider"]
    api_key = _config["api_key"]

    if provider == "ollama":
        return AsyncOpenAI(base_url=_config["base_url"], api_key="ollama")
    elif provider == "openai":
        return AsyncOpenAI(api_key=api_key)
    elif provider == "anthropic":
        return _AnthropicAdapter(api_key)
    else:
        raise ValueError(f"Unknown provider: {provider}")
