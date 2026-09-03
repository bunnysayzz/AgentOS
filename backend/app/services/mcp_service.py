"""MCP Gateway service - LLM provider abstraction, model routing, cost governance (Firestore)."""

import time
import httpx
from datetime import datetime, timezone, timedelta

from app.core.db import FirestoreDB, stamp
from app.models.mcp import LLMProvider
from app.schemas.mcp import ChatCompletionRequest, ChatCompletionResponse
from app.services.provider_service import get_api_key_for_provider, get_provider_config, list_provider_configs
from app.services.provider_metadata import get_fallback_chain, is_rate_limit_error, get_provider_metadata

LLM_CALLS = "llm_calls"
MODEL_REGISTRY = "model_registry"

# ─── Curated MCP server catalog (marketplace) ────────
# Popular, well-maintained reference servers users can wire into their own
# MCP gateways. Config snippets are copy-paste ready for Claude Code / Cursor.
MCP_MARKETPLACE: list[dict] = [
    {
        "id": "filesystem",
        "name": "Filesystem",
        "description": "Read, write, and organize files on the local machine with sandboxed path access.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"],
        "env_vars": [],
        "homepage": "https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem",
        "category": "Files & Storage",
    },
    {
        "id": "github",
        "name": "GitHub",
        "description": "Search repos, read issues and PRs, and manage the GitHub workflow from your agent.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env_vars": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
        "homepage": "https://github.com/modelcontextprotocol/servers/tree/main/src/github",
        "category": "Developer Tools",
    },
    {
        "id": "postgres",
        "name": "PostgreSQL",
        "description": "Query schemas, run read-only SQL, and inspect tables in a Postgres database.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://user:pass@host:5432/db"],
        "env_vars": [],
        "homepage": "https://github.com/modelcontextprotocol/servers/tree/main/src/postgres",
        "category": "Databases",
    },
    {
        "id": "brave-search",
        "name": "Brave Search",
        "description": "Web search with the Brave Search API — fresh, ranked results for research agents.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env_vars": ["BRAVE_API_KEY"],
        "homepage": "https://github.com/modelcontextprotocol/servers/tree/main/src/brave-search",
        "category": "Search & Web",
    },
    {
        "id": "firecrawl",
        "name": "Firecrawl",
        "description": "Crawl and scrape websites into clean markdown for grounding and research.",
        "command": "npx",
        "args": ["-y", "firecrawl-mcp"],
        "env_vars": ["FIRECRAWL_API_KEY"],
        "homepage": "https://github.com/mendableai/firecrawl-mcp-server",
        "category": "Search & Web",
    },
    {
        "id": "playwright",
        "name": "Playwright",
        "description": "Drive a real browser: navigate pages, click, fill forms, and take screenshots.",
        "command": "npx",
        "args": ["-y", "@playwright/mcp@latest"],
        "env_vars": [],
        "homepage": "https://github.com/microsoft/playwright-mcp",
        "category": "Browser & Testing",
    },
    {
        "id": "slack",
        "name": "Slack",
        "description": "Read channels, search messages, and send posts to a Slack workspace.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-slack"],
        "env_vars": ["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"],
        "homepage": "https://github.com/modelcontextprotocol/servers/tree/main/src/slack",
        "category": "Communication",
    },
    {
        "id": "memory",
        "name": "Memory (Knowledge Graph)",
        "description": "Persistent knowledge-graph memory so agents remember facts across sessions.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "env_vars": [],
        "homepage": "https://github.com/modelcontextprotocol/servers/tree/main/src/memory",
        "category": "Memory & Context",
    },
    {
        "id": "fetch",
        "name": "Fetch",
        "description": "Fetch any URL and convert it to markdown for reading by an agent.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-fetch"],
        "env_vars": [],
        "homepage": "https://github.com/modelcontextprotocol/servers/tree/main/src/fetch",
        "category": "Search & Web",
    },
    {
        "id": "sequential-thinking",
        "name": "Sequential Thinking",
        "description": "Structured step-by-step reasoning for complex problems — better than one-shot answers.",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
        "env_vars": [],
        "homepage": "https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking",
        "category": "Reasoning",
    },
]


def list_marketplace() -> list[dict]:
    """Return the curated MCP server catalog."""
    return MCP_MARKETPLACE


# ─── Default model pricing (per 1K tokens in USD) ──

DEFAULT_MODEL_PRICING: dict[str, dict] = {
    "gpt-4o": {"input": 0.0025, "output": 0.01, "context": 128000},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006, "context": 128000},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03, "context": 128000},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015, "context": 16385},
    "o1-preview": {"input": 0.015, "output": 0.06, "context": 128000},
    "o1-mini": {"input": 0.003, "output": 0.012, "context": 128000},
    "claude-3-5-sonnet": {"input": 0.003, "output": 0.015, "context": 200000},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125, "context": 200000},
    "claude-3-opus": {"input": 0.015, "output": 0.075, "context": 200000},
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.005, "context": 1000000},
    "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003, "context": 1000000},
}


# ─── Errors ──────────────────────────────────────────


class MCPError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ModelNotFoundError(MCPError):
    def __init__(self, model: str):
        super().__init__(f"Model '{model}' not found or not available", status_code=404)


# ─── Friendly error translation ───────────────────────
# Provider errors are translated to plain-language messages for the user.
# Raw bodies, URLs and API keys NEVER reach the chat UI.


def _provider_label(provider) -> str:
    """Human-readable label for an LLMProvider value."""
    value = provider.value if hasattr(provider, "value") else str(provider)
    names = {
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "google": "Google Gemini",
        "groq": "Groq",
        "mistral": "Mistral",
        "deepseek": "DeepSeek",
        "openrouter": "OpenRouter",
        "cerebras": "Cerebras",
        "agentrouter": "AgentRouter",
        "ollama": "Ollama",
    }
    if value in names:
        return names[value]
    return value.replace("_", " ").title()


