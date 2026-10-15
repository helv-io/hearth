"""LLM endpoint settings. The key and Grok tokens stay out of the JSON file."""

from __future__ import annotations

import json
import os

from hearth.paths import config_dir
from hearth.presets import by_id, match_base

DEFAULT_BASE = "https://api.x.ai/v1"
DEFAULT_MODEL = "grok-4.7"
DEFAULT_PROVIDER = "grok"


def _settings_path():
    return config_dir() / "settings.json"


def _key_path():
    return config_dir() / "key"


def load() -> dict:
    path = _settings_path()
    data = {"base_url": DEFAULT_BASE, "model": DEFAULT_MODEL, "provider": DEFAULT_PROVIDER}
    if path.exists():
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stored = {}
        if isinstance(stored, dict):
            if isinstance(stored.get("base_url"), str) and stored["base_url"].strip():
                data["base_url"] = stored["base_url"].strip()
            if isinstance(stored.get("model"), str) and stored["model"].strip():
                data["model"] = stored["model"].strip()
            provider = stored.get("provider")
            if isinstance(provider, str) and by_id(provider)["id"] == provider:
                data["provider"] = provider
            else:
                data["provider"] = match_base(data["base_url"])
    file_key = ""
    key_path = _key_path()
    if key_path.exists():
        try:
            file_key = key_path.read_text(encoding="utf-8").strip()
        except OSError:
            file_key = ""
    env_key = os.environ.get("XAI_API_KEY", "").strip() if data["provider"] == "grok" else ""
    data["has_key"] = bool(file_key or env_key)
    data["key_source"] = "file" if file_key else ("env" if env_key else "")
    data["key"] = file_key or env_key
    return data


def save(base_url: str, model: str, key: str | None, forget_key: bool = False, provider: str = DEFAULT_PROVIDER) -> dict:
    provider = by_id(provider)["id"]
    base_url = (base_url or "").strip().rstrip("/")
    if not base_url and provider != "custom":
        base_url = by_id(provider)["base"]
    model = (model or DEFAULT_MODEL).strip()
    _settings_path().write_text(
        json.dumps({"provider": provider, "base_url": base_url, "model": model}, indent=2) + "\n",
        encoding="utf-8",
    )
    key_path = _key_path()
    if forget_key:
        key_path.unlink(missing_ok=True)
    elif key is not None and key.strip():
        key_path.write_text(key.strip() + "\n", encoding="utf-8")
        os.chmod(key_path, 0o600)
    return load()
