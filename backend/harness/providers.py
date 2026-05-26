"""
Provider abstraction — normalizes all LLM APIs to OpenAI-compatible protocol.

Supports: OpenAI, DeepSeek, Anthropic, Groq, OpenRouter, Ollama, llama.cpp, vLLM.
"""
import os
import time
import sys
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProviderConfig:
    """Configuration for a model provider."""
    name: str
    base_url: str
    api_key: str = ""
    model_id: str = ""
    supports_tools: bool = True
    supports_json_mode: bool = True
    supports_streaming: bool = True
    max_context: int = 128000
    prompt_template: str = "openai"  # openai, chatml, anthropic
    default_headers: dict = field(default_factory=dict)
    is_local: bool = False


# ── Provider presets ─────────────────────────────────────────────────

PROVIDERS: dict[str, ProviderConfig] = {
    # ── Closed-Source ──
    "openai": ProviderConfig(
        name="openai",
        base_url="https://api.openai.com/v1",
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        model_id="gpt-4o-mini",
        prompt_template="openai",
    ),
    "deepseek": ProviderConfig(
        name="deepseek",
        base_url="https://api.deepseek.com/v1",
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        model_id="deepseek-chat",
        prompt_template="openai",
    ),
    "anthropic": ProviderConfig(
        name="anthropic",
        base_url="https://api.anthropic.com/v1",
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        model_id="claude-sonnet-4-20250514",
        prompt_template="anthropic",
    ),
    "groq": ProviderConfig(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        api_key=os.environ.get("GROQ_API_KEY", ""),
        model_id="llama-3.3-70b-versatile",
        prompt_template="openai",
    ),
    "openrouter": ProviderConfig(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        model_id="openai/gpt-4o-mini",
        prompt_template="openai",
        default_headers={
            "HTTP-Referer": os.environ.get("SOM_HTTP_REFERER", "https://github.com/som-code/som-code"),
            "X-Title": os.environ.get("SOM_APP_TITLE", "SOM-CODE"),
        },
    ),
    "opencode-go": ProviderConfig(
        name="opencode-go",
        # OpenCode Go subscription gateways vary by account/setup; keep the
        # default configurable while preserving the standard OpenAI-compatible
        # /v1/chat/completions contract.
        base_url=os.environ.get("OPENCODE_GO_BASE_URL", os.environ.get("OPENCODE_BASE_URL", "https://api.opencode.ai/v1")),
        api_key=os.environ.get("OPENCODE_GO_API_KEY", os.environ.get("OPENCODE_API_KEY", "")),
        model_id=os.environ.get("OPENCODE_GO_MODEL", "anthropic/claude-sonnet-4"),
        prompt_template="openai",
    ),

    # ── Open-Source / Self-Hosted ──
    "ollama": ProviderConfig(
        name="ollama",
        base_url="http://localhost:11434/v1",
        model_id="llama3.2:3b",
        is_local=True,
        supports_tools=False,       # Depends on model
        supports_json_mode=False,   # Depends on model
    ),
    "llama.cpp": ProviderConfig(
        name="llama.cpp",
        base_url="http://localhost:8080/v1",
        model_id="local-model",
        is_local=True,
        supports_tools=False,
        supports_json_mode=False,
    ),
    "vllm": ProviderConfig(
        name="vllm",
        base_url="http://localhost:8000/v1",
        model_id="local-model",
        is_local=True,
    ),

    # ── Mock (for testing) ──
    "mock": ProviderConfig(
        name="mock",
        base_url="http://localhost:9999/v1",  # never actually called
        model_id="mock-model",
        is_local=True,
        supports_tools=False,
        supports_json_mode=False,
    ),
}


PROVIDER_ALIASES = {
    "opencode": "opencode-go",
    "opencode_go": "opencode-go",
    "openrouter.ai": "openrouter",
    "llamacpp": "llama.cpp",
}