def _friendly_http_error(
    status_code: int,
    provider: str,
    model: str = "",
    body_text: str = "",
) -> str:
    """Map a provider HTTP error to a clear, user-safe message.

    Never includes the raw body, the request URL, or the API key — only the
    provider name, the status code, and (for model problems) the model.
    """
    low = (body_text or "").lower()
    model_problem = "model" in low and any(
        token in low for token in ("not exist", "not found", "not available", "unknown", "access")
    )

    if model_problem and status_code in (400, 403, 404):
        name = model or "selected"
        return (
            f"{_provider_label(provider)} doesn't have the model '{name}' "
            f"(HTTP {status_code}). Pick another model from the list."
        )
    if status_code in (401, 403):
        return (
            f"{_provider_label(provider)} rejected the API key (HTTP {status_code}). "
            "Update the key on the Providers page and try again."
        )
    if status_code == 402:
        return (
            f"{_provider_label(provider)} needs billing or credits (HTTP 402). "
            "Top up your account on the provider's site."
        )
    if status_code == 404:
        return (
            f"{_provider_label(provider)} endpoint not found (HTTP 404). "
            "Check the base URL on the Providers page."
        )
    if status_code == 429 or "rate limit" in low or "quota" in low or "resource_exhausted" in low:
        return (
            f"{_provider_label(provider)} hit a rate or quota limit (HTTP {status_code}). "
            "Wait a moment and try again."
        )
    if status_code == 400:
        return f"{_provider_label(provider)} rejected the request (HTTP 400). Try a different prompt."
    if status_code >= 500:
        return f"{_provider_label(provider)} is having server issues (HTTP {status_code}). Try again shortly."
    return f"{_provider_label(provider)} request failed (HTTP {status_code})."


def _check_provider_response(
    resp: httpx.Response,
    provider: str,
    model: str = "",
) -> None:
    """Raise a friendly MCPError for non-2xx provider responses."""
    if resp.status_code < 400:
        return
    try:
        body = resp.text[:500]
    except Exception:
        body = ""
    raise MCPError(
        _friendly_http_error(resp.status_code, provider, model, body),
        status_code=resp.status_code,
    )


def _connect_error_message(provider: str, exc: Exception) -> str:
    """Plain-language transport failure (no URLs, no raw bodies, no keys)."""
    name = _provider_label(provider)
    low = str(exc).lower()
    if "timeout" in low or "timed out" in low:
        return f"{name} timed out. Try again in a moment."
    if "resolve" in low or "dns" in low or "connection" in low:
        return (
            f"Couldn't reach {name}. Check the base URL on the Providers page, "
            "or try again later."
        )
    return f"Couldn't reach {name}. Try again in a moment."


def _raise_connect_error(provider: str, exc: Exception) -> None:
    """Raise a friendly MCPError for transport/connection failures."""
    message = _connect_error_message(provider, exc)
    raise MCPError(message, 504 if "timed out" in message.lower() else 502)


def _provider_from_url(base_url: str) -> str:
    """Best-effort provider id from an OpenAI-compatible base URL."""
    host = (base_url or "").lower()
    for name in (
        "openai", "anthropic", "google", "groq", "mistral", "deepseek",
        "openrouter", "cerebras", "ollama", "agentrouter",
    ):
        if name in host:
            return name
    return "this provider"


# ─── Model Registry ────────────────────────────────


async def get_available_models(
    db: FirestoreDB, provider: LLMProvider | None = None
) -> list[dict]:
    """List all available models, optionally filtered by provider."""
    rows = [
        r for r in db.query(MODEL_REGISTRY)
        if r.get("is_active") and not r.get("is_deprecated") and not r.get("deleted_at")
        and (provider is None or r.get("provider") == provider.value)
    ]
    rows.sort(key=lambda r: (r.get("provider") or "", r.get("model_name") or ""))
    return rows


async def seed_default_models(db: FirestoreDB) -> int:
    """Seed default model pricing into the registry if empty."""
    if db.count(MODEL_REGISTRY) > 0:
        return 0

    count = 0
    for model_key, pricing in DEFAULT_MODEL_PRICING.items():
        provider = LLMProvider.OPENAI
        if model_key.startswith("claude"):
            provider = LLMProvider.ANTHROPIC
        elif model_key.startswith("gemini"):
            provider = LLMProvider.GOOGLE

        model = stamp({
            "provider": provider.value,
            "model_name": model_key,
            "input_price_per_1k": pricing["input"],
            "output_price_per_1k": pricing["output"],
            "context_window": pricing["context"],
            "max_output_tokens": 8192,
            "is_active": True,
            "is_deprecated": False,
            "capabilities": ["chat", "function_calling", "streaming"],
            "description": None,
            "registry_metadata": None,
        })
        db.add(MODEL_REGISTRY, model)
        count += 1
    return count


