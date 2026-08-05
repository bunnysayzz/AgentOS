"""MCP Gateway service - LLM provider abstraction, model routing, cost governance (Firestore)."""

import time
import httpx
from datetime import datetime, timezone, timedelta

from app.core.db import FirestoreDB, stamp
from app.models.mcp import LLMProvider
from app.schemas.mcp import ChatCompletionRequest, ChatCompletionResponse
from app.services.provider_service import get_api_key_for_provider, get_provider_config, list_provider_configs
from app.services.provider_metadata import get_fallback_chain, is_rate_limit_error

LLM_CALLS = "llm_calls"
MODEL_REGISTRY = "model_registry"


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
        cleaned.append({k: v for k, v in m.items() if v is not None})
    return cleaned


# ─── Real LLM API Calls ────────────────────────────


async def _call_openai_compatible(
    api_key: str,
    messages: list[dict],
    model: str,
    temperature: float,
    max_tokens: int | None,
    base_url: str = "https://api.openai.com/v1",
) -> dict:
    """Call an OpenAI-compatible chat completions API."""
    body = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens:
        body["max_tokens"] = max_tokens

    url = base_url.rstrip("/")
    if not url.endswith("chat/completions"):
        url += "/chat/completions"

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        )
        if r.status_code == 401:
            error_data = r.json().get("error", {})
            raise MCPError(f"Authentication failed: {error_data.get('message', 'Invalid API key')}", 401)
        if r.status_code == 429:
            error_data = r.json().get("error", {})
            raise MCPError(f"Rate limit exceeded: {error_data.get('message', 'Too many requests')}", 429)
        if r.status_code == 402:
            raise MCPError("Insufficient balance/credits: Payment required", 402)
        r.raise_for_status()
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
        r.raise_for_status()
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

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, json=body)
        r.raise_for_status()
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
        LLMProvider.ANTHROPIC: "claude-3-haiku-20240307",
        LLMProvider.GOOGLE: "gemini-2.0-flash",
        LLMProvider.GROQ: "llama-3.3-70b-versatile",
        LLMProvider.CEREBRAS: "gpt-oss-120b",
        LLMProvider.OPENROUTER: "meta-llama/llama-3.3-70b-instruct:free",
        LLMProvider.MISTRAL: "open-mistral-nemo",
        LLMProvider.HUGGINGFACE: "meta-llama/Llama-3.3-70B-Instruct",
        LLMProvider.DEEPSEEK: "deepseek-chat",
        LLMProvider.OLLAMA: "llama3.2",
    }
    return model_map.get(provider)


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
        is_fallback = attempt_idx > 0

        if not api_key:
            continue  # Skip if no key configured for this provider

        start_time = time.monotonic()

        try:
            messages_dict = _clean_messages([m.model_dump() for m in request.messages])

            actual_model = model_name
            if is_fallback:
                default_model = _get_model_for_provider(provider)
                actual_model = default_model or model_name

            if provider in (LLMProvider.OPENAI, LLMProvider.DEEPSEEK, LLMProvider.GROQ,
                            LLMProvider.CEREBRAS, LLMProvider.OPENROUTER, LLMProvider.MISTRAL,
                            LLMProvider.HUGGINGFACE, LLMProvider.OLLAMA):
                base_url = provider_config.get("base_url") if provider_config else None
                if not base_url:
                    if provider == LLMProvider.DEEPSEEK:
                        base_url = "https://api.deepseek.com"
                    else:
                        base_url = "https://api.openai.com/v1"
                if provider == LLMProvider.OLLAMA:
                    base_url = base_url or "http://localhost:11434/v1"

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
                base_url = provider_config.get("base_url") if provider_config else None
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
                    raise MCPError(f"Real API calls for {provider.value} are not yet implemented")

            duration_ms = int((time.monotonic() - start_time) * 1000)
            total_tokens = prompt_tokens + completion_tokens
            cost_usd = calculate_cost(model_name, prompt_tokens, completion_tokens)

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
            error_str = str(e)
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


# ─── Cost Tracking ─────────────────────────────────


def _cost_rows(db: FirestoreDB, workspace_id: str | None, days: int) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = db.query(LLM_CALLS) if workspace_id is None else db.query(LLM_CALLS, "workspace_id", str(workspace_id))
    return [r for r in rows if (r.get("created_at") or "") >= cutoff]


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
    """Get recent LLM calls."""
    rows = db.query(LLM_CALLS) if workspace_id is None else db.query(LLM_CALLS, "workspace_id", str(workspace_id))
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows[:limit]
