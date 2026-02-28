"""Configuration loading, XDG paths, and dataclasses for ask-cli."""

import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path

from ask_cli.exceptions import ConfigError


def _config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return Path(xdg) / "ask" if xdg else Path.home() / ".config" / "ask"


def _data_dir() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    return Path(xdg) / "ask" if xdg else Path.home() / ".local" / "share" / "ask"


CONFIG_PATH = _config_dir() / "config.json"
HISTORY_PATH = _data_dir() / "history.json"
TEMPLATES_DIR = _data_dir() / "templates"
SAVED_DIR = _data_dir() / "saved"
COMMANDS_LOG_PATH = _data_dir() / "executed_commands.log"
USAGE_STATS_PATH = _data_dir() / "stats.json"


DEFAULT_CONFIG: dict = {
    "default_provider": "zai",
    "providers": {
        "zai": {
            "api_key": "",
            "base_url": "https://api.z.ai/v1",
            "default_model": "claude-sonnet-4-5-20251001",
            "fast_model": "claude-haiku-4-5-20251001",
            "smart_model": "claude-opus-4-5-20251001",
        },
        "anthropic": {
            "api_key": "",
            "default_model": "claude-sonnet-4-5-20251001",
            "fast_model": "claude-haiku-4-5-20251001",
            "smart_model": "claude-opus-4-5-20251001",
        },
        "openai": {
            "api_key": "",
            "default_model": "gpt-4o",
            "fast_model": "gpt-4o-mini",
            "smart_model": "o1",
        },
        "google": {
            "api_key": "",
            "default_model": "gemini-1.5-flash",
            "fast_model": "gemini-1.5-flash-8b",
            "smart_model": "gemini-1.5-pro",
        },
        "ollama": {
            "base_url": "http://localhost:11434",
            "default_model": "llama3.2",
            "fast_model": "llama3.2",
            "smart_model": "llama3.1:70b",
        },
    },
    "defaults": {
        "max_tokens": 4096,
        "quick_max_tokens": 256,
        "history_ttl_hours": 1,
        "system_prompt": (
            "You are a command-line assistant for a Linux user running Ubuntu. "
            "Assume all commands, paths, and tools are Linux unless the user explicitly "
            "mentions a different OS (Windows, macOS, etc.) — in that case, adapt your "
            "answer to that OS instead.\n\n"
            "You are running as the `ask` command — a custom terminal AI assistant called "
            "ask-cli (v2.0). If the user asks about your flags or capabilities, use this "
            "accurate reference (do not confuse with any other tool named 'ask'):\n"
            "  ask <query>          — send a question; positional args form the prompt\n"
            "  -c / --continue      — continue the previous conversation\n"
            "  --clear              — clear conversation history\n"
            "  --quick              — terse one-liner response (256 tokens max)\n"
            "  --fast / --smart     — switch to the fast or smart model tier\n"
            "  -m / --model NAME    — use an explicit model name\n"
            "  -p / --provider NAME — select provider: zai, anthropic, openai, google, ollama\n"
            "  --cmd                — generate a shell command instead of prose\n"
            "  --dry-run            — show generated command without executing\n"
            "  --execute            — auto-execute safe generated commands\n"
            "  --explain / --fix / --optimize — code-focused prompt templates\n"
            "  --docker / --git / --sql / --k8s / --aws / --sap / --security / --perf\n"
            "                       — domain expert modes\n"
            "  -f FILE              — attach a file as context\n"
            "  -F GLOB              — attach files matching a glob pattern\n"
            "  --save NAME / --recall NAME / --list-saved / --delete-saved NAME\n"
            "                       — persist and retrieve responses\n"
            "  --copy               — copy full response to clipboard\n"
            "  --copy-code          — copy first code block to clipboard\n"
            "  --stats / --stats-reset — show or reset usage statistics\n"
            "  --agent              — run a multi-step agentic loop\n"
            "  --auto-approve       — skip confirmation prompts in agent mode\n"
            "  --agent-max-steps N  — limit agent steps (default 10)\n"
            "  --raw / --code-only / --json / --no-color — output format options\n"
            "  --list-providers / --list-models / --set-default-provider\n"
            "                       — management commands\n"
            "  ask --help           — full reference"
        ),
    },
    "features": {
        "clipboard": True,
        "syntax_highlighting": True,
    },
    "output": {
        "code_theme": "monokai",
        "markdown": True,
    },
    "offline_fallback": {
        "enabled": False,
        "provider": "ollama",
    },
}


