"""MCP Gateway service - LLM provider abstraction, model routing, cost governance."""

import time
import json
import httpx
from datetime import datetime, timezone
from uuid import UUID

from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp import LLMCall, ModelRegistry, LLMProvider, ProviderConfig
from app.schemas.mcp import ChatCompletionRequest, ChatCompletionResponse, ChatMessage
from app.core.config import settings
from app.services.provider_service import get_api_key_for_provider, get_provider_config, list_provider_configs
from app.services.provider_metadata import get_fallback_chain, is_rate_limit_error


# ─── Provider Fallback Configuration ────────────────────────────

# Default query message for fallback: brief, generic
FALLBACK_USER_QUERY = "Hello, please respond with a brief acknowledgment."


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
    db: AsyncSession, provider: LLMProvider | None = None
) -> list[ModelRegistry]:
    """List all available models, optionally filtered by provider."""
    conditions = [
        ModelRegistry.is_active.is_(True),
        ModelRegistry.is_deprecated.is_(False),
        ModelRegistry.deleted_at.is_(None),
    ]
    if provider:
        conditions.append(ModelRegistry.provider == provider)

    result = await db.execute(
        select(ModelRegistry).where(*conditions).order_by(ModelRegistry.provider, ModelRegistry.model_name)
    )
    return list(result.scalars().all())


async def seed_default_models(db: AsyncSession) -> int:
    """Seed default model pricing into the registry if empty."""
    result = await db.execute(select(func.count(ModelRegistry.id)))
    count = result.scalar() or 0
    if count > 0:
        return 0

    count = 0
    for model_key, pricing in DEFAULT_MODEL_PRICING.items():
        provider = LLMProvider.OPENAI
        if model_key.startswith("claude"):
            provider = LLMProvider.ANTHROPIC
        elif model_key.startswith("gemini"):
            provider = LLMProvider.GOOGLE

        model = ModelRegistry(
            provider=provider,
            model_name=model_key,
            input_price_per_1k=pricing["input"],
            output_price_per_1k=pricing["output"],
            context_window=pricing["context"],
            max_output_tokens=8192,
            is_active=True,
            capabilities=["chat", "function_calling", "streaming"],
        )
        db.add(model)
        count += 1

    await db.flush()
    return count


