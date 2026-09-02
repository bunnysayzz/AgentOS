"""Provider Config API routes - manage LLM API keys, test connections."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import FirestoreDB
from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.schemas.mcp import ProviderConfigCreate, ProviderConfigResponse
from app.models.user import User
from app.models.mcp import LLMProvider
from app.services import provider_service

router = APIRouter(prefix="/mcp/providers", tags=["MCP Provider Configs"], redirect_slashes=False)


# ─── Route ORDER IS IMPORTANT: Static routes MUST come before path-parameter routes ──
# /detect must be defined BEFORE /{provider} or FastAPI will try to match 'detect' as a provider enum value

@router.get("/detect", description="Detect provider from API key prefix")
async def detect_provider(
    api_key: str = Query(..., min_length=3),
    current_user: User = Depends(get_current_active_user),
):
    """Detect the provider from an API key prefix."""
    # Key prefix patterns for auto-detection
    # List of (prefix, info) tuples — checked longest-prefix-first
    _SIGS: list[tuple[str, dict]] = [
        ("sk-proj-", {"provider": "openai", "label": "OpenAI (Project Key)", "base_url": "https://api.openai.com/v1", "default_model": "gpt-4o-mini"}),
        ("sk-or-v1", {"provider": "openrouter", "label": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "default_model": "meta-llama/llama-3.3-70b-instruct:free"}),
        ("sk-ant-", {"provider": "anthropic", "label": "Anthropic", "base_url": "https://api.anthropic.com/v1", "default_model": "claude-3-5-sonnet"}),
        ("sk-moon-", {"provider": "moonshotai", "label": "Moonshot AI (Kimi)", "base_url": "https://api.moonshot.ai/v1", "default_model": "moonshot-v1-128k"}),
        ("sk-", {"provider": "openai", "label": "OpenAI", "base_url": "https://api.openai.com/v1", "default_model": "gpt-4o-mini"}),
        ("AIzaSy", {"provider": "google", "label": "Google Gemini", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "default_model": "gemini-2.0-flash"}),
        ("gsk_", {"provider": "groq", "label": "Groq", "base_url": "https://api.groq.com/openai/v1", "default_model": "llama-3.3-70b-versatile"}),
        ("csk-", {"provider": "cerebras", "label": "Cerebras", "base_url": "https://api.cerebras.ai/v1", "default_model": "gpt-oss-120b"}),
        ("dsk-", {"provider": "agentrouter", "label": "AgentRouter (DeepSeek V4)", "base_url": "https://deepseek-console-913582f071dc.herokuapp.com/v1", "default_model": "deepseek/deepseek-v4-flash"}),
        ("dinfra_", {"provider": "deepinfra", "label": "DeepInfra", "base_url": "https://api.deepinfra.com/v1/openai", "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct"}),
        ("fw_", {"provider": "fireworks", "label": "Fireworks AI", "base_url": "https://api.fireworks.ai/inference/v1", "default_model": "accounts/fireworks/models/llama-v3p3-70b-instruct"}),
        ("hf_", {"provider": "huggingface", "label": "HuggingFace", "base_url": "https://router.huggingface.co/v1", "default_model": "meta-llama/Llama-3.3-70B-Instruct"}),
        ("hyp-", {"provider": "hyperbolic", "label": "Hyperbolic", "base_url": "https://api.hyperbolic.xyz/v1", "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct"}),
        ("nb-", {"provider": "nebius", "label": "Nebius", "base_url": "https://api.tokenfactory.nebius.com/v1", "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct"}),
        ("nvapi-", {"provider": "nvidia_nim", "label": "NVIDIA NIM", "base_url": "https://integrate.api.nvidia.com/v1", "default_model": "meta/llama-3.1-8b-instruct"}),
        ("nvita-", {"provider": "novita", "label": "Novita AI", "base_url": "https://api.novita.ai/v3/openai", "default_model": "meta-llama/llama-3.3-70b-instruct"}),
        ("pplx-", {"provider": "perplexity", "label": "Perplexity", "base_url": "https://api.perplexity.ai", "default_model": "sonar-pro"}),
        ("tgp_v1", {"provider": "togetherai", "label": "Together AI", "base_url": "https://api.together.xyz/v1", "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo"}),
        ("up_", {"provider": "upstage", "label": "Upstage", "base_url": "https://api.upstage.ai/v1/solar", "default_model": "solar-pro-2-preview"}),
        ("v2Sq", {"provider": "mistral", "label": "Mistral AI", "base_url": "https://api.mistral.ai/v1", "default_model": "open-mistral-nemo"}),
        ("xai-", {"provider": "xai", "label": "xAI (Grok)", "base_url": "https://api.x.ai/v1", "default_model": "grok-2-1212"}),
        ("github_pat", {"provider": "github_models", "label": "GitHub Models", "base_url": "https://models.inference.ai.azure.com", "default_model": "gpt-4o-mini"}),
        ("ghp_", {"provider": "github_models", "label": "GitHub (PAT)", "base_url": "https://models.inference.ai.azure.com", "default_model": "gpt-4o-mini"}),
        ("apf_", {"provider": "apifreellm", "label": "API Free LLM", "base_url": "https://apifreellm.com/api/v1/chat/", "default_model": "apifreellm"}),
        ("llmapi", {"provider": "llmapi", "label": "LLM API", "base_url": "https://api.llmapi.ai/v1", "default_model": "gpt-4o"}),
    ]
    PROVIDER_SIGNATURES = dict(sorted(_SIGS, key=lambda x: -len(x[0])))
    
    # Sort by longest prefix first
    sorted_sigs = sorted(PROVIDER_SIGNATURES.items(), key=lambda x: (-len(x[0]), x[0]))
    
    for prefix, info in sorted_sigs:
        if api_key.startswith(prefix):
            return {
                "detected": True,
                "provider": info["provider"],
                "label": info["label"],
                "base_url": info["base_url"],
                "default_model": info["default_model"],
            }
    return {
        "detected": False,
        "provider": None,
        "label": "Unknown provider",
        "base_url": None,
        "default_model": None,
    }


@router.get("", response_model=list[ProviderConfigResponse])
@router.get("/", response_model=list[ProviderConfigResponse])
async def list_providers(
    db: FirestoreDB = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all configured LLM providers."""
    configs = await provider_service.list_provider_configs(db)
    return [
        ProviderConfigResponse(
            provider=c.provider,
            default_model=c.default_model,
            is_configured=c.is_active,
            base_url=c.base_url,
            created_at=c.created_at,
        )
        for c in configs
    ]