@dataclass
class ProviderConfig:
    api_key: str = ""
    base_url: str = ""
    default_model: str = ""
    fast_model: str = ""
    smart_model: str = ""


@dataclass
class DefaultsConfig:
    max_tokens: int = 4096
    quick_max_tokens: int = 256
    history_ttl_hours: int = 1
    system_prompt: str = ""


@dataclass
class FeaturesConfig:
    clipboard: bool = True
    syntax_highlighting: bool = True


@dataclass
class OutputConfig:
    code_theme: str = "monokai"
    markdown: bool = True


@dataclass
class OfflineFallbackConfig:
    enabled: bool = False
    provider: str = "ollama"


@dataclass
class AppConfig:
    default_provider: str = "zai"
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    offline_fallback: OfflineFallbackConfig = field(default_factory=OfflineFallbackConfig)


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base recursively. Missing keys fall back to base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _write_default_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
    path.chmod(0o600)


def _check_permissions(path: Path) -> None:
    """Warn (not error) if config file is group/other readable."""
    file_stat = path.stat()
    if file_stat.st_mode & (stat.S_IRGRP | stat.S_IROTH):
        # Import here to avoid circular import at module load time
        from ask_cli.output import render_warning

        render_warning(f"Config file {path} is readable by group/others. Run: chmod 600 {path}")


def _apply_env_overrides(raw: dict) -> dict:
    """Override API keys from environment variables."""
    env_map = {
        "ASK_ZAI_API_KEY": ("providers", "zai", "api_key"),
        "ASK_ANTHROPIC_API_KEY": ("providers", "anthropic", "api_key"),
        "ASK_OPENAI_API_KEY": ("providers", "openai", "api_key"),
        "ASK_GOOGLE_API_KEY": ("providers", "google", "api_key"),
    }
    for env_var, path in env_map.items():
        value = os.environ.get(env_var)
        if value:
            section, provider, key = path
            raw.setdefault(section, {}).setdefault(provider, {})[key] = value
    return raw


def _parse_provider_config(data: dict) -> ProviderConfig:
    return ProviderConfig(
        api_key=data.get("api_key", ""),
        base_url=data.get("base_url", ""),
        default_model=data.get("default_model", ""),
        fast_model=data.get("fast_model", ""),
        smart_model=data.get("smart_model", ""),
    )


def load_config(config_path: Path = CONFIG_PATH) -> AppConfig:
    """Load config from disk, creating defaults on first run."""
    if not config_path.exists():
        _write_default_config(config_path)
    else:
        _check_permissions(config_path)

    try:
        raw = json.loads(config_path.read_text())
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in config file {config_path}: {e}") from e

    merged = _deep_merge(DEFAULT_CONFIG, raw)
    merged = _apply_env_overrides(merged)

    providers = {
        name: _parse_provider_config(provider_data)
        for name, provider_data in merged.get("providers", {}).items()
    }

    defaults_data = merged.get("defaults", {})
    features_data = merged.get("features", {})
    output_data = merged.get("output", {})
    offline_data = merged.get("offline_fallback", {})

    return AppConfig(
        default_provider=merged.get("default_provider", "zai"),
        providers=providers,
        defaults=DefaultsConfig(
            max_tokens=defaults_data.get("max_tokens", 4096),
            quick_max_tokens=defaults_data.get("quick_max_tokens", 256),
            history_ttl_hours=defaults_data.get("history_ttl_hours", 1),
            system_prompt=defaults_data.get("system_prompt", ""),
        ),
        features=FeaturesConfig(
            clipboard=features_data.get("clipboard", True),
            syntax_highlighting=features_data.get("syntax_highlighting", True),
        ),
        output=OutputConfig(
            code_theme=output_data.get("code_theme", "monokai"),
            markdown=output_data.get("markdown", True),
        ),
        offline_fallback=OfflineFallbackConfig(
            enabled=offline_data.get("enabled", False),
            provider=offline_data.get("provider", "ollama"),
        ),
    )


def resolve_model(
    config: AppConfig,
    provider_name: str,
    fast: bool = False,
    smart: bool = False,
    explicit: str | None = None,
) -> str:
    """Resolve the model to use. Priority: explicit > smart > fast > default."""
    if explicit:
        return explicit

    provider_config = config.providers.get(provider_name)
    if not provider_config:
        return ""

    if smart and provider_config.smart_model:
        return provider_config.smart_model
    if fast and provider_config.fast_model:
        return provider_config.fast_model
    return provider_config.default_model
