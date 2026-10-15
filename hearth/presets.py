"""LLM providers. The list matches skgate's keyed presets, with Grok sign-in first."""

from __future__ import annotations

# Same ids, names, and base URLs as github.com/helv-io/skgate internal/provider/keyed/presets.go.
# Grok is separate there: subscription sign-in, with an API key still accepted here.
PRESETS = [
    {
        "id": "grok",
        "name": "Grok",
        "base": "https://api.x.ai/v1",
        "needs_key": False,
        "optional": True,
        "hint": "Sign in with Grok, or paste an API key.",
        "docs": "https://docs.x.ai",
        "adapter": "",
        "custom": False,
        "sso": True,
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "base": "https://api.openai.com/v1",
        "needs_key": True,
        "optional": False,
        "hint": "",
        "docs": "https://platform.openai.com/api-keys",
        "adapter": "",
        "custom": False,
        "sso": False,
    },
    {
        "id": "anthropic",
        "name": "Anthropic",
        "base": "https://api.anthropic.com/v1",
        "needs_key": True,
        "optional": False,
        "hint": "",
        "docs": "https://console.anthropic.com/settings/keys",
        "adapter": "anthropic",
        "custom": False,
        "sso": False,
    },
    {
        "id": "gemini",
        "name": "Google Gemini",
        "base": "https://generativelanguage.googleapis.com/v1beta/openai",
        "needs_key": True,
        "optional": False,
        "hint": "",
        "docs": "https://aistudio.google.com/apikey",
        "adapter": "",
        "custom": False,
        "sso": False,
    },
    {
        "id": "mistral",
        "name": "Mistral",
        "base": "https://api.mistral.ai/v1",
        "needs_key": True,
        "optional": False,
        "hint": "",
        "docs": "https://console.mistral.ai/api-keys",
        "adapter": "",
        "custom": False,
        "sso": False,
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "base": "https://api.deepseek.com/v1",
        "needs_key": True,
        "optional": False,
        "hint": "",
        "docs": "https://platform.deepseek.com/api_keys",
        "adapter": "",
        "custom": False,
        "sso": False,
    },
    {
        "id": "groq",
        "name": "Groq",
        "base": "https://api.groq.com/openai/v1",
        "needs_key": True,
        "optional": False,
        "hint": "",
        "docs": "https://console.groq.com/keys",
        "adapter": "",
        "custom": False,
        "sso": False,
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "base": "https://openrouter.ai/api/v1",
        "needs_key": True,
        "optional": False,
        "hint": "",
        "docs": "https://openrouter.ai/settings/keys",
        "adapter": "",
        "custom": False,
        "sso": False,
    },
    {
        "id": "ollama",
        "name": "Ollama",
        "base": "http://localhost:11434/v1",
        "needs_key": False,
        "optional": False,
        "hint": "No key. Ollama on this computer listens here.",
        "docs": "https://ollama.com",
        "adapter": "",
        "custom": False,
        "sso": False,
    },
    {
        "id": "lmstudio",
        "name": "LM Studio",
        "base": "http://localhost:1234/v1",
        "needs_key": False,
        "optional": False,
        "hint": "No key. LM Studio on this computer listens here.",
        "docs": "https://lmstudio.ai",
        "adapter": "",
        "custom": False,
        "sso": False,
    },
    {
        "id": "custom",
        "name": "Custom endpoint",
        "base": "",
        "needs_key": False,
        "optional": True,
        "hint": "Any OpenAI-compatible endpoint. The key is optional.",
        "docs": "",
        "adapter": "",
        "custom": True,
        "sso": False,
    },
]


def by_id(provider_id: str) -> dict:
    for preset in PRESETS:
        if preset["id"] == provider_id:
            return preset
    return by_id("custom")


def match_base(base_url: str) -> str:
    normalized = (base_url or "").strip().rstrip("/")
    for preset in PRESETS:
        if preset["base"] and preset["base"].rstrip("/") == normalized:
            return preset["id"]
    return "custom"


def resolve():
    """Return the saved provider, the bearer to send, and whether it is a Grok sign-in token."""
    from hearth import grok_sso, settings

    config = settings.load()
    preset = by_id(config["provider"])
    key = config.get("key") or ""
    oauth = False
    if preset["id"] == "grok" and grok_sso.signed_in():
        key = grok_sso.access_token()
        oauth = True
    if preset["needs_key"] and not preset["optional"] and not key:
        raise RuntimeError("Add an API key in LLM Model settings.")
    if preset["id"] == "grok" and not key:
        raise RuntimeError("Sign in to Grok, or add an API key.")
    if not config["base_url"]:
        raise RuntimeError("Add an endpoint in LLM Model settings.")
    return config, preset, key, oauth