def resolve_provider(spec: str) -> tuple[ProviderConfig, str]:
    """
    Resolve a provider spec like 'ollama/qwen2.5:7b',
    'openrouter/anthropic/claude-sonnet-4', or
    'opencode-go/anthropic/claude-sonnet-4'.

    Returns (ProviderConfig, model_id).
    """
    if not spec:
        spec = os.environ.get("SOM_MODEL", "openrouter/openai/gpt-4o-mini")

    if "/" in spec:
        provider_name, model_id = spec.split("/", 1)
    else:
        provider_name = spec
        provider_name = PROVIDER_ALIASES.get(provider_name, provider_name)
        if provider_name not in PROVIDERS:
            raise ValueError(
                f"Unknown provider '{provider_name}'. Available: {sorted(PROVIDERS.keys())}"
            )
        model_id = os.environ.get(f"{provider_name.upper().replace('-', '_').replace('.', '_')}_MODEL", PROVIDERS[provider_name].model_id)

    provider_name = PROVIDER_ALIASES.get(provider_name, provider_name)

    if provider_name not in PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider_name}'. Available: {sorted(PROVIDERS.keys())}"
        )

    config = PROVIDERS[provider_name]
    resolved = ProviderConfig(**{**config.__dict__})
    resolved.name = provider_name
    return resolved, model_id


class ProviderClient:
    """
    Thin wrapper around the OpenAI client that handles:
    - Retry with exponential backoff
    - Provider-specific headers
    - Tool calling mode detection (native vs XML vs codeblock)
    """

    def __init__(self, provider_spec: str):
        from openai import OpenAI

        config, model_id = resolve_provider(provider_spec)
        self.config = config
        self.model_id = model_id
        self.provider_spec = provider_spec

        self.client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key or "not-needed",
            default_headers=config.default_headers,
        )

    def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        max_retries: int = 3,
    ):
        """
        Call the model with retry. Returns raw OpenAI response object.

        Falls back to XML/codeblock tool mode for models that don't support
        native tool calling.
        """
        kwargs = dict(
            model=self.model_id,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Only pass tools if provider supports native tool calling
        if tools and self.config.supports_tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        for attempt in range(max_retries):
            try:
                return self.client.chat.completions.create(**kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                wait = 2 ** attempt
                print(f"  ⚠ API error (attempt {attempt+1}/{max_retries}): {e}", file=sys.stderr)
                time.sleep(wait)


# ── Mock client for testing ──────────────────────────────────────────

class MockResponse:
    """Simulates an OpenAI API response for testing."""

    def __init__(self, content="", tool_calls=None, finish_reason="stop"):
        self.choices = [MockChoice(content, tool_calls, finish_reason)]
        self.usage = MockUsage()
        self.model = "mock-model"

class MockChoice:
    def __init__(self, content, tool_calls, finish_reason):
        self.message = MockMessage(content, tool_calls or [])
        self.finish_reason = finish_reason

class MockMessage:
    def __init__(self, content, tool_calls):
        self.content = content
        self.tool_calls = tool_calls

class MockUsage:
    prompt_tokens = 100
    completion_tokens = 50
    total_tokens = 150


class MockToolCall:
    """Simulates a tool call in the response."""
    def __init__(self, id, name, arguments):
        self.id = id
        self.function = MockFunction(name, arguments)
    def model_dump(self):
        return {"id": self.id, "type": "function", "function": {"name": self.function.name, "arguments": self.function.arguments}}

class MockFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class MockProviderClient:
    """
    Test client that returns predetermined responses.
    Used for smoke tests without real API keys.
    """

    def __init__(self, responses: list[MockResponse]):
        """
        responses: list of MockResponse objects to return in sequence.
        The last response is reused if more calls are made.
        """
        self.responses = responses
        self.call_count = 0
        self.model_id = "mock-model"
        self.config = PROVIDERS["mock"]

    def chat(self, messages, tools=None, temperature=0.7, max_tokens=4096, max_retries=3):
        """Return the next predetermined response."""
        idx = min(self.call_count, len(self.responses) - 1)
        resp = self.responses[idx]
        self.call_count += 1
        return resp
