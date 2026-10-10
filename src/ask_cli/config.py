"""Configuration loading, XDG paths, and dataclasses for ask-cli."""

import contextlib
import copy
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn
from urllib.parse import urlparse

from ask_cli.core.storage import read_json_object, write_private_json
from ask_cli.exceptions import ConfigError, StorageError


@dataclass(frozen=True)
class AppPaths:
    config_dir: Path
    data_dir: Path

    @property
    def config_file(self) -> Path:
        return self.config_dir / "config.json"

    @property
    def history_file(self) -> Path:
        return self.data_dir / "history.json"

    @property
    def templates_dir(self) -> Path:
        return self.data_dir / "templates"

    @property
    def saved_dir(self) -> Path:
        return self.data_dir / "saved"

    @property
    def commands_log(self) -> Path:
        return self.data_dir / "executed_commands.log"

    @property
    def stats_file(self) -> Path:
        return self.data_dir / "stats.json"


def resolve_paths() -> AppPaths:
    """Resolve XDG locations from the current environment (call once at startup)."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    xdg_data = os.environ.get("XDG_DATA_HOME")
    config_root = Path(xdg_config) if xdg_config else Path.home() / ".config"
    data_root = Path(xdg_data) if xdg_data else Path.home() / ".local" / "share"
    return AppPaths(config_dir=config_root / "ask", data_dir=data_root / "ask")


DEFAULT_CONFIG: dict = {
    "default_provider": "ollama",
    "providers": {
        "zai": {
            "api_key": "",
            "base_url": "https://api.z.ai/api/anthropic",
            "default_model": "claude-sonnet-4-5-20251001",
            "fast_model": "claude-haiku-4-5-20251001",
            "smart_model": "claude-opus-4-5-20251001",
        },
        "anthropic": {
            "api_key": "",
            "default_model": "claude-sonnet-4-5-20251001",
            "fast_model": "claude-haiku-4-5-20251001",
            "smart_model": "claude-opus-4-6",
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
            "default_model": "glm-5.1:cloud",
            "fast_model": "glm-5.1:cloud",
            "smart_model": "glm-5.1:cloud",
        },
    },
    "defaults": {
        "max_tokens": 4096,
        "quick_max_tokens": 1024,
        "history_ttl_hours": 1,
        "system_prompt": (
            "You are `ask` — the ask-cli terminal AI assistant. You run on a Linux/Ubuntu "
            "system; assume Linux commands, paths, and tools unless the user explicitly "
            "names another OS.\n\n"
            "# Response style\n"
            "- Be concise. Terminal users read in a narrow column — a one-line answer "
            "beats a paragraph when it answers the question.\n"
            "- Prefer a command or code snippet over prose when that's what's being asked.\n"
            "- Fence all code with a language tag (```bash, ```python, ```sql, …) so the "
            "terminal's syntax highlighter and `--code-only` output work correctly.\n"
            '- No preamble ("Sure!", "Here\'s…"), no trailing summary. Answer, stop.\n\n'
            "# Shell commands\n"
            "- Output the smallest command that does the job. No wrapping prose unless "
            "clarifying a real risk.\n"
            "- Never emit destructive commands (`rm -rf`, `dd`, `mkfs`, `: > file`, "
            "unbounded `find -delete`, pipes into `sh`) without an inline warning "
            "describing exactly what gets destroyed.\n"
            "- Assume GNU coreutils and common tools (curl, jq, ripgrep, fd, gh, docker, "
            "kubectl, psql). Flag when a suggestion needs something unusual.\n\n"
            "# About yourself\n"
            "You are ask-cli — a custom terminal AI tool, not Amazon Alexa Skills Kit or "
            "any other tool named `ask`. If the user asks what flags exist or what you "
            "can do, direct them to `ask --help` — that is the source of truth, not your "
            "memory. You know these high-value flags:\n"
            "- `-c` continue last conversation, `--clear` reset it\n"
            "- `--quick` one-liner mode, `--fast` / `--smart` model tiers\n"
            "- `-p <provider>` / `-m <model>` override provider/model\n"
            "- `--cmd` generate a shell command; `--dry-run` / `--execute` variants\n"
            "- `-f <file>` / `-F <glob>` attach files as context\n\n"
            "# Composition\n"
            "This is the base context. Additional instructions may follow (domain "
            "templates, `--quick` suffix, user overrides). They refine this base — "
            "follow them, but keep the response-style rules above unless explicitly "
            "overridden."
        ),
    },
    "features": {
        "clipboard": True,
    },
    "output": {
        "code_theme": "monokai",
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
    quick_max_tokens: int = 1024
    history_ttl_hours: int = 1
    system_prompt: str = ""


@dataclass
class FeaturesConfig:
    clipboard: bool = True


@dataclass
class OutputConfig:
    code_theme: str = "monokai"


@dataclass
class AppConfig:
    default_provider: str = "ollama"
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    # Problems worth telling the user about that don't stop ask from running
    warnings: list[str] = field(default_factory=list)


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base recursively, returning a new dict that shares nothing with
    either input. Missing keys fall back to base."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _write_default_config(path: Path) -> None:
    try:
        write_private_json(path, DEFAULT_CONFIG)
    except StorageError as e:
        raise ConfigError(f"Cannot create default config: {e}") from e


def _migrate_permissions(paths: AppPaths) -> None:
    """Tighten permissions on pre-existing user-data files and dirs that were created
    before v2.3.x. Cheap (a few stat/chmod syscalls). Silent on any failure."""
    for d in (paths.config_dir, paths.data_dir, paths.saved_dir, paths.templates_dir):
        if d.exists():
            with contextlib.suppress(OSError):
                if d.stat().st_mode & 0o077:
                    d.chmod(0o700)
    for f in (paths.history_file, paths.commands_log, paths.stats_file, paths.config_file):
        if f.exists():
            with contextlib.suppress(OSError):
                if f.stat().st_mode & 0o077:
                    f.chmod(0o600)
    if paths.saved_dir.exists():
        for entry in paths.saved_dir.glob("*.json"):
            with contextlib.suppress(OSError):
                if entry.stat().st_mode & 0o077:
                    entry.chmod(0o600)


KNOWN_PROVIDERS = ("zai", "anthropic", "openai", "google", "ollama")
KEYED_PROVIDERS = ("zai", "anthropic", "openai", "google")


def api_key_env_var(provider_id: str) -> str:
    return f"ASK_{provider_id.upper()}_API_KEY"


def _apply_env_overrides(raw: dict) -> dict:
    """Override API keys from ASK_<PROVIDER>_API_KEY environment variables."""
    for provider_id in KEYED_PROVIDERS:
        value = os.environ.get(api_key_env_var(provider_id))
        if value:
            raw.setdefault("providers", {}).setdefault(provider_id, {})["api_key"] = value
    return raw


_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _base_url_warning(provider_name: str, base_url: str, has_api_key: bool) -> str | None:
    """Warn when an API key would travel unencrypted or to an unexpected scheme.

    https:// is fine anywhere; plain http:// only to this machine — or anywhere when
    there's no key to leak (e.g. Ollama on another LAN host).
    """
    if not base_url:
        return None
    parsed = urlparse(base_url)
    scheme = parsed.scheme.lower()
    if scheme == "https":
        return None
    if scheme == "http" and (parsed.hostname in _LOCAL_HOSTS or not has_api_key):
        return None
    return (
        f"Provider '{provider_name}' base_url is '{base_url}' — unencrypted or non-local "
        "URLs can leak your API key. Use https://, or http://localhost for local servers."
    )


def _parse_provider_config(data: dict) -> ProviderConfig:
    return ProviderConfig(
        api_key=data.get("api_key", ""),
        base_url=data.get("base_url", ""),
        default_model=data.get("default_model", ""),
        fast_model=data.get("fast_model", ""),
        smart_model=data.get("smart_model", ""),
    )


_FIX_HINT = "Fix it by hand. Don't delete the file: it holds your settings and may hold API keys."

_PROVIDER_FIELDS = ("api_key", "base_url", "default_model", "fast_model", "smart_model")

# Expected type per key within each top-level section. "positive" means an int > 0.
_SECTION_FIELDS: dict[str, dict[str, type | str]] = {
    "defaults": {
        "max_tokens": "positive",
        "quick_max_tokens": "positive",
        "history_ttl_hours": "positive",
        "system_prompt": str,
    },
    "features": {"clipboard": bool},
    "output": {"code_theme": str},
}


def _type_problem(value: object, expected: type | str) -> str | None:
    if expected == "positive":
        # bool is an int subclass; `true` is never a sensible token count
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            return "must be a positive whole number"
        return None
    if not isinstance(value, expected):  # type: ignore[arg-type]
        return f"must be a {'true/false value' if expected is bool else 'string'}"
    return None


def _validate_shape(raw: object, config_path: Path) -> None:
    """Raise ConfigError naming the offending key if the config has the wrong shape.

    Unknown keys are ignored so older or hand-extended config files keep loading.
    """

    def fail(key_path: str, problem: str) -> NoReturn:
        raise ConfigError(
            f"Invalid config file {config_path}: {key_path} {problem}.", hint=_FIX_HINT
        )

    if not isinstance(raw, dict):
        fail("top level", "must be a JSON object")
    if "default_provider" in raw and not isinstance(raw["default_provider"], str):
        fail("default_provider", "must be a string")

    providers = raw.get("providers", {})
    if not isinstance(providers, dict):
        fail("providers", "must be an object")
    for name, provider in providers.items():
        if not isinstance(provider, dict):
            fail(f"providers.{name}", "must be an object")
        for field_name in _PROVIDER_FIELDS:
            if field_name in provider and not isinstance(provider[field_name], str):
                fail(f"providers.{name}.{field_name}", "must be a string")

    for section, fields in _SECTION_FIELDS.items():
        values = raw.get(section, {})
        if not isinstance(values, dict):
            fail(section, "must be an object")
        for key, expected in fields.items():
            if key in values and (problem := _type_problem(values[key], expected)):
                fail(f"{section}.{key}", problem)


def load_config(paths: AppPaths) -> AppConfig:
    """Load config from disk, creating defaults on first run."""
    _migrate_permissions(paths)
    config_path = paths.config_file

    # _migrate_permissions has already tightened an existing file to 0600
    if not config_path.exists():
        _write_default_config(config_path)

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ConfigError(f"Invalid JSON in config file {config_path}: {e}", hint=_FIX_HINT) from e
    except OSError as e:
        raise ConfigError(f"Cannot read config file {config_path}: {e}") from e
    _validate_shape(raw, config_path)

    merged = _deep_merge(DEFAULT_CONFIG, raw)
    merged = _apply_env_overrides(merged)

    providers = {
        name: _parse_provider_config(provider_data)
        for name, provider_data in merged.get("providers", {}).items()
    }
    warnings = [
        warning
        for name, provider in providers.items()
        if (warning := _base_url_warning(name, provider.base_url, bool(provider.api_key)))
    ]

    defaults_data = merged.get("defaults", {})
    features_data = merged.get("features", {})
    output_data = merged.get("output", {})

    return AppConfig(
        default_provider=merged.get("default_provider", "ollama"),
        providers=providers,
        defaults=DefaultsConfig(
            max_tokens=defaults_data.get("max_tokens", 4096),
            quick_max_tokens=defaults_data.get("quick_max_tokens", 1024),
            history_ttl_hours=defaults_data.get("history_ttl_hours", 1),
            system_prompt=defaults_data.get("system_prompt", ""),
        ),
        features=FeaturesConfig(clipboard=features_data.get("clipboard", True)),
        output=OutputConfig(code_theme=output_data.get("code_theme", "monokai")),
        warnings=warnings,
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


def set_default_provider(config_path: Path, provider_name: str) -> None:
    """Rewrite default_provider in the config file, keeping every other key."""
    if provider_name not in KNOWN_PROVIDERS:
        raise ConfigError(
            f"Unknown provider '{provider_name}'.",
            hint=f"Available providers: {', '.join(KNOWN_PROVIDERS)}",
        )
    try:
        raw = read_json_object(config_path) or {}
        raw["default_provider"] = provider_name
        write_private_json(config_path, raw)
    except StorageError as e:
        raise ConfigError(f"Failed to update config: {e}", hint=_FIX_HINT) from e