@router.get("/{provider}", response_model=ProviderConfigResponse | None)
async def get_provider(
    provider: LLMProvider,
    db: FirestoreDB = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get config for a specific provider."""
    config = await provider_service.get_provider_config(db, provider)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider '{provider.value}' not configured",
        )
    return ProviderConfigResponse(
        provider=config.provider,
        default_model=config.default_model,
        is_configured=config.is_active,
        base_url=config.base_url,
        created_at=config.created_at,
    )


@router.put("/{provider}", response_model=ProviderConfigResponse)
async def upsert_provider(
    provider: LLMProvider,
    config_in: ProviderConfigCreate,
    db: FirestoreDB = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create or update an LLM provider config (API key, base URL, etc.)."""
    # Ensure the provider in the URL matches the body
    if config_in.provider != provider:
        config_in.provider = provider

    config = await provider_service.upsert_provider_config(db, config_in)
    return ProviderConfigResponse(
        provider=config.provider,
        default_model=config.default_model,
        is_configured=config.is_active,
        base_url=config.base_url,
        created_at=config.created_at,
    )


@router.delete("/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider: LLMProvider,
    db: FirestoreDB = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a provider config."""
    deleted = await provider_service.delete_provider_config(db, provider)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider '{provider.value}' not configured",
        )
    return None


@router.post("/{provider}/test")
async def test_provider_connection(
    provider: LLMProvider,
    db: FirestoreDB = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Test the connection to a configured provider."""
    success, message = await provider_service.test_connection(db, provider)
    return {
        "provider": provider.value,
        "success": success,
        "message": message,
    }
