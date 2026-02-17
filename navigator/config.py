"""Configuration management for Navigator."""

import json
import os
from pathlib import Path

NAVIGATOR_DIR = Path(os.environ.get("NAVIGATOR_HOME", str(Path.home() / ".navigator")))
CONFIG_PATH = NAVIGATOR_DIR / "config.json"
CONVERSATIONS_PATH = NAVIGATOR_DIR / "conversations.jsonl"
PREFERENCES_PATH = NAVIGATOR_DIR / "preferences.jsonl"

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
OLLAMA_PREFIX = "ollama:"


def is_ollama_model(model: str | None = None) -> bool:
    """True if the model is an Ollama local model (ollama:modelname)."""
    m = model if model is not None else get_model()
    return (m or "").strip().startswith(OLLAMA_PREFIX)


def get_ollama_model_name(model: str | None = None) -> str:
    """Get the Ollama model name (strip ollama: prefix). Returns empty if not Ollama."""
    m = model if model is not None else get_model()
    if not is_ollama_model(m):
        return ""
    return (m or "").strip()[len(OLLAMA_PREFIX) :].strip()


PREFERENCE_COMPRESSION_THRESHOLD = 50
# Minimum messages (user + assistant) to evaluate; avoids learning from trivial/short convos
MIN_CONVERSATION_MESSAGES = 6


def is_debug() -> bool:
    """Whether debug logging is enabled (NAVIGATOR_DEBUG=1)."""
    return os.environ.get("NAVIGATOR_DEBUG", "").strip() in ("1", "true", "yes")


def ensure_navigator_dir() -> None:
    """Create ~/.navigator if it doesn't exist."""
    NAVIGATOR_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Load config from ~/.navigator/config.json."""
    ensure_navigator_dir()
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_config(config: dict) -> None:
    """Save config to ~/.navigator/config.json."""
    ensure_navigator_dir()
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def _trim_key(key: str | None) -> str | None:
    """Trim whitespace from key (common copy/paste issue)."""
    if key is None:
        return None
    key = key.strip()
    return key if key else None


def get_token() -> str | None:
    """Get token from config or ANTHROPIC_API_KEY env. Prefers api_key over setup_token."""
    config = load_config()
    return _trim_key(
        config.get("api_key")
        or config.get("setup_token")
        or os.environ.get("ANTHROPIC_API_KEY")
    )


def get_model() -> str:
    """Get model from config, or default."""
    return load_config().get("model", DEFAULT_MODEL)


def set_token(token: str) -> None:
    """Set setup-token in config (whitespace is trimmed)."""
    config = load_config()
    config["setup_token"] = (token or "").strip()
    save_config(config)


def set_api_key(api_key: str) -> None:
    """Set API key in config (whitespace is trimmed). Use for programmatic API access."""
    config = load_config()
    config["api_key"] = (api_key or "").strip()
    save_config(config)


def set_model(model: str) -> None:
    """Set model in config."""
    config = load_config()
    config["model"] = model
    save_config(config)


def get_last_evaluated() -> str | None:
    """Get timestamp of last evaluated conversation."""
    return load_config().get("last_evaluated")


def set_last_evaluated(timestamp: str) -> None:
    """Set timestamp of last evaluated conversation."""
    config = load_config()
    config["last_evaluated"] = timestamp
    save_config(config)


def get_persona_file() -> str | None:
    """Get path to loaded persona file (JSON/JSONL)."""
    return load_config().get("persona_file")


def set_persona_file(path: str | Path | None) -> None:
    """Set persona file path. Pass None to clear."""
    config = load_config()
    if path is None:
        config.pop("persona_file", None)
        config.pop("persona_summary", None)
    else:
        config["persona_file"] = str(Path(path).resolve())
    save_config(config)


def get_persona_summary() -> str | None:
    """Get the cached persona summary (generated at load time)."""
    return load_config().get("persona_summary")


def set_persona_summary(summary: str | None) -> None:
    """Set persona summary. Pass None to clear."""
    config = load_config()
    if summary is None:
        config.pop("persona_summary", None)
    else:
        config["persona_summary"] = summary
    save_config(config)


def _is_api_key(token: str) -> bool:
    """True if token is an API key (sk-ant-api03-...), else OAuth/setup-token (sk-ant-oat01-...).
    Note: OAuth tokens are rejected by the API for programmatic access ('OAuth authentication
    is currently not supported'). Only API keys work for Navigator.
    """
    t = token.strip()
    # OAuth/setup-tokens are sk-ant-oat01-... - API rejects these for programmatic use
    if t.startswith("sk-ant-oat01-"):
        return False
    # API keys are sk-ant-api03-... and use x-api-key - these work
    return t.startswith("sk-ant-")


def get_auth_env() -> dict[str, str]:
    """Build env dict for Agent SDK / anthropic SDK auth.
    Setup-tokens (from claude setup-token) must be sent as Authorization: Bearer,
    not x-api-key. Use ANTHROPIC_CUSTOM_HEADERS for that.
    """
    env = dict(os.environ)
    token = get_token()
    if not token:
        return env

    if _is_api_key(token):
        env["ANTHROPIC_API_KEY"] = token
    else:
        # OAuth/setup-token: send as Authorization Bearer. Note: API often returns
        # "OAuth authentication is currently not supported" for programmatic access.
        # User should use an API key (navigator config --api-key) instead.
        env["ANTHROPIC_CUSTOM_HEADERS"] = f"Authorization: Bearer {token}"
        env.pop("ANTHROPIC_API_KEY", None)
    return env
