"""Configuration loading, XDG paths, and dataclasses for ask-cli."""

import contextlib
import copy
import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path

from ask_cli.core.storage import write_private_json
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
        "system_prompt_windows": (
            "You are `ask` — a terminal AI assistant running in WSL, invoked from "
            "a Windows workstation. Assume the user is on Windows for OS-specific "
            "questions: give Windows/PowerShell answers first. Only mention macOS "
            "or Linux when the user explicitly asks about them or when cross-"
            "platform context genuinely matters.\n\n"
            "# Response style\n"
            "- Be concise. A direct answer beats a lecture.\n"
            "- Fence code with language tags (```powershell, ```python, ```sql, "
            "…) so syntax highlighting works. Prefer PowerShell fencing for "
            "shell snippets unless the user explicitly wants bash or cmd.\n"
            '- No preamble ("Sure!", "Great question!"), no trailing summary. '
            "Answer, stop.\n\n"
            "# Shell commands\n"
            "- Default to PowerShell syntax for shell commands. Use cmd.exe only "
            "when PowerShell is awkward or the user asks for it. Use Linux/bash "
            "only when the user explicitly mentions WSL, Linux, or bash.\n"
            "- Prefer PowerShell's native cmdlets (`Get-Process`, `Select-String`, "
            "`Restart-Service`) over aliases (`ps`, `sls`). Aliases are fine in "
            "one-liners where verbosity hurts.\n"
            "- Never emit destructive commands (`Remove-Item -Recurse -Force`, "
            "`rm -rf`, `format`, `rmdir /S /Q`) without an inline warning "
            "describing exactly what gets destroyed.\n\n"
            "# About yourself\n"
            "You are ask-cli — a custom terminal AI tool. Not Amazon Alexa Skills "
            "Kit or any other tool named `ask`. You happen to run inside WSL "
            "(Windows Subsystem for Linux) as an implementation detail, but you "
            "treat the user as a Windows user unless they say otherwise. For "
            "flag details, direct the user to `ask --help`.\n\n"
            "# Composition\n"
            "This is the base context. Additional instructions may follow (domain "
            "templates, `--quick` suffix, user overrides). They refine this base."
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
    quick_max_tokens: int = 1024
    history_ttl_hours: int = 1
    system_prompt: str = ""
    system_prompt_windows: str = ""


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
    default_provider: str = "ollama"
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    offline_fallback: OfflineFallbackConfig = field(default_factory=OfflineFallbackConfig)


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


def _check_permissions(path: Path) -> None:
    """Warn (not error) if config file is group/other readable."""
    file_stat = path.stat()
    if file_stat.st_mode & (stat.S_IRGRP | stat.S_IROTH):
        # Import here to avoid circular import at module load time
        from ask_cli.output import render_warning

        render_warning(f"Config file {path} is readable by group/others. Run: chmod 600 {path}")


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


def _validate_base_url(provider_name: str, base_url: str) -> None:
    """Warn if base_url scheme is unusual — an attacker-controlled URL would exfiltrate the API key.

    Accepts https:// (any host) and http:// only for localhost / 127.0.0.1.
    """
    if not base_url:
        return
    from ask_cli.output import render_warning

    lowered = base_url.lower()
    if lowered.startswith("https://"):
        return
    if lowered.startswith(("http://localhost", "http://127.0.0.1", "http://[::1]")):
        return
    render_warning(
        f"Provider '{provider_name}' base_url is '{base_url}' — unencrypted or non-localhost "
        "URLs can leak your API key. Use https:// or http://localhost."
    )


def _parse_provider_config(data: dict, provider_name: str = "") -> ProviderConfig:
    base_url = data.get("base_url", "")
    if provider_name:
        _validate_base_url(provider_name, base_url)
    return ProviderConfig(
        api_key=data.get("api_key", ""),
        base_url=base_url,
        default_model=data.get("default_model", ""),
        fast_model=data.get("fast_model", ""),
        smart_model=data.get("smart_model", ""),
    )


def load_config(paths: AppPaths) -> AppConfig:
    """Load config from disk, creating defaults on first run."""
    _migrate_permissions(paths)
    config_path = paths.config_file

    if not config_path.exists():
        _write_default_config(config_path)
    else:
        _check_permissions(config_path)

    try:
        raw = json.loads(config_path.read_text())
    except json.JSONDecodeError as e:
        raise ConfigError(
            f"Invalid JSON in config file {config_path}: {e}",
            hint="Fix the syntax by hand. Don't delete the file: it holds your settings "
            "and may hold API keys.",
        ) from e

    merged = _deep_merge(DEFAULT_CONFIG, raw)
    merged = _apply_env_overrides(merged)

    providers = {
        name: _parse_provider_config(provider_data, provider_name=name)
        for name, provider_data in merged.get("providers", {}).items()
    }

    defaults_data = merged.get("defaults", {})
    features_data = merged.get("features", {})
    output_data = merged.get("output", {})
    offline_data = merged.get("offline_fallback", {})

    return AppConfig(
        default_provider=merged.get("default_provider", "ollama"),
        providers=providers,
        defaults=DefaultsConfig(
            max_tokens=defaults_data.get("max_tokens", 4096),
            quick_max_tokens=defaults_data.get("quick_max_tokens", 1024),
            history_ttl_hours=defaults_data.get("history_ttl_hours", 1),
            system_prompt=defaults_data.get("system_prompt", ""),
            system_prompt_windows=defaults_data.get("system_prompt_windows", ""),
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