def calculate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate the cost of an LLM call based on token usage."""
    pricing = DEFAULT_MODEL_PRICING.get(model_name, {"input": 0.01, "output": 0.03})
    input_cost = (prompt_tokens / 1000) * pricing["input"]
    output_cost = (completion_tokens / 1000) * pricing["output"]
    return round(input_cost + output_cost, 6)


def _record_call(
    db: FirestoreDB,
    workspace_id: str | None,
    agent_id: str | None,
    execution_id: str | None,
    provider: LLMProvider,
    model_name: str,
    system_prompt: str | None,
    messages: list[dict],
    temperature: float,
    max_tokens: int | None,
    response_content: str,
    finish_reason: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    duration_ms: int,
    is_error: bool,
    error_message: str | None,
    is_streaming: bool,
) -> dict:
    """Persist an LLM call record to Firestore."""
    call = stamp({
        "workspace_id": str(workspace_id) if workspace_id else None,
        "agent_id": str(agent_id) if agent_id else None,
        "execution_id": str(execution_id) if execution_id else None,
        "provider": provider.value,
        "model_name": model_name,
        "system_prompt": system_prompt,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_content": response_content,
        "finish_reason": finish_reason,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost_usd": cost_usd,
        "duration_ms": duration_ms,
        "is_cached": False,
        "is_error": is_error,
        "error_message": error_message,
        "is_streaming": is_streaming,
    })
    db.add(LLM_CALLS, call)
    return call


# Providers that use native (non-OpenAI) API formats
_NATIVE_PROVIDERS = {LLMProvider.ANTHROPIC, LLMProvider.GOOGLE}


def _is_native_provider(provider: LLMProvider) -> bool:
    """Check if a provider uses a native (non-OpenAI) API format."""
    return provider in _NATIVE_PROVIDERS


def _clean_messages(messages: list[dict]) -> list[dict]:
    """Strip null-only keys (name/tool_calls/tool_call_id) from message dicts.

    Pydantic's model_dump() emits ``name: null``, ``tool_calls: null`` and
    ``tool_call_id: null`` for plain user/system messages. Groq and Cerebras
    reject those with HTTP 400 ("Value is not nullable"), so drop them before
    sending to any OpenAI-compatible endpoint.
    """
    cleaned = []
    for m in messages:
        if not isinstance(m, dict):
            cleaned.append(m)
            continue
        # Drop None and empty-string values (OpenAI tool-calling assistant
        # messages carry ``content: null`` — an empty string can 400 on some
        # providers like Groq).
        cleaned.append({k: v for k, v in m.items() if v is not None and v != ""})
    return cleaned


# ─── Real LLM API Calls ────────────────────────────


async def _call_openai_compatible(
    api_key: str,
    messages: list[dict],
    model: str,
    temperature: float,
    max_tokens: int | None,
    base_url: str = "https://api.openai.com/v1",
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
    provider: str = "",
) -> dict:
    """Call an OpenAI-compatible chat completions API."""
    body = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens:
        body["max_tokens"] = max_tokens
    if tools:
        body["tools"] = tools
    if tool_choice:
        body["tool_choice"] = tool_choice

    url = _pick_stream_url(base_url)
    provider = provider or _provider_from_url(base_url)

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
            )
    except httpx.HTTPError as exc:
        _raise_connect_error(provider, exc)
    _check_provider_response(r, provider, model)
    return r.json()


async def _call_anthropic(
    api_key: str, messages: list[dict], model: str, temperature: float, max_tokens: int | None
) -> dict:
    """Call Anthropic messages API."""
    system = None
    chat_messages = []
    for m in messages:
        if m["role"] == "system":
            system = m["content"]
        else:
            chat_messages.append(m)

    body = {
        "model": model,
        "messages": chat_messages,
        "temperature": temperature,
        "max_tokens": max_tokens or 1024,
    }
    if system:
        body["system"] = system

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=body,
            )
    except httpx.HTTPError as exc:
        _raise_connect_error("anthropic", exc)
    _check_provider_response(r, "anthropic", model)
    data = r.json()
    return {
        "id": data["id"],
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": data["content"][0]["text"]},
            "finish_reason": data["stop_reason"],
        }],
        "usage": {
            "prompt_tokens": data["usage"]["input_tokens"],
            "completion_tokens": data["usage"]["output_tokens"],
            "total_tokens": data["usage"]["input_tokens"] + data["usage"]["output_tokens"],
        },
    }


def _mask_key(key: str) -> str:
    """Mask an API key so only the first 6 and last 4 characters are visible."""
    if not key or len(key) <= 12:
        return "****"
    return f"{key[:6]}{'*' * (len(key) - 10)}{key[-4:]}"


async def _call_google(
    api_key: str, messages: list[dict], model: str, temperature: float, max_tokens: int | None
) -> dict:
    """Call Google Gemini API."""
    contents = []
    for m in messages:
        if m["role"] in ("user", "assistant"):
            contents.append({"role": m["role"], "parts": [{"text": m["content"]}]})

    body = {"contents": contents, "generationConfig": {"temperature": temperature}}
    if max_tokens:
        body["generationConfig"]["maxOutputTokens"] = max_tokens

    # The key travels in the ``x-goog-api-key`` header, never in the URL, so
    # transport errors and logs can't leak it.
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json=body, headers={"x-goog-api-key": api_key})
    except httpx.HTTPError as exc:
        _raise_connect_error("google", exc)
    _check_provider_response(r, "google", model)
    data = r.json()
    candidate = data.get("candidates", [{}])[0]
    content = candidate.get("content", {})
    parts = content.get("parts", [{}])
    text = parts[0].get("text", "") if parts else ""
    usage = data.get("usageMetadata", {})
    return {
        "id": f"gemini-{datetime.now(timezone.utc).timestamp()}",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": text},
            "finish_reason": candidate.get("finishReason", "stop"),
        }],
        "usage": {
            "prompt_tokens": usage.get("promptTokenCount", 0),
            "completion_tokens": usage.get("candidatesTokenCount", 0),
            "total_tokens": usage.get("totalTokenCount", 0),
        },
    }


# ─── Chat/Completion ───────────────────────────────


def _build_system_message(messages) -> str | None:
    """Extract system message from messages array."""
    for msg in messages:
        if msg.role == "system":
            return msg.content
    return None


def _get_model_for_provider(provider: LLMProvider) -> str | None:
    """Get the default model name for a provider."""
    model_map = {
        LLMProvider.OPENAI: "gpt-4o-mini",
        LLMProvider.ANTHROPIC: "claude-3-5-haiku-20241022",
        LLMProvider.GOOGLE: "gemini-2.0-flash",
        LLMProvider.GOOGLE_VERTEX: "gemini-2.0-flash",
        LLMProvider.GROQ: "llama-3.3-70b-versatile",
        LLMProvider.CEREBRAS: "gpt-oss-120b",
        LLMProvider.OPENROUTER: "meta-llama/llama-3.3-70b-instruct:free",
        LLMProvider.MISTRAL: "open-mistral-nemo",
        LLMProvider.HUGGINGFACE: "meta-llama/Llama-3.3-70B-Instruct",
        LLMProvider.DEEPSEEK: "deepseek-chat",
        LLMProvider.AGENTROUTER: "deepseek/deepseek-v4-flash",
        LLMProvider.OLLAMA: "llama3.2",
        LLMProvider.XAI: "grok-2-1212",
        LLMProvider.COHERE: "command-r-plus",
        LLMProvider.PERPLEXITY: "sonar-pro",
        LLMProvider.TOGETHERAI: "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        LLMProvider.FIREWORKS: "accounts/fireworks/models/llama-v3p3-70b-instruct",
        LLMProvider.DEEPINFRA: "meta-llama/Meta-Llama-3.1-70B-Instruct",
        LLMProvider.NVIDIA_NIM: "meta/llama-3.1-8b-instruct",
        LLMProvider.NOVITA: "meta-llama/llama-3.3-70b-instruct",
        LLMProvider.SAMBANOVA: "Meta-Llama-3.3-70B-Instruct",
        LLMProvider.HYPERBOLIC: "meta-llama/Meta-Llama-3.1-70B-Instruct",
        LLMProvider.DATABRICKS: "databricks-meta-llama-3-1-70b-instruct",
        LLMProvider.DIGITALOCEAN: "llama-3.3-70b",
        LLMProvider.MOONSHOTAI: "moonshot-v1-128k",
        LLMProvider.VENICE: "llama-3.3-70b",
        LLMProvider.POOLSIDE: "poolside-1b",
        LLMProvider.IO_NET: "meta-llama/Meta-Llama-3.1-70B-Instruct",
        LLMProvider.NEBIUS: "meta-llama/Meta-Llama-3.1-70B-Instruct",
        LLMProvider.SCALEWAY: "llama-3.3-70b-instruct",
        LLMProvider.OVHCLOUD: "Meta-Llama-3.1-70B-Instruct",
        LLMProvider.SNOWFLAKE: "claude-3-5-sonnet",
        LLMProvider.HELICONE: "gpt-4o",
        LLMProvider.MODAL: "meta-llama/Meta-Llama-3.1-70B-Instruct",
        LLMProvider.BASETEN: "meta-llama/Meta-Llama-3.1-70B-Instruct",
        LLMProvider.CORTECS: "kimi-k2-instruct",
        LLMProvider.LLAMA: "llama-3.3-70b",
        LLMProvider.UPSTAGE: "solar-pro-2-preview",
        LLMProvider.SILICONFLOW: "meta-llama/Meta-Llama-3.1-70B-Instruct",
        LLMProvider.ALIBABA: "qwen-max",
        LLMProvider.TENCENT: "hunyuan-pro",
        LLMProvider.Z_AI: "glm-4-plus",
        LLMProvider.ZHIPU_ZAI: "glm-4-plus",
        LLMProvider.STEPFUN: "step-2-16k",
        LLMProvider.FRIENDLI: "meta-llama-3.3-70b-instruct",
        LLMProvider.CRUSOE: "meta-llama/Meta-Llama-3.1-70B-Instruct",
        LLMProvider.MEGANOVA: "llama-3.3-70b",
        LLMProvider.CHUTES: "meta-llama/Meta-Llama-3.1-70B-Instruct",
        LLMProvider.KILO: "gpt-4o",
        LLMProvider.AI_302: "gpt-4o",
        LLMProvider.ABACUS: "gpt-4o",
        LLMProvider.ANYAPI: "gpt-4o",
        LLMProvider.REGOLO: "gpt-4o",
        LLMProvider.REQUESTY: "gpt-4o",
        LLMProvider.ZENMUX: "gpt-4o",
        LLMProvider.SARVAM: "sarvam-m",
        LLMProvider.SCX_AI: "gpt-4o",
        LLMProvider.INFERENCE: "meta-llama/Meta-Llama-3.1-70B-Instruct",
        LLMProvider.GITHUB_COPILOT: "gpt-4o",
        LLMProvider.CLOUDFLARE_AI_GATEWAY: "gpt-4o",
        LLMProvider.GITLAB: "duo-chat-sonnet-4-5",
        LLMProvider.WATSONX: "ibm-granite/granite-3-8b-instruct",
        LLMProvider.AZURE: "gpt-4o",
        LLMProvider.AZURE_COGNITIVE: "gpt-4o",
        LLMProvider.OLLAMA_CLOUD: "llama3.3",
        LLMProvider.OPENCODE: "gpt-4o",
        LLMProvider.XIAOMI: "MiMo-7B-RL",
    }
    return model_map.get(provider)


async def _enforce_hard_limit(db: FirestoreDB, workspace_id: str | None) -> None:
    """Block an LLM call when the workspace's hard budget limit is exceeded.

    Only kicks in for workspace-scoped calls where a budget with
    ``hard_limit`` is configured (a single workspace-doc read otherwise), so
    the common path stays cheap.
    """
    if not workspace_id:
        return
    from app.services import budget_service

    budget = budget_service.get_budget_settings(db, str(workspace_id))
    if not budget.get("hard_limit"):
        return
    if budget.get("monthly_limit_usd") is None and budget.get("daily_limit_usd") is None:
        return

    result = budget_service.check_budget(db, str(workspace_id))
    if result.get("blocked"):
        raise MCPError(
            "Workspace budget exceeded — calls are blocked by the hard spending limit. "
            "Raise the limit or disable the hard limit in the Budget page.",
            status_code=402,
        )


async def route_chat_completion(
    db: FirestoreDB,
    request: ChatCompletionRequest,
    workspace_id: str | None = None,
    agent_id: str | None = None,
    execution_id: str | None = None,
    use_fallback: bool = True,
    preferred_provider: LLMProvider | None = None,
) -> ChatCompletionResponse:
    """Route a chat completion request to the appropriate LLM provider.

    ``preferred_provider`` pins the first provider to try (used by agent and
    workflow execution so an agent's declared provider is honored); the
    normal model-prefix detection + fallback chain still applies afterwards.
    """
    await _enforce_hard_limit(db, workspace_id)
    model_name = request.model
    system_prompt = _build_system_message(request.messages)
    temperature = request.temperature if request.temperature is not None else 0.7

    primary_provider = LLMProvider.OPENAI
    if model_name.startswith("claude"):
        primary_provider = LLMProvider.ANTHROPIC
    elif model_name.startswith("gemini"):
        primary_provider = LLMProvider.GOOGLE
    elif model_name.startswith("ollama"):
        primary_provider = LLMProvider.OLLAMA
    elif model_name.startswith("deepseek"):
        primary_provider = LLMProvider.DEEPSEEK

    fallback_providers: list[LLMProvider] = []
    if use_fallback:
        all_configs = await list_provider_configs(db)
        configured_slugs = [c.get("provider") for c in all_configs if c.get("is_active")]
        fallback_chain = get_fallback_chain(configured_slugs, model_name=model_name)
        fallback_providers = [
            LLMProvider(slug) for slug in fallback_chain
            if slug in configured_slugs
        ]
        if primary_provider.value in configured_slugs:
            if primary_provider in fallback_providers:
                fallback_providers.remove(primary_provider)
            fallback_providers.insert(0, primary_provider)

    # Honoring the agent's declared provider: make it first in line.
    if preferred_provider is not None and preferred_provider.value in [
        c.get("provider") for c in (await list_provider_configs(db)) if c.get("is_active")
    ]:
        if preferred_provider in fallback_providers:
            fallback_providers.remove(preferred_provider)
        fallback_providers.insert(0, preferred_provider)

    providers_to_try = fallback_providers if use_fallback else [primary_provider]
    if not providers_to_try:
        providers_to_try = [primary_provider]

    last_error = None
    messages_dict: list[dict] = _clean_messages([m.model_dump() for m in request.messages])

    for attempt_idx, provider in enumerate(providers_to_try):
        provider_config = await get_provider_config(db, provider)
        api_key = get_api_key_for_provider(provider_config)
        is_fallback = provider != primary_provider
        if not api_key:
            continue  # Skip if no key configured for this provider

        start_time = time.monotonic()

        try:
            messages_dict = _clean_messages([m.model_dump() for m in request.messages])

            actual_model = model_name
            if is_fallback:
                default_model = _get_model_for_provider(provider)
                actual_model = default_model or model_name

            if not _is_native_provider(provider):
                # All OpenAI-compatible providers (172+ from models.dev)
                base_url = (provider_config.get("base_url") if provider_config else None) or ""
                if not base_url:
                    meta = get_provider_metadata(provider)
                    base_url = meta.get("base_url") or ""
                if not base_url:
                    base_url = "https://api.openai.com/v1"

                result = await _call_openai_compatible(
                    api_key=api_key,
                    messages=messages_dict,
                    model=actual_model,
                    temperature=temperature,
                    max_tokens=request.max_tokens,
                    base_url=base_url,
                )
                response_content = result["choices"][0]["message"]["content"]
                prompt_tokens = result["usage"].get("prompt_tokens", 10)
                completion_tokens = result["usage"].get("completion_tokens", 10)
                finish_reason = result["choices"][0].get("finish_reason", "stop")

            elif provider == LLMProvider.ANTHROPIC:
                result = await _call_anthropic(api_key, messages_dict, actual_model, temperature, request.max_tokens)
                response_content = result["choices"][0]["message"]["content"]
                prompt_tokens = result["usage"]["prompt_tokens"]
                completion_tokens = result["usage"]["completion_tokens"]
                finish_reason = result["choices"][0].get("finish_reason", "stop")

            elif provider == LLMProvider.GOOGLE:
                result = await _call_google(api_key, messages_dict, actual_model, temperature, request.max_tokens)
                response_content = result["choices"][0]["message"]["content"]
                prompt_tokens = result["usage"]["prompt_tokens"]
                completion_tokens = result["usage"]["completion_tokens"]
                finish_reason = result["choices"][0].get("finish_reason", "stop")

            else:
                # Every other provider is OpenAI-compatible. Fall back to the
                # provider's metadata base URL when one wasn't stored (matches
                # test_connection), so all 30+ providers can actually chat.
                base_url = (provider_config.get("base_url") if provider_config else None) or ""
                if not base_url:
                    base_url = get_provider_metadata(provider).get("base_url") or ""
                if base_url:
                    result = await _call_openai_compatible(
                        api_key=api_key,
                        messages=messages_dict,
                        model=actual_model,
                        temperature=temperature,
                        max_tokens=request.max_tokens,
                        base_url=base_url,
                    )
                    response_content = result["choices"][0]["message"]["content"]
                    prompt_tokens = result["usage"].get("prompt_tokens", 10)
                    completion_tokens = result["usage"].get("completion_tokens", 10)
                    finish_reason = result["choices"][0].get("finish_reason", "stop")
                else:
                    raise MCPError(
                        f"Provider '{provider.value}' has no base URL configured. "
                        "Set a base URL in the Providers page, or choose a different provider.",
                        status_code=400,
                    )

            duration_ms = int((time.monotonic() - start_time) * 1000)
            total_tokens = prompt_tokens + completion_tokens
            cost_usd = calculate_cost(actual_model, prompt_tokens, completion_tokens)

            llm_call = _record_call(
                db, workspace_id, agent_id, execution_id,
                provider, actual_model, system_prompt,
                messages_dict,
                temperature, request.max_tokens,
                response_content, finish_reason,
                prompt_tokens, completion_tokens, cost_usd,
                duration_ms, False, None, request.stream,
            )

            return ChatCompletionResponse(
                id=f"chatcmpl-{llm_call['id']}",
                model=actual_model,
                provider=provider,
                choices=[{
                    "index": 0,
                    "message": {"role": "assistant", "content": response_content},
                    "finish_reason": finish_reason,
                }],
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                },
                cost_usd=cost_usd,
                created=datetime.now(timezone.utc),
            )

        except Exception as e:
            if isinstance(e, httpx.HTTPError):
                error_str = _connect_error_message(provider, e)
            else:
                error_str = str(e)
                # Mask any API keys that might appear in error messages
                for sensitive in [api_key, api_key[:8] if api_key else ""]:
                    if sensitive and len(sensitive) > 4:
                        error_str = error_str.replace(sensitive, _mask_key(sensitive))
            last_error = error_str

            duration_ms = int((time.monotonic() - start_time) * 1000)
            _record_call(
                db, workspace_id, agent_id, execution_id,
                provider, model_name, system_prompt,
                messages_dict,
                temperature, request.max_tokens,
                "", "error", 0, 0, 0.0, duration_ms,
                True, f"Fallback from {provider.value}: {error_str}", request.stream,
            )

            if is_fallback or (is_rate_limit_error(error_str) and len(providers_to_try) > 1):
                continue
            break

    # All providers failed — return simulated response with error info
    last_user_msg = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            last_user_msg = msg.content[:100]
            break

    response_content = (
        f"⚠️ All providers unavailable. "
        f"Last error: {last_error or 'No configured providers'}. "
        f"Your message: '{last_user_msg}...'"
    )
    prompt_tokens = max(len(str([m.model_dump() for m in request.messages])) // 4, 10)
    completion_tokens = max(len(response_content) // 4, 10)
    total_tokens = prompt_tokens + completion_tokens
    cost_usd = calculate_cost(model_name, prompt_tokens, completion_tokens)

    llm_call = _record_call(
        db, workspace_id, agent_id, execution_id,
        primary_provider, model_name, system_prompt,
        [m.model_dump() for m in request.messages],
        temperature, request.max_tokens,
        response_content, "stop", prompt_tokens, completion_tokens, cost_usd,
        0, True, f"All providers failed. Last: {last_error}", request.stream,
    )

    return ChatCompletionResponse(
        id=f"chatcmpl-{llm_call['id']}",
        model=model_name,
        provider=primary_provider,
        choices=[{
            "index": 0,
            "message": {"role": "assistant", "content": response_content},
            "finish_reason": "stop",
        }],
        usage={"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": total_tokens},
        cost_usd=cost_usd,
        created=datetime.now(timezone.utc),
    )


def _detect_primary_provider(model_name: str) -> LLMProvider:
    """Detect the primary provider from a model-name prefix."""
    if model_name.startswith("claude"):
        return LLMProvider.ANTHROPIC
    if model_name.startswith("gemini"):
        return LLMProvider.GOOGLE
    if model_name.startswith("ollama"):
        return LLMProvider.OLLAMA
    if model_name.startswith("deepseek"):
        return LLMProvider.DEEPSEEK
    if model_name.startswith("grok"):
        return LLMProvider.XAI
    if model_name.startswith("gpt"):
        return LLMProvider.OPENAI
    if model_name.startswith("llama"):
        return LLMProvider.GROQ
    if model_name.startswith("mistral"):
        return LLMProvider.MISTRAL
    if model_name.startswith("command"):
        return LLMProvider.COHERE
    if model_name.startswith("sonar"):
        return LLMProvider.PERPLEXITY
    if model_name.startswith("qwen"):
        return LLMProvider.ALIBABA
    if model_name.startswith("glm"):
        return LLMProvider.ZHIPU_ZAI
    if model_name.startswith("solar"):
        return LLMProvider.UPSTAGE
    if model_name.startswith("step"):
        return LLMProvider.STEPFUN
    if model_name.startswith("hunyuan"):
        return LLMProvider.TENCENT
    return LLMProvider.OPENAI


async def _resolve_provider_chain(
    db: FirestoreDB,
    model_name: str,
    preferred_provider: LLMProvider | None = None,
) -> tuple[list[LLMProvider], LLMProvider]:
    """Ordered providers to try (preferred → detected primary → priority chain)
    plus the detected primary provider."""
    primary_provider = _detect_primary_provider(model_name)
    all_configs = await list_provider_configs(db)
    configured_slugs = [c.get("provider") for c in all_configs if c.get("is_active")]

    fallback_chain = get_fallback_chain(configured_slugs, model_name=model_name)
    fallback_providers = [
        LLMProvider(slug) for slug in fallback_chain if slug in configured_slugs
    ]
    if primary_provider.value in configured_slugs:
        if primary_provider in fallback_providers:
            fallback_providers.remove(primary_provider)
        fallback_providers.insert(0, primary_provider)
    if preferred_provider is not None and preferred_provider.value in configured_slugs:
        if preferred_provider in fallback_providers:
            fallback_providers.remove(preferred_provider)
        fallback_providers.insert(0, preferred_provider)

    return (fallback_providers or [primary_provider]), primary_provider


async def route_chat_completion_raw(
    db: FirestoreDB,
    request: ChatCompletionRequest,
    workspace_id: str | None = None,
    agent_id: str | None = None,
    execution_id: str | None = None,
    preferred_provider: LLMProvider | None = None,
    tools: list[dict] | None = None,
) -> dict:
    """Like ``route_chat_completion`` but returns the raw first-choice message
    (content **and** ``tool_calls``) so callers can run a tool-calling loop.

    Only OpenAI-compatible providers receive the ``tools`` array (Anthropic and
    Google use different tool formats); those providers just answer without
    tools. The call is recorded in the ledger, and a ``MCPError`` is raised if
    every configured provider fails.
    """
    await _enforce_hard_limit(db, workspace_id)
    model_name = request.model
    system_prompt = _build_system_message(request.messages)
    temperature = request.temperature if request.temperature is not None else 0.7
    messages_dict = _clean_messages([m.model_dump() for m in request.messages])

    providers_to_try, _primary = await _resolve_provider_chain(db, model_name, preferred_provider)
    last_error = None

    for attempt_idx, provider in enumerate(providers_to_try):
        provider_config = await get_provider_config(db, provider)
        api_key = get_api_key_for_provider(provider_config)
        is_fallback = provider != primary_provider
        if not api_key:
            continue

        start_time = time.monotonic()
        actual_model = model_name
        if is_fallback:
            actual_model = _get_model_for_provider(provider) or model_name

        try:
            messages_dict = _clean_messages([m.model_dump() for m in request.messages])

            if not _is_native_provider(provider):
                # All OpenAI-compatible providers (172+ from models.dev)
                base_url = (provider_config.get("base_url") if provider_config else None) or ""
                if not base_url:
                    meta = get_provider_metadata(provider)
                    base_url = meta.get("base_url") or ""
                if not base_url:
                    base_url = "https://api.openai.com/v1"
                result = await _call_openai_compatible(
                    api_key=api_key, messages=messages_dict, model=actual_model,
                    temperature=temperature, max_tokens=request.max_tokens,
                    base_url=base_url, tools=tools,
                )
            elif provider == LLMProvider.ANTHROPIC:
                result = await _call_anthropic(api_key, messages_dict, actual_model, temperature, request.max_tokens)
            elif provider == LLMProvider.GOOGLE:
                result = await _call_google(api_key, messages_dict, actual_model, temperature, request.max_tokens)
            else:
                base_url = (provider_config.get("base_url") if provider_config else None) or ""
                if not base_url:
                    base_url = get_provider_metadata(provider).get("base_url") or ""
                if not base_url:
                    raise MCPError(
                        f"Provider '{provider.value}' has no base URL configured. "
                        "Set a base URL in the Providers page, or choose a different provider.",
                        status_code=400,
                    )
                result = await _call_openai_compatible(
                    api_key=api_key, messages=messages_dict, model=actual_model,
                    temperature=temperature, max_tokens=request.max_tokens,
                    base_url=base_url, tools=tools,
                )

            choice = (result.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            usage = result.get("usage") or {}
            prompt_tokens = usage.get("prompt_tokens") or 0
            completion_tokens = usage.get("completion_tokens") or 0
            cost_usd = calculate_cost(actual_model, prompt_tokens, completion_tokens)

            _record_call(
                db, workspace_id, agent_id, execution_id,
                provider, actual_model, system_prompt, messages_dict,
                temperature, request.max_tokens,
                message.get("content") or "", choice.get("finish_reason") or "stop",
                prompt_tokens, completion_tokens, cost_usd,
                int((time.monotonic() - start_time) * 1000), False, None, False,
            )

            return {
                "provider": provider.value,
                "model": actual_model,
                "message": message,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
                "cost_usd": cost_usd,
            }
        except Exception as e:
            last_error = str(e)
            if is_fallback or (is_rate_limit_error(str(e)) and len(providers_to_try) > 1):
                continue
            break

    raise MCPError(last_error or "No configured providers", status_code=503)


# ─── Streaming ──────────────────────────────────────


def _pick_stream_url(base_url: str) -> str:
    """Append ``/chat/completions`` to an OpenAI-compatible base URL unless the
    base URL already names a chat endpoint (e.g. API Free LLM's ``/chat``)."""
    url = base_url.rstrip("/")
    if not (url.endswith("chat/completions") or url.endswith("/chat")):
        url += "/chat/completions"
    return url


async def _stream_openai_compatible(
    api_key: str,
    messages: list[dict],
    model: str,
    temperature: float,
    max_tokens: int | None,
    base_url: str,
    provider: str = "",
):
    """Stream an OpenAI-compatible chat completion.

    Yields ``{"type": "delta", "content": str}`` for each text token and
    ``{"type": "usage", ...}`` when the provider reports token usage.
    """
    import json as _json

    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if max_tokens:
        body["max_tokens"] = max_tokens

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            _pick_stream_url(base_url),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        ) as resp:
            if resp.status_code != 200:
                raw = (await resp.aread()).decode(errors="replace")
                raise MCPError(
                    _friendly_http_error(
                        resp.status_code, provider or _provider_from_url(base_url), model, raw
                    ),
                    resp.status_code,
                )

            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload or payload == "[DONE]":
                    continue
                try:
                    obj = _json.loads(payload)
                except ValueError:
                    continue

                choices = obj.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield {"type": "delta", "content": content}

                usage = obj.get("usage")
                if usage and usage.get("total_tokens"):
                    yield {
                        "type": "usage",
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    }


async def stream_chat_completion(
    db: FirestoreDB,
    request: ChatCompletionRequest,
    workspace_id: str | None = None,
    agent_id: str | None = None,
    execution_id: str | None = None,
    preferred_provider: LLMProvider | None = None,
):
    """Stream a chat completion to an LLM provider.

    Yields SSE payload dicts: ``{"type": "delta", "content": ...}`` for text,
    ``{"type": "usage", ...}`` for token counts (when reported), and finally
    ``{"type": "done", "model", "provider", "usage", "cost_usd"}``. On total
    failure yields ``{"type": "error", "message": ...}``. The call is recorded
    in the LLM-call ledger exactly like the non-streaming path.
    """
    try:
        await _enforce_hard_limit(db, workspace_id)
    except MCPError as e:
        yield {"type": "error", "message": e.message}
        return
    model_name = request.model
    system_prompt = _build_system_message(request.messages)
    temperature = request.temperature if request.temperature is not None else 0.7
    messages_dict = _clean_messages([m.model_dump() for m in request.messages])

    # Provider resolution mirrors route_chat_completion: preferred provider →
    # model-prefix detection → configured fallback priority chain.
    providers_to_try, primary_provider = await _resolve_provider_chain(
        db, model_name, preferred_provider
    )
    last_error = None

    for attempt_idx, provider in enumerate(providers_to_try):
        provider_config = await get_provider_config(db, provider)
        api_key = get_api_key_for_provider(provider_config)
        is_fallback = provider != primary_provider
        if not api_key:
            continue  # Skip providers without a configured key
        start_time = time.monotonic()

        actual_model = model_name
        if is_fallback:
            actual_model = _get_model_for_provider(provider) or model_name

        prompt_tokens = 0
        completion_tokens = 0
        chunks: list[str] = []

        try:
            if not _is_native_provider(provider):
                # All OpenAI-compatible providers (172+ from models.dev)
                base_url = (provider_config.get("base_url") if provider_config else None) or ""
                if not base_url:
                    base_url = get_provider_metadata(provider).get("base_url") or ""
                if not base_url:
                    base_url = "https://api.openai.com/v1"

                async for evt in _stream_openai_compatible(
                    api_key=api_key, messages=messages_dict, model=actual_model,
                    temperature=temperature, max_tokens=request.max_tokens, base_url=base_url,
                ):
                    if evt["type"] == "usage":
                        prompt_tokens = evt["prompt_tokens"]
                        completion_tokens = evt["completion_tokens"]
                    elif evt["type"] == "delta":
                        chunks.append(evt["content"])
                        yield evt

            elif provider == LLMProvider.ANTHROPIC:
                # Anthropic SSE is a different format; do a single-shot call and
                # emit its text as one delta (still token-streamed to the client
                # in one chunk, with real usage recorded).
                result = await _call_anthropic(api_key, messages_dict, actual_model, temperature, request.max_tokens)
                prompt_tokens = result["usage"]["prompt_tokens"]
                completion_tokens = result["usage"]["completion_tokens"]
                content = result["choices"][0]["message"]["content"]
                chunks.append(content)
                yield {"type": "delta", "content": content}

            elif provider == LLMProvider.GOOGLE:
                result = await _call_google(api_key, messages_dict, actual_model, temperature, request.max_tokens)
                prompt_tokens = result["usage"]["prompt_tokens"]
                completion_tokens = result["usage"]["completion_tokens"]
                content = result["choices"][0]["message"]["content"]
                chunks.append(content)
                yield {"type": "delta", "content": content}

            else:
                base_url = (provider_config.get("base_url") if provider_config else None) or ""
                if not base_url:
                    base_url = get_provider_metadata(provider).get("base_url") or ""
                if not base_url:
                    raise MCPError(
                        f"Provider '{provider.value}' has no base URL configured. "
                        "Set a base URL in the Providers page, or choose a different provider.",
                        status_code=400,
                    )
                async for evt in _stream_openai_compatible(
                    api_key=api_key, messages=messages_dict, model=actual_model,
                    temperature=temperature, max_tokens=request.max_tokens, base_url=base_url,
                ):
                    if evt["type"] == "usage":
                        prompt_tokens = evt["prompt_tokens"]
                        completion_tokens = evt["completion_tokens"]
                    elif evt["type"] == "delta":
                        chunks.append(evt["content"])
                        yield evt

            duration_ms = int((time.monotonic() - start_time) * 1000)
            # Some OpenAI-compatible endpoints ignore ``include_usage``; if we
            # never got real usage, fall back to a rough token estimate (mirrors
            # the non-streaming path) so cost tracking stays meaningful.
            if prompt_tokens == 0 and completion_tokens == 0:
                joined = "".join(chunks)
                prompt_tokens = max(len(str([m.model_dump() for m in request.messages])) // 4, 10)
                completion_tokens = max(len(joined) // 4, 10)
            cost_usd = calculate_cost(actual_model, prompt_tokens, completion_tokens)

            _record_call(
                db, workspace_id, agent_id, execution_id,
                provider, actual_model, system_prompt, messages_dict,
                temperature, request.max_tokens,
                "".join(chunks), "stop",
                prompt_tokens, completion_tokens, cost_usd,
                duration_ms, False, None, True,
            )

            yield {
                "type": "done",
                "model": actual_model,
                "provider": provider.value,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
                "cost_usd": cost_usd,
            }
            return

        except Exception as e:
            if isinstance(e, httpx.HTTPError):
                error_str = _connect_error_message(provider, e)
            else:
                error_str = str(e)
                # Mask any API keys that might appear in error messages
                for sensitive in [api_key, api_key[:8] if api_key else ""]:
                    if sensitive and len(sensitive) > 4:
                        error_str = error_str.replace(sensitive, _mask_key(sensitive))
            last_error = error_str
            if is_fallback or (is_rate_limit_error(error_str) and len(providers_to_try) > 1):
                continue
            break

    # Record the total failure in the ledger for observability.
    try:
        _record_call(
            db, workspace_id, agent_id, execution_id,
            primary_provider, model_name, system_prompt, messages_dict,
            temperature, request.max_tokens, "", "error", 0, 0, 0.0,
            0, True, f"Streaming failed: {last_error or 'No configured providers'}", True,
        )
    except Exception:
        pass
    yield {"type": "error", "message": last_error or "No configured providers"}


# ─── Cost Tracking ─────────────────────────────────


def _cost_rows(db: FirestoreDB, workspace_id: str | None, days: int) -> list[dict]:
    """LLM calls within the last N days, date-filtered in Firestore.

    Previously this downloaded the ENTIRE llm_calls collection and filtered
    in Python — an O(n) scan that grows forever. ``query_since`` pushes the
    ``created_at >= cutoff`` range down to Firestore (composite index declared
    in firestore.indexes.json), so only in-window rows ever leave the DB.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    if workspace_id is None:
        rows = db.query_since(LLM_CALLS, None, None, cutoff)
    else:
        rows = db.query_since(LLM_CALLS, "workspace_id", str(workspace_id), cutoff)
    return rows


async def get_cost_summary(
    db: FirestoreDB, workspace_id: str | None = None, days: int = 30
) -> dict:
    """Get cost summary for a workspace or globally."""
    rows = _cost_rows(db, workspace_id, days)

    total_calls = len(rows)
    total_prompt = sum(r.get("prompt_tokens") or 0 for r in rows)
    total_completion = sum(r.get("completion_tokens") or 0 for r in rows)
    total_tokens = sum(r.get("total_tokens") or 0 for r in rows)
    total_cost = float(sum(r.get("cost_usd") or 0 for r in rows))

    return {
        "total_cost_usd": round(total_cost, 4),
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_tokens": total_tokens,
        "total_calls": total_calls,
        "avg_cost_per_call": round(total_cost / total_calls, 6) if total_calls > 0 else 0,
        "period_days": days,
    }


async def get_cost_by_provider(
    db: FirestoreDB, workspace_id: str | None = None, days: int = 30
) -> list[dict]:
    """Get cost breakdown by LLM provider."""
    rows = _cost_rows(db, workspace_id, days)
    agg: dict[str, dict] = {}
    for r in rows:
        prov = r.get("provider") or "unknown"
        entry = agg.setdefault(prov, {"calls": 0, "tokens": 0, "cost_usd": 0.0})
        entry["calls"] += 1
        entry["tokens"] += r.get("total_tokens") or 0
        entry["cost_usd"] += r.get("cost_usd") or 0
    result = [
        {"provider": k, "calls": v["calls"], "tokens": v["tokens"], "cost_usd": round(v["cost_usd"], 4)}
        for k, v in agg.items()
    ]
    result.sort(key=lambda x: x["cost_usd"], reverse=True)
    return result


async def get_cost_by_model(
    db: FirestoreDB, workspace_id: str | None = None, days: int = 30
) -> list[dict]:
    """Get cost breakdown by model."""
    rows = _cost_rows(db, workspace_id, days)
    agg: dict[tuple, dict] = {}
    for r in rows:
        key = (r.get("model_name") or "unknown", r.get("provider") or "unknown")
        entry = agg.setdefault(key, {"calls": 0, "tokens": 0, "cost_usd": 0.0})
        entry["calls"] += 1
        entry["tokens"] += r.get("total_tokens") or 0
        entry["cost_usd"] += r.get("cost_usd") or 0
    result = [
        {"model": k[0], "provider": k[1], "calls": v["calls"], "tokens": v["tokens"], "cost_usd": round(v["cost_usd"], 4)}
        for k, v in agg.items()
    ]
    result.sort(key=lambda x: x["cost_usd"], reverse=True)
    return result


async def get_recent_calls(
    db: FirestoreDB, workspace_id: str | None = None, limit: int = 50
) -> list[dict]:
    """Get the newest N LLM calls (order+limit pushed to Firestore)."""
    if workspace_id is None:
        rows = db.query_top(LLM_CALLS, None, None, limit)
    else:
        rows = db.query_top(LLM_CALLS, "workspace_id", str(workspace_id), limit)
    return rows
