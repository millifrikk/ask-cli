"""Argument parsing and entry point for ask-cli."""

import argparse
import os
import stat
import sys
from pathlib import Path

from ask_cli import __version__
from ask_cli.config import (
    KEYED_PROVIDERS,
    AppConfig,
    DefaultsConfig,
    api_key_env_var,
    load_config,
    resolve_model,
    resolve_paths,
)
from ask_cli.core.agent import run_agent
from ask_cli.core.commands import (
    CMD_SYSTEM_SUFFIX,
    extract_command,
    extract_first_code_block,
    is_destructive,
    log_command,
    run_command,
)
from ask_cli.core.conversation import run_query
from ask_cli.core.fences import is_json_response
from ask_cli.core.files import read_attachments
from ask_cli.core.history import ConversationHistory
from ask_cli.core.saved import delete_saved, list_saved, recall_response, save_response
from ask_cli.core.stats import load_stats, record_query, reset_stats
from ask_cli.core.storage import read_json_object, write_private_json
from ask_cli.core.templates import JSON_SYSTEM_SUFFIX, resolve_system_prompt
from ask_cli.exceptions import (
    AskCLIError,
    ConfigError,
    ModelNotFoundError,
    ProviderError,
    SavedResponseError,
    StorageError,
)
from ask_cli.output import (
    ResponseDisplay,
    confirm,
    copy_to_clipboard,
    disable_color,
    render_error,
    render_info,
    render_markdown,
    render_model_list,
    render_provider_table,
    render_saved_list,
    render_stats,
    render_warning,
)
from ask_cli.providers.anthropic import AnthropicProvider
from ask_cli.providers.base import BaseProvider
from ask_cli.providers.google import GoogleProvider
from ask_cli.providers.ollama import OllamaProvider
from ask_cli.providers.openai import OpenAIProvider
from ask_cli.providers.zai import ZaiProvider

DOMAIN_FLAGS = ("sap", "docker", "sql", "git", "k8s", "aws", "security", "perf")

PROVIDER_CLASSES: dict[str, type[BaseProvider]] = {
    "zai": ZaiProvider,
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "google": GoogleProvider,
    "ollama": OllamaProvider,
}


def _parent_cmdline() -> list[str]:
    """Read `/proc/PPid/cmdline` (NUL-separated) and return argv as a list. Empty on failure."""
    try:
        with open(f"/proc/{os.getppid()}/cmdline", "rb") as f:
            raw = f.read().decode("utf-8", errors="replace")
        return [arg for arg in raw.split("\0") if arg]
    except OSError:
        return []