def calculate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate the cost of an LLM call based on token usage."""
    pricing = DEFAULT_MODEL_PRICING.get(model_name, {"input": 0.01, "output": 0.03})
    input_cost = (prompt_tokens / 1000) * pricing["input"]
    output_cost = (completion_tokens / 1000) * pricing["output"]
    return round(input_cost + output_cost, 6)


# ─── Real LLM API Calls ────────────────────────────


async def _call_openai_compatible(
    api_key: str,
    messages: list[dict],
    model: str,
    temperature: float,
    max_tokens: int | None,
    base_url: str = "https://api.openai.com/v1",
) -> dict:
    """Call an OpenAI-compatible chat completions API.
    
    This works with any provider that supports the OpenAI API format:
    - DeepSeek, Groq, Cerebras, OpenRouter, Together, Fireworks, etc.
    """
    body = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens:
        body["max_tokens"] = max_tokens
    
    # Ensure base URL ends with /chat/completions
    url = base_url.rstrip("/")
    if not url.endswith("chat/completions"):
        if url.endswith("v1"):
            url += "/chat/completions"
        elif url.endswith("openai"):
            url += "/chat/completions"
        else:
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
            raise MCPError(f"Insufficient balance/credits: Payment required", 402)
        r.raise_for_status()
        return r.json()


async def _call_openai(
    api_key: str, messages: list[dict], model: str, temperature: float, max_tokens: int | None
) -> dict:
    """Call OpenAI chat completions API."""
    body = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens:
        body["max_tokens"] = max_tokens
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        )
        r.raise_for_status()
        return r.json()


async def _call_anthropic(
    api_key: str, messages: list[dict], model: str, temperature: float, max_tokens: int | None
) -> dict:
    """Call Anthropic messages API."""
    # Extract system message
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
    # Convert OpenAI-style messages to Gemini format
    contents = []
    for m in messages:
        if m["role"] in ("user", "assistant"):
            contents.append({"role": m["role"], "parts": [{"text": m["content"]}]})

    body = {
        "contents": contents,
        "generationConfig": {"temperature": temperature},
    }
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


def _build_system_message(messages: list[ChatMessage]) -> str | None:
    """Extract system message from messages array."""
    for msg in messages:
        if msg.role == "system":
            return msg.content
    return None


async def route_chat_completion(
    db: AsyncSession,
    request: ChatCompletionRequest,
    workspace_id: UUID | None = None,
    agent_id: UUID | None = None,
    execution_id: UUID | None = None,
    use_fallback: bool = True,
) -> ChatCompletionResponse:
    """Route a chat completion request to the appropriate LLM provider.
    
    Features:
    - Makes a real API call if the provider has a configured API key
    - Falls back to simulated response if no keys are configured
    - Supports automatic fallback chain: if a provider fails (rate limit/quota),
      tries the next configured provider in priority order
    
    Args:
        use_fallback: If True, automatically tries fallback providers on failure.
    """
    model_name = request.model
    system_prompt = _build_system_message(request.messages)
    temperature = request.temperature if request.temperature is not None else 0.7

    # Provider detection from model name
    primary_provider = LLMProvider.OPENAI
    if model_name.startswith("claude"):
        primary_provider = LLMProvider.ANTHROPIC
    elif model_name.startswith("gemini"):
        primary_provider = LLMProvider.GOOGLE
    elif model_name.startswith("ollama"):
        primary_provider = LLMProvider.OLLAMA
    elif model_name.startswith("deepseek"):
        primary_provider = LLMProvider.DEEPSEEK

    # If fallback is enabled, build fallback chain of configured providers
    fallback_providers: list[LLMProvider] = []
    if use_fallback:
        all_configs = await list_provider_configs(db)
        configured_slugs = [c.provider.value for c in all_configs if c.is_active]
        fallback_chain = get_fallback_chain(configured_slugs, model_name=model_name)
        fallback_providers = [
            LLMProvider(slug) for slug in fallback_chain
            if slug in configured_slugs
        ]
        # Ensure primary is first in chain
        if primary_provider.value in configured_slugs:
            if primary_provider in fallback_providers:
                fallback_providers.remove(primary_provider)
            fallback_providers.insert(0, primary_provider)

    providers_to_try = fallback_providers if use_fallback else [primary_provider]

    # If no fallback providers configured, just use primary
    if not providers_to_try:
        providers_to_try = [primary_provider]

    last_error = None
    response = None

    for attempt_idx, provider in enumerate(providers_to_try):
        provider_config = await get_provider_config(db, provider)
        api_key = get_api_key_for_provider(provider_config)
        is_fallback = attempt_idx > 0

        if not api_key:
            continue  # Skip if no key configured for this provider

        start_time = time.monotonic()

        try:
            messages_dict = [m.model_dump() for m in request.messages]

            # Determine the model to use for this provider
            # Use provider's default model if the original model doesn't match
            actual_model = model_name
            if is_fallback:
                # Use the provider's default model for fallback calls
                default_model = _get_model_for_provider(provider)
                actual_model = default_model or model_name

            if provider == LLMProvider.OPENAI or provider == LLMProvider.DEEPSEEK:
                # OpenAI-compatible API call
                base_url = provider_config.base_url if provider_config else None
                if not base_url:
                    if provider == LLMProvider.DEEPSEEK:
                        base_url = "https://api.deepseek.com"
                    else:
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
                # Try OpenAI-compatible call for unknown providers
                base_url = provider_config.base_url if provider_config else None
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

            # Success — record and return
            duration_ms = int((time.monotonic() - start_time) * 1000)
            total_tokens = prompt_tokens + completion_tokens
            cost_usd = calculate_cost(model_name, prompt_tokens, completion_tokens)

            llm_call = LLMCall(
                workspace_id=workspace_id,
                agent_id=agent_id,
                execution_id=execution_id,
                provider=provider,
                model_name=actual_model,
                system_prompt=system_prompt,
                messages=[m.model_dump() for m in request.messages],
                temperature=temperature,
                max_tokens=request.max_tokens,
                response_content=response_content,
                finish_reason=finish_reason,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                duration_ms=duration_ms,
                is_error=False,
                error_message=None,
                is_streaming=request.stream,
            )
            db.add(llm_call)
            await db.flush()

            return ChatCompletionResponse(
                id=f"chatcmpl-{llm_call.id}",
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

            # Record failed attempt
            duration_ms = int((time.monotonic() - start_time) * 1000)
            llm_call = LLMCall(
                workspace_id=workspace_id,
                agent_id=agent_id,
                execution_id=execution_id,
                provider=provider,
                model_name=model_name,
                system_prompt=system_prompt,
                messages=[m.model_dump() for m in request.messages],
                temperature=temperature,
                max_tokens=request.max_tokens,
                response_content="",
                finish_reason="error",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_usd=0,
                duration_ms=duration_ms,
                is_error=True,
                error_message=f"Fallback from {provider.value}: {error_str}",
                is_streaming=request.stream,
            )
            db.add(llm_call)
            await db.flush()

            # Check if we should try next provider
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
    prompt_tokens = max(len(str(request.messages)) // 4, 10)
    completion_tokens = max(len(response_content) // 4, 10)
    total_tokens = prompt_tokens + completion_tokens
    cost_usd = calculate_cost(model_name, prompt_tokens, completion_tokens)

    llm_call = LLMCall(
        workspace_id=workspace_id,
        agent_id=agent_id,
        execution_id=execution_id,
        provider=primary_provider,
        model_name=model_name,
        system_prompt=system_prompt,
        messages=[m.model_dump() for m in request.messages],
        temperature=temperature,
        max_tokens=request.max_tokens,
        response_content=response_content,
        finish_reason="stop",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        duration_ms=0,
        is_error=True,
        error_message=f"All providers failed. Last: {last_error}",
        is_streaming=request.stream,
    )
    db.add(llm_call)
    await db.flush()

    return ChatCompletionResponse(
        id=f"chatcmpl-{llm_call.id}",
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


def _get_model_for_provider(provider: LLMProvider) -> str | None:
    """Get the default model name for a provider."""
    model_map = {
        LLMProvider.OPENAI: "gpt-4o-mini",
        LLMProvider.ANTHROPIC: "claude-3-haiku-20240307",
        LLMProvider.GOOGLE: "gemini-2.0-flash",
        LLMProvider.GROQ: "llama-3.3-70b-versatile",
        LLMProvider.CEREBRAS: "llama3.1-8b",
        LLMProvider.OPENROUTER: "meta-llama/llama-3.3-70b-instruct:free",
        LLMProvider.MISTRAL: "open-mistral-nemo",
        LLMProvider.HUGGINGFACE: "meta-llama/Llama-3.3-70B-Instruct",
        LLMProvider.DEEPSEEK: "deepseek-chat",
        LLMProvider.OLLAMA: "llama3.2",
    }
    return model_map.get(provider)


# ─── Cost Tracking ─────────────────────────────────


async def get_cost_summary(
    db: AsyncSession, workspace_id: UUID | None = None, days: int = 30
) -> dict:
    """Get cost summary for a workspace or globally."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    conditions = [
        LLMCall.created_at >= cutoff,
    ]
    if workspace_id:
        conditions.append(LLMCall.workspace_id == workspace_id)

    result = await db.execute(
        select(
            func.count(LLMCall.id),
            func.coalesce(func.sum(LLMCall.prompt_tokens), 0),
            func.coalesce(func.sum(LLMCall.completion_tokens), 0),
            func.coalesce(func.sum(LLMCall.total_tokens), 0),
            func.coalesce(func.sum(LLMCall.cost_usd), 0.0),
        ).where(*conditions)
    )
    row = result.one()

    total_calls = row[0] or 0
    total_prompt = row[1] or 0
    total_completion = row[2] or 0
    total_tokens = row[3] or 0
    total_cost = float(row[4] or 0.0)

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
    db: AsyncSession, workspace_id: UUID | None = None, days: int = 30
) -> list[dict]:
    """Get cost breakdown by LLM provider."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    conditions = [
        LLMCall.created_at >= cutoff,
    ]
    if workspace_id:
        conditions.append(LLMCall.workspace_id == workspace_id)

    result = await db.execute(
        select(
            LLMCall.provider,
            func.count(LLMCall.id),
            func.coalesce(func.sum(LLMCall.total_tokens), 0),
            func.coalesce(func.sum(LLMCall.cost_usd), 0.0),
        )
        .where(*conditions)
        .group_by(LLMCall.provider)
        .order_by(func.sum(LLMCall.cost_usd).desc())
    )
    return [
        {"provider": row[0], "calls": row[1] or 0, "tokens": row[2] or 0, "cost_usd": round(float(row[3] or 0.0), 4)}
        for row in result.all()
    ]


async def get_cost_by_model(
    db: AsyncSession, workspace_id: UUID | None = None, days: int = 30
) -> list[dict]:
    """Get cost breakdown by model."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    conditions = [
        LLMCall.created_at >= cutoff,
    ]
    if workspace_id:
        conditions.append(LLMCall.workspace_id == workspace_id)

    result = await db.execute(
        select(
            LLMCall.model_name,
            LLMCall.provider,
            func.count(LLMCall.id),
            func.coalesce(func.sum(LLMCall.total_tokens), 0),
            func.coalesce(func.sum(LLMCall.cost_usd), 0.0),
        )
        .where(*conditions)
        .group_by(LLMCall.model_name, LLMCall.provider)
        .order_by(func.sum(LLMCall.cost_usd).desc())
    )
    return [
        {
            "model": row[0], "provider": row[1],
            "calls": row[2] or 0, "tokens": row[3] or 0,
            "cost_usd": round(float(row[4] or 0.0), 4),
        }
        for row in result.all()
    ]


async def get_recent_calls(
    db: AsyncSession, workspace_id: UUID | None = None, limit: int = 50
) -> list[LLMCall]:
    """Get recent LLM calls."""
    conditions = []
    if workspace_id:
        conditions.append(LLMCall.workspace_id == workspace_id)

    result = await db.execute(
        select(LLMCall)
        .where(*conditions)
        .order_by(LLMCall.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
