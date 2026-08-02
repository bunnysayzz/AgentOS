"""Provider metadata - display info, icons, colors, defaults, and fallback priority."""

from app.models.mcp import LLMProvider

# ─── Provider Display Metadata ──────────────────────────────────────

PROVIDER_METADATA: dict[str, dict] = {
    "openai": {
        "label": "OpenAI",
        "color": "from-emerald-500 to-emerald-600",
        "icon": "openai",
        "tagline": "GPT-4o, GPT-4o-mini, GPT-3.5",
        "default_model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "free_tier": "Pay-as-you-go with $5 free credits",
        "fallback_priority": 1,
    },
    "anthropic": {
        "label": "Anthropic",
        "color": "from-amber-500 to-amber-600",
        "icon": "anthropic",
        "tagline": "Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku",
        "default_model": "claude-3-5-sonnet-20241022",
        "base_url": "https://api.anthropic.com/v1",
        "free_tier": "Pay-as-you-go",
        "fallback_priority": 2,
    },
    "google": {
        "label": "Google Gemini",
        "color": "from-blue-500 to-blue-600",
        "icon": "google",
        "tagline": "Gemini 2.0 Flash, Gemini 1.5 Pro — 1M context window",
        "default_model": "gemini-2.0-flash",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "free_tier": "60 RPM / 1M TPM free tier",
        "fallback_priority": 3,
    },
    "bluesminds": {
        "label": "Bluesminds",
        "color": "from-cyan-500 to-cyan-600",
        "icon": "bluesminds",
        "tagline": "GPT-4o-mini, GPT-3.5 — Zero cost",
        "default_model": "gpt-4o-mini",
        "base_url": "https://api.bluesminds.com/v1",
        "free_tier": "100% free — tested working ✅",
        "fallback_priority": 5,
    },
    "groq": {
        "label": "Groq",
        "color": "from-purple-500 to-purple-600",
        "icon": "groq",
        "tagline": "Llama 3.3 70B — World's fastest: 300-1000+ t/s",
        "default_model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "free_tier": "Free tier with rate limits",
        "fallback_priority": 6,
    },
    "cerebras": {
        "label": "Cerebras",
        "color": "from-orange-500 to-orange-600",
        "icon": "cerebras",
        "tagline": "Llama 3.1 8B — 20x faster inference, 1M tokens/day",
        "default_model": "llama3.1-8b",
        "base_url": "https://api.cerebras.ai/v1",
        "free_tier": "1M tokens/day free",
        "fallback_priority": 7,
    },
    "openrouter": {
        "label": "OpenRouter",
        "color": "from-rose-500 to-rose-600",
        "icon": "openrouter",
        "tagline": "28 free models (:free suffix) — Llama 3.3 70B, Mistral, more",
        "default_model": "meta-llama/llama-3.3-70b-instruct:free",
        "base_url": "https://openrouter.ai/api/v1",
        "free_tier": "28 models with free tier",
        "fallback_priority": 8,
    },
    "mistral": {
        "label": "Mistral AI",
        "color": "from-sky-500 to-sky-600",
        "icon": "mistral",
        "tagline": "Open-Mistral-Nemo — 30 RPM free, 128K context",
        "default_model": "open-mistral-nemo",
        "base_url": "https://api.mistral.ai/v1",
        "free_tier": "30 RPM free tier",
        "fallback_priority": 9,
    },
    "huggingface": {
        "label": "HuggingFace",
        "color": "from-yellow-500 to-yellow-600",
        "icon": "huggingface",
        "tagline": "300+ open-source models — Llama 3.3 70B, Qwen, DeepSeek",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct",
        "base_url": "https://router.huggingface.co/v1",
        "free_tier": "Free inference API with rate limits",
        "fallback_priority": 10,
    },
    "nvidia_nim": {
        "label": "NVIDIA NIM",
        "color": "from-green-500 to-green-600",
        "icon": "nvidia",
        "tagline": "Llama 3.1 8B — 1000 free NIM credits",
        "default_model": "meta/llama-3.1-8b-instruct",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "free_tier": "1000 free NIM credits",
        "fallback_priority": 11,
    },
    "github_models": {
        "label": "GitHub Models",
        "color": "from-gray-500 to-gray-600",
        "icon": "github",
        "tagline": "GPT-4o-mini — Free for GitHub accounts",
        "default_model": "gpt-4o-mini",
        "base_url": "https://models.inference.ai.azure.com",
        "free_tier": "Free with GitHub account",
        "fallback_priority": 12,
    },
    "cloudflare": {
        "label": "Cloudflare Workers AI",
        "color": "from-orange-400 to-orange-500",
        "icon": "cloudflare",
        "tagline": "Llama 3.1 8B — 10K Neurons/day, edge inference",
        "default_model": "@cf/meta/llama-3.1-8b-instruct",
        "base_url": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
        "free_tier": "10K Neurons/day free",
        "fallback_priority": 13,
    },
    "shuttleai": {
        "label": "ShuttleAI",
        "color": "from-violet-500 to-violet-600",
        "icon": "shuttleai",
        "tagline": "GPT-OSS-20B — 2 RPM free",
        "default_model": "gpt-oss-20b",
        "base_url": "https://api.shuttleai.com/v1",
        "free_tier": "2 RPM free tier",
        "fallback_priority": 14,
    },
    "aihubmix": {
        "label": "AIHubMix",
        "color": "from-indigo-500 to-indigo-600",
        "icon": "aihubmix",
        "tagline": "27+ free models — GPT-chat-latest, Llama, Claude via proxies",
        "default_model": "gpt-chat-latest",
        "base_url": "https://aihubmix.com/v1",
        "free_tier": "27+ free models available",
        "fallback_priority": 15,
    },
    "kluster_ai": {
        "label": "Kluster AI",
        "color": "from-pink-500 to-pink-600",
        "icon": "kluster",
        "tagline": "DeepSeek R1 — Generous free tier, 64K context",
        "default_model": "deepseek-r1",
        "base_url": "https://api.kluster.ai/v1",
        "free_tier": "Generous free tier",
        "fallback_priority": 16,
    },
    "zhipu_zai": {
        "label": "Zhipu (智谱 AI)",
        "color": "from-blue-600 to-blue-700",
        "icon": "zhipu",
        "tagline": "GLM-4.5 Air — 128K context, MIT licensed GLM-5 744B",
        "default_model": "glm-4.5-air",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "free_tier": "Free tier available",
        "fallback_priority": 17,
    },
    "together_ai": {
        "label": "Together AI",
        "color": "from-red-500 to-red-600",
        "icon": "together",
        "tagline": "Llama 3.3 70B Turbo — $25 free credits",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "base_url": "https://api.together.xyz/v1",
        "free_tier": "$25 free credits on signup",
        "fallback_priority": 18,
    },
    "sambanova": {
        "label": "SambaNova",
        "color": "from-teal-500 to-teal-600",
        "icon": "sambanova",
        "tagline": "Llama 3.3 70B — $5 for 30 days",
        "default_model": "Meta-Llama-3.3-70B-Instruct",
        "base_url": "https://api.sambanova.ai/v1",
        "free_tier": "$5 free credits (30-day)",
        "fallback_priority": 19,
    },
    "hyperbolic": {
        "label": "Hyperbolic",
        "color": "from-fuchsia-500 to-fuchsia-600",
        "icon": "hyperbolic",
        "tagline": "Llama 3.1 70B — $1 promo credits",
        "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
        "base_url": "https://api.hyperbolic.xyz/v1",
        "free_tier": "$1 promo credits",
        "fallback_priority": 20,
    },
    "fireworks": {
        "label": "Fireworks AI",
        "color": "from-amber-400 to-amber-500",
        "icon": "fireworks",
        "tagline": "Llama v3.3 70B — $1 free credits",
        "default_model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "free_tier": "$1 free credits",
        "fallback_priority": 21,
    },
    "deepinfra": {
        "label": "DeepInfra",
        "color": "from-lime-500 to-lime-600",
        "icon": "deepinfra",
        "tagline": "Llama 3.1 70B — Free credits available",
        "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
        "base_url": "https://api.deepinfra.com/v1/openai",
        "free_tier": "Free credits on signup",
        "fallback_priority": 22,
    },
    "novita": {
        "label": "Novita AI",
        "color": "from-sky-400 to-sky-500",
        "icon": "novita",
        "tagline": "Llama 3.3 70B — Free credits available",
        "default_model": "meta-llama/llama-3.3-70b-instruct",
        "base_url": "https://api.novita.ai/v3/openai",
        "free_tier": "Free credits on signup",
        "fallback_priority": 23,
    },
    "aiml_api": {
        "label": "AI/ML API",
        "color": "from-cyan-400 to-cyan-500",
        "icon": "aiml",
        "tagline": "400+ models — GPT-4o, Claude, Llama — free tier",
        "default_model": "gpt-4o",
        "base_url": "https://api.aimlapi.com/v1",
        "free_tier": "400+ models with free tier",
        "fallback_priority": 24,
    },
    "swiftrouter": {
        "label": "SwiftRouter",
        "color": "from-blue-400 to-blue-500",
        "icon": "swiftrouter",
        "tagline": "66 models — GPT-4o, Claude, Gemini — already configured ✅",
        "default_model": "gpt-4o",
        "base_url": "https://api.swiftrouter.com/v1",
        "free_tier": "Multiple free models available",
        "fallback_priority": 25,
    },
    "deepseek": {
        "label": "DeepSeek",
        "color": "from-blue-700 to-indigo-700",
        "icon": "deepseek",
        "tagline": "DeepSeek Chat — $0.14/M tokens, 128K context",
        "default_model": "deepseek-chat",
        "base_url": "https://api.deepseek.com",
        "free_tier": "$0.14/M tokens (very cheap)",
        "fallback_priority": 26,
    },
    "apifreellm": {
        "label": "API Free LLM",
        "color": "from-green-400 to-green-500",
        "icon": "apifreellm",
        "tagline": "Free LLM endpoint — no-cost inference",
        "default_model": "apifreellm",
        "base_url": "https://apifreellm.com/api/v1/chat",
        "free_tier": "100% free",
        "fallback_priority": 27,
    },
    "llmapi": {
        "label": "LLM API",
        "color": "from-purple-400 to-purple-500",
        "icon": "llmapi",
        "tagline": "GPT-4o access via LLM API provider",
        "default_model": "gpt-4o",
        "base_url": "https://api.llmapi.ai/v1",
        "free_tier": "Free tier available",
        "fallback_priority": 28,
    },
    "pollinations": {
        "label": "Pollinations AI",
        "color": "from-pink-400 to-pink-500",
        "icon": "pollinations",
        "tagline": "Free AI model access — no API key needed!",
        "default_model": "openai",
        "base_url": "https://text.pollinations.ai/openai",
        "free_tier": "100% free — no API key required",
        "fallback_priority": 4,
    },
    "naga_ai": {
        "label": "Naga AI",
        "color": "from-red-400 to-red-500",
        "icon": "naga",
        "tagline": "Free AI model aggregation service",
        "default_model": "gpt-3.5-turbo",
        "base_url": "https://api.naga.ac/v1",
        "free_tier": "Free tier available",
        "fallback_priority": 29,
    },
    "azure": {
        "label": "Azure OpenAI",
        "color": "from-sky-500 to-sky-600",
        "icon": "azure",
        "tagline": "GPT-4o, GPT-4, GPT-3.5 via Azure",
        "default_model": "gpt-4o",
        "base_url": "https://{resource}.openai.azure.com/v1",
        "free_tier": "Azure free account ($200 credits)",
        "fallback_priority": 30,
    },
    "ollama": {
        "label": "Ollama (Local)",
        "color": "from-violet-500 to-violet-600",
        "icon": "ollama",
        "tagline": "Llama 3, Mistral, CodeLlama — run locally, no API key needed",
        "default_model": "llama3.2",
        "base_url": "http://localhost:11434",
        "free_tier": "100% free (local)",
        "fallback_priority": 99,
    },
    "custom": {
        "label": "Custom Provider",
        "color": "from-surface-500 to-surface-600",
        "icon": "custom",
        "tagline": "Any OpenAI-compatible API endpoint",
        "default_model": "custom-model",
        "base_url": "",
        "free_tier": "Depends on provider",
        "fallback_priority": 100,
    },
}