def _invocation_is_interactive_wsl() -> bool:
    """True if we're in an interactive WSL shell — user typed this, not proxied by wsl.exe.

    Three signals must all agree:
      1. We're in WSL (`WSL_DISTRO_NAME` or `WSL_INTEROP` set).
      2. At least one of stdin/stdout is a TTY. Under Windows Terminal + ConPTY
         this isn't enough on its own because wsl.exe proxies a TTY through.
      3. The parent process is an interactive shell — specifically, its argv
         does NOT contain `-c` and it isn't `/init`. `wsl.exe <cmd>` spawns
         `bash -c "<cmd>"` to parse the command line, which has `-c`. A shell
         a user typed `ask "..."` into has no `-c` (it's reading from a TTY).
    """
    try:
        in_wsl = bool(os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"))
        if not in_wsl:
            return False
        if not (sys.stdin.isatty() or sys.stdout.isatty()):
            return False
        argv = _parent_cmdline()
        if not argv:
            return False
        if "-c" in argv:
            return False
        return not (argv[0].endswith("/init") or argv[0] == "init")
    except (AttributeError, OSError):
        return False


def _select_base_system_prompt(defaults: DefaultsConfig) -> str:
    """Pick the system prompt for the current invocation context.

    `ASK_CONTEXT=windows` selects the Windows/general prompt; anything else uses
    the Linux default. Set by the PowerShell wrapper (Path A) or the User-scope
    env var + WSLENV propagation (Path B).

    Because `WSLENV=ASK_CONTEXT/u` propagates the value into *every* WSL session
    — not just ones spawned by `wsl.exe` from PowerShell — we additionally
    override back to Linux when we can detect the user is typing directly in an
    interactive WSL terminal.
    """
    context = os.environ.get("ASK_CONTEXT", "linux").lower()
    if context == "windows" and _invocation_is_interactive_wsl():
        context = "linux"
    if context == "windows" and defaults.system_prompt_windows:
        return defaults.system_prompt_windows
    return defaults.system_prompt


def _build_provider(name: str, config: AppConfig) -> BaseProvider:
    if name not in PROVIDER_CLASSES:
        raise ConfigError(
            f"Unknown provider '{name}'.",
            hint=f"Available providers: {', '.join(PROVIDER_CLASSES)}",
        )
    provider_config = config.providers.get(name)
    if provider_config is None:
        raise ConfigError(
            f"No configuration found for provider '{name}'.",
            hint=f"Add a providers.{name} section to your config file.",
        )
    return PROVIDER_CLASSES[name](provider_config)


def _handle_list_providers(config: AppConfig) -> None:
    rows = []
    for name, provider_class in PROVIDER_CLASSES.items():
        provider_config = config.providers.get(name)
        if provider_config is None:
            rows.append((name, "not configured", ""))
            continue
        provider = provider_class(provider_config)
        status = "configured" if provider.is_configured() else "not configured"
        rows.append((name, status, provider_config.default_model))
    render_provider_table(rows)


def _handle_list_models(provider_name: str, config: AppConfig) -> None:
    provider_config = config.providers.get(provider_name)
    if provider_config is None:
        raise ConfigError(
            f"No configuration found for provider '{provider_name}'.",
            hint=f"Available providers: {', '.join(PROVIDER_CLASSES)}",
        )
    models = {
        "default": provider_config.default_model,
        "fast": provider_config.fast_model,
        "smart": provider_config.smart_model,
    }
    render_model_list(provider_name, models)


def _check_completeness(
    response: str, stop_reason: str | None, max_tokens: int, quick: bool
) -> None:
    longer = "drop --quick" if quick else "raise defaults.max_tokens in your config"
    if not response:
        if stop_reason == "filtered":
            raise AskCLIError(
                "The model returned an empty response: it was blocked by a content filter.",
                hint="Rephrase the question, or try another provider with -p.",
            )
        hint = (
            f"The {max_tokens}-token limit was used up before any text (reasoning models do "
            f"this); {longer}."
            if stop_reason == "max_tokens"
            else "Try again, or try another model with --smart or -p."
        )
        raise AskCLIError("The model returned an empty response.", hint=hint)
    if stop_reason == "max_tokens":
        render_warning(f"Response was cut off at the {max_tokens}-token limit; {longer}.")


def _read_piped_stdin() -> str:
    # Only read when stdin is a pipe or a redirected file. A TTY, /dev/null or an
    # IDE's never-closed stdin (character device or socket) would block forever.
    try:
        mode = os.fstat(sys.stdin.fileno()).st_mode
    except (AttributeError, OSError, ValueError):
        return ""
    if not (stat.S_ISFIFO(mode) or stat.S_ISREG(mode)):
        return ""
    return sys.stdin.read().strip()


def _log_command_or_warn(command: str, log_path: Path) -> None:
    # The log is an audit trail, not a safety gate: warn rather than block the command
    try:
        log_command(command, log_path)
    except StorageError as error:
        render_warning(str(error))


def _handle_set_default_provider(provider_name: str, config_path: Path) -> None:
    if provider_name not in PROVIDER_CLASSES:
        raise ConfigError(
            f"Unknown provider '{provider_name}'.",
            hint=f"Available providers: {', '.join(PROVIDER_CLASSES)}",
        )
    try:
        raw = read_json_object(config_path) or {}
        raw["default_provider"] = provider_name
        write_private_json(config_path, raw)
    except StorageError as e:
        raise ConfigError(f"Failed to update config: {e}") from e
    render_info(f"Default provider set to '{provider_name}'.")


def _determine_output_mode(args) -> str:
    if args.markdown:
        return "markdown"
    if args.raw:
        return "raw"
    if args.code_only:
        return "code"
    if args.json:
        return "json"
    return "markdown"


def _determine_template(args) -> str | None:
    for name in DOMAIN_FLAGS:
        if getattr(args, name, False):
            return name
    if args.explain:
        return "explain"
    if args.fix:
        return "fix"
    if args.optimize:
        return "optimize"
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ask",
        description="Terminal AI assistant",
    )

    parser.add_argument("--version", action="version", version=f"ask {__version__}")

    parser.add_argument("query", nargs="*", help="Question or prompt")

    # Provider selection
    provider_group = parser.add_argument_group("provider")
    provider_group.add_argument("-p", "--provider", help="Provider to use")
    provider_group.add_argument("-m", "--model", help="Explicit model name")
    provider_group.add_argument("--fast", action="store_true", help="Use the fast model tier")
    provider_group.add_argument("--smart", action="store_true", help="Use the smart model tier")

    # History
    history_group = parser.add_argument_group("history")
    history_group.add_argument(
        "-c",
        "--continue",
        dest="continue_session",
        action="store_true",
        help="Continue the previous conversation",
    )
    history_group.add_argument(
        "--clear", action="store_true", help="Clear conversation history and exit"
    )

    # Output formatting
    fmt_group = parser.add_argument_group("output")
    fmt_group.add_argument("--markdown", action="store_true", help="Render output as markdown")
    fmt_group.add_argument("--raw", action="store_true", help="Print raw output with no formatting")
    fmt_group.add_argument(
        "--code-only", action="store_true", help="Extract and display only code blocks"
    )
    fmt_group.add_argument(
        "--json", action="store_true", help="Output raw JSON (model must produce it)"
    )
    fmt_group.add_argument(
        "--quick", action="store_true", help="Terse one-liner response (1024 tokens)"
    )
    fmt_group.add_argument(
        "--no-color", action="store_true", help="Disable color and rich formatting"
    )

    # Attachments
    attach_group = parser.add_argument_group("attachments")
    attach_group.add_argument(
        "-f",
        "--file",
        action="append",
        dest="file",
        metavar="FILE",
        help="Attach a file as context",
    )
    attach_group.add_argument(
        "-F",
        "--files",
        action="append",
        dest="files",
        metavar="PATTERN",
        help="Attach files matching a glob pattern (recursive)",
    )
    attach_group.add_argument(
        "--max-file-size",
        type=int,
        default=100,
        metavar="KB",
        help="Max size per file in KB (default: 100)",
    )

    # Templates
    tmpl_group = parser.add_argument_group("templates")
    tmpl_group.add_argument("--explain", action="store_true", help="Use the explain template")
    tmpl_group.add_argument("--fix", action="store_true", help="Use the fix template")
    tmpl_group.add_argument("--optimize", action="store_true", help="Use the optimize template")

    # Domain modes
    domain_group = parser.add_argument_group("domain modes")
    for _flag in DOMAIN_FLAGS:
        domain_group.add_argument(
            f"--{_flag}", action="store_true", help=f"{_flag.upper()} expert mode"
        )

    # Save & recall
    saved_group = parser.add_argument_group("save & recall")
    saved_group.add_argument("--save", metavar="NAME", help="Save response with a name")
    saved_group.add_argument("--recall", metavar="NAME", help="Recall a saved response by name")
    saved_group.add_argument("--list-saved", action="store_true", help="List all saved responses")
    saved_group.add_argument(
        "--delete-saved", metavar="NAME", help="Delete a saved response by name"
    )

    # Command execution
    cmd_group = parser.add_argument_group("command execution")
    cmd_group.add_argument(
        "--cmd", action="store_true", help="Generate a shell command instead of prose"
    )
    cmd_group.add_argument(
        "--dry-run", action="store_true", help="Show command without executing (use with --cmd)"
    )
    cmd_group.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Auto-execute commands that don't match destructive patterns. "
            "The pattern list is a best-effort allowlist, not a sandbox — review before trusting."
        ),
    )

    # Agent
    agent_group = parser.add_argument_group("agent")
    agent_group.add_argument("--agent", action="store_true", help="Enable agent mode")
    agent_group.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve non-destructive commands in agent mode",
    )
    agent_group.add_argument(
        "--agent-max-steps",
        type=int,
        default=10,
        metavar="N",
        help="Max agent steps (default: 10)",
    )

    # Clipboard
    clip_group = parser.add_argument_group("clipboard")
    clip_group.add_argument("--copy", action="store_true", help="Copy response to clipboard")
    clip_group.add_argument(
        "--copy-code", action="store_true", help="Copy first code block to clipboard"
    )

    # Statistics
    stats_group = parser.add_argument_group("statistics")
    stats_group.add_argument("--stats", action="store_true", help="Show usage statistics")
    stats_group.add_argument("--stats-reset", action="store_true", help="Reset usage statistics")

    # Management
    mgmt_group = parser.add_argument_group("management")
    mgmt_group.add_argument(
        "--list-providers", action="store_true", help="List available providers"
    )
    mgmt_group.add_argument("--list-models", action="store_true", help="List models for a provider")
    mgmt_group.add_argument(
        "--set-default-provider", metavar="PROVIDER", help="Set the default provider"
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.no_color:
        disable_color()

    # The single error boundary: business logic raises typed errors carrying an
    # actionable hint; nothing below this point prints a traceback or exits.
    try:
        return _run(args, parser)
    except ProviderError as error:
        render_error(str(error), hint=error.hint or _provider_hint(error))
        return 1
    except AskCLIError as error:
        render_error(str(error), hint=error.hint)
        return 1
    except KeyboardInterrupt:
        render_info("Interrupted.")
        return 130


def _provider_hint(error: ProviderError) -> str | None:
    if isinstance(error, ModelNotFoundError):
        return f"Run `ask -p {error.provider} --list-models` to see the configured models."
    if error.status_code == 401 and error.provider in KEYED_PROVIDERS:
        return (
            f"Check {api_key_env_var(error.provider)} or "
            f"providers.{error.provider}.api_key in your config file."
        )
    if error.status_code == 429:
        return "Wait a moment and try again, or switch provider with -p."
    return None


def _run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    paths = resolve_paths()
    config = load_config(paths)

    # Management commands — dispatch and exit
    if args.clear:
        history = ConversationHistory(paths.history_file, config.defaults.history_ttl_hours)
        history.clear()
        render_info("Conversation history cleared.")
        return 0

    if args.list_providers:
        _handle_list_providers(config)
        return 0

    provider_name = args.provider or config.default_provider

    if args.list_models:
        _handle_list_models(provider_name, config)
        return 0

    if args.set_default_provider:
        _handle_set_default_provider(args.set_default_provider, paths.config_file)
        return 0

    # Save & recall management — dispatch and exit
    if args.list_saved:
        render_saved_list(list_saved(paths.saved_dir))
        return 0

    if args.delete_saved:
        delete_saved(args.delete_saved, paths.saved_dir)
        render_info(f"Deleted saved response '{args.delete_saved}'.")
        return 0

    if args.recall:
        entry = recall_response(args.recall, paths.saved_dir)
        render_markdown(entry["response"])
        return 0

    if args.stats:
        render_stats(load_stats(paths.stats_file))
        return 0

    if args.stats_reset:
        reset_stats(paths.stats_file)
        render_info("Statistics reset.")
        return 0

    # Build the query from positional args and/or piped stdin
    query_parts = [" ".join(args.query).strip(), _read_piped_stdin()]
    query = "\n\n".join(part for part in query_parts if part)

    if not query:
        parser.print_usage(sys.stderr)
        render_error("No question given.", hint='Try: ask "your question"  (or ask --help)')
        return 2

    if args.file or args.files:
        attachments = read_attachments(
            args.file or [],
            args.files or [],
            max_file_size=args.max_file_size * 1024,
        )
        for warning in attachments.warnings:
            render_warning(warning)
        if attachments.text:
            query = f"{attachments.text}\n\n{query}"

    provider = _build_provider(provider_name, config)

    model = resolve_model(
        config,
        provider_name,
        fast=args.fast,
        smart=args.smart,
        explicit=args.model,
    )

    max_tokens = config.defaults.quick_max_tokens if args.quick else config.defaults.max_tokens

    template = _determine_template(args)
    system_prompt = resolve_system_prompt(
        template, args.quick, paths.templates_dir, _select_base_system_prompt(config.defaults)
    )

    # Inject command-generation suffix when in cmd mode
    cmd_mode = args.cmd or args.dry_run
    if cmd_mode:
        system_prompt = (
            f"{system_prompt}\n\n{CMD_SYSTEM_SUFFIX}" if system_prompt else CMD_SYSTEM_SUFFIX
        )
        # --cmd generates a single shell command — auto-copy it so the user
        # can paste directly without clicking around the terminal.
        if not args.copy_code:
            args.copy_code = True

    # --agent: run the multi-step agent loop and return
    if args.agent:
        run_agent(
            goal=query,
            provider=provider,
            model=model,
            max_tokens=max_tokens,
            base_system_prompt=system_prompt,
            max_steps=args.agent_max_steps,
            auto_approve=args.auto_approve,
            log_path=paths.commands_log,
        )
        return 0

    history = ConversationHistory(paths.history_file, config.defaults.history_ttl_hours)
    use_history = args.continue_session
    if use_history:
        if not history.load():
            render_info("No recent conversation to continue — starting a new conversation.")
    else:
        history.start_new()

    output_mode = _determine_output_mode(args)
    if output_mode == "json":
        system_prompt = (
            f"{system_prompt}\n\n{JSON_SYSTEM_SUFFIX}" if system_prompt else JSON_SYSTEM_SUFFIX
        )

    with ResponseDisplay(output_mode) as display:
        response = run_query(
            query=query,
            provider=provider,
            model=model,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            history=history,
            use_history=use_history,
            on_chunk=display.update,
            # --quick disables reasoning tokens on models that support it (Qwen3.5
            # via Ollama, etc.) so the token budget doesn't get eaten by thinking.
            think=False if args.quick else None,
        )

    _check_completeness(response, provider.last_stop_reason, max_tokens, quick=args.quick)

    if output_mode == "json" and response and not is_json_response(response):
        render_warning("The model's response is not valid JSON.")

    # --save: persist the response after a successful query
    if args.save and response:
        try:
            save_response(args.save, query, response, paths.saved_dir)
            render_info(f"Saved response as '{args.save}'.")
        except SavedResponseError as e:
            render_error(str(e))

    # --cmd: extract and optionally execute the generated command
    if cmd_mode and response:
        command = extract_command(response)
        if command is None:
            render_warning("Could not extract a command from the response.")
        elif args.dry_run:
            render_info("Dry run — command not executed.")
        elif args.execute and not is_destructive(command):
            _log_command_or_warn(command, paths.commands_log)
            exit_code = run_command(command)
            if exit_code != 0:
                render_warning(f"Command exited with code {exit_code}.")
        elif not sys.stdin.isatty():
            # Piped input means there is nobody to answer a prompt
            render_warning(
                "Not executing: stdin is not a terminal, so confirmation can't be asked. "
                "The command was printed above; run it yourself."
            )
        else:
            destructive = is_destructive(command)
            if destructive:
                render_warning("Destructive command detected — confirmation required.")
            confirmed = (
                confirm("Type 'yes' to execute: ", exact="yes")
                if destructive
                else confirm("Execute this command? [y/N]: ")
            )
            if confirmed:
                _log_command_or_warn(command, paths.commands_log)
                run_command(command)

    # --copy / --copy-code: send response or code block to clipboard
    if args.copy and response:
        copy_to_clipboard(response, "Response")

    if args.copy_code and response:
        code = extract_first_code_block(response)
        if code:
            copy_to_clipboard(code, "Code")
        else:
            render_warning("No code block found in response.")

    # Record usage stats after a successful query; a stats failure must not lose the answer
    if response:
        try:
            record_query(paths.stats_file, template or "default", len(query), len(response))
        except StorageError as error:
            render_warning(f"Usage statistics not recorded: {error}")

    return 0