# ─── Fallback Priority Chain ──────────────────────────────────────

# Providers ordered by fallback priority preference
# Lower number = higher priority (try first)
FALLBACK_PRIORITY: list[str] = sorted(
    PROVIDER_METADATA.keys(),
    key=lambda p: PROVIDER_METADATA[p]["fallback_priority"],
)

# Model-to-provider mapping for fallback routing
MODEL_PROVIDER_MAP: dict[str, str] = {
    "gpt-4o": "openai",
    "gpt-4o-mini": "openai",
    "gpt-4-turbo": "openai",
    "gpt-3.5-turbo": "openai",
    "o1-preview": "openai",
    "o1-mini": "openai",
    "claude": "anthropic",
    "gemini": "google",
    "deepseek": "deepseek",
    "llama": "groq",  # Can fallback to groq, cerebras, huggingface, etc.
    "mistral": "mistral",
    "codellama": "ollama",
}

# ─── Helper Functions ───────────────────────────────────────────────

def get_provider_metadata(provider: str | LLMProvider) -> dict:
    """Get metadata for a provider, falling back to defaults."""
    key = provider.value if isinstance(provider, LLMProvider) else provider
    return PROVIDER_METADATA.get(key, {
        "label": key.replace("_", " ").title(),
        "color": "from-surface-500 to-surface-600",
        "icon": "custom",
        "tagline": "",
        "default_model": "",
        "base_url": "",
        "free_tier": "",
        "fallback_priority": 100,
    })


def get_fallback_chain(
    configured_providers: list[str],
    model_name: str = "",
) -> list[str]:
    """Get the ordered fallback chain of configured providers.
    
    The primary provider is detected from the model name.
    Subsequent providers follow the fallback priority order.
    """
    # Detect primary provider from model name
    primary = None
    if model_name:
        for prefix, provider in MODEL_PROVIDER_MAP.items():
            if model_name.startswith(prefix):
                primary = provider
                break
    
    # Build ordered chain
    chain = []
    if primary and primary in configured_providers:
        chain.append(primary)
    
    # Add remaining configured providers in priority order
    for provider in FALLBACK_PRIORITY:
        if provider in configured_providers and provider != primary:
            chain.append(provider)
    
    return chain


def is_rate_limit_error(error_message: str) -> bool:
    """Check if an error is a rate limit or quota error (retryable)."""
    error_lower = error_message.lower()
    retryable_signals = [
        "rate limit",
        "rate_limit",
        "quota",
        "429",
        "too many requests",
        "insufficient_quota",
        "exhausted",
        "resource_exhausted",
        "402",
        "payment required",
        "insufficient balance",
        "over limit",
        "limit reached",
    ]
    return any(signal in error_lower for signal in retryable_signals)
