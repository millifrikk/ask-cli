"""Argument parsing and entry point for ask-cli."""

import json
import sys

import pyperclip

from ask_cli import __version__
from ask_cli.config import (
    COMMANDS_LOG_PATH,
    CONFIG_PATH,
    HISTORY_PATH,
    SAVED_DIR,
    TEMPLATES_DIR,
    USAGE_STATS_PATH,
    AppConfig,
    load_config,
    resolve_model,
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
from ask_cli.core.files import read_attachments
from ask_cli.core.history import ConversationHistory
from ask_cli.core.saved import delete_saved, list_saved, recall_response, save_response
from ask_cli.core.stats import load_stats, record_query, reset_stats
from ask_cli.core.templates import resolve_system_prompt
from ask_cli.exceptions import (
    AgentError,
    AttachmentError,
    ConfigError,
    ProviderError,
    SavedResponseError,
    TemplateError,
)
from ask_cli.output import (
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


def _build_provider(name: str, config: AppConfig) -> BaseProvider:
    if name not in PROVIDER_CLASSES:
        render_error(
            f"Unknown provider '{name}'.",
            hint=f"Available providers: {', '.join(PROVIDER_CLASSES)}",
        )
        sys.exit(1)
    provider_config = config.providers.get(name)
    if provider_config is None:
        render_error(f"No configuration found for provider '{name}'.")
        sys.exit(1)
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
        render_error(f"No configuration found for provider '{provider_name}'.")
        sys.exit(1)
    models = {
        "default": provider_config.default_model,
        "fast": provider_config.fast_model,
        "smart": provider_config.smart_model,
    }
    render_model_list(provider_name, models, provider_config.default_model)


def _handle_set_default_provider(provider_name: str) -> None:
    if provider_name not in PROVIDER_CLASSES:
        render_error(
            f"Unknown provider '{provider_name}'.",
            hint=f"Available providers: {', '.join(PROVIDER_CLASSES)}",
        )
        sys.exit(1)
    try:
        raw = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
        raw["default_provider"] = provider_name
        CONFIG_PATH.write_text(json.dumps(raw, indent=2))
        render_info(f"Default provider set to '{provider_name}'.")
    except (OSError, json.JSONDecodeError) as e:
        render_error(f"Failed to update config: {e}")
        sys.exit(1)


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


def main() -> None:
    import argparse

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
        "--execute", action="store_true", help="Auto-execute safe commands (use with --cmd)"
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

    args = parser.parse_args()

    if args.no_color:
        disable_color()

    try:
        config = load_config()
    except ConfigError as e:
        render_error(str(e), hint="Fix or delete ~/.config/ask/config.json to reset.")
        sys.exit(1)

    # Management commands — dispatch and exit
    if args.clear:
        history = ConversationHistory(HISTORY_PATH, config.defaults.history_ttl_hours)
        history.clear()
        render_info("Conversation history cleared.")
        return

    if args.list_providers:
        _handle_list_providers(config)
        return

    provider_name = args.provider or config.default_provider

    if args.list_models:
        _handle_list_models(provider_name, config)
        return

    if args.set_default_provider:
        _handle_set_default_provider(args.set_default_provider)
        return

    # Save & recall management — dispatch and exit
    if args.list_saved:
        render_saved_list(list_saved(SAVED_DIR))
        return

    if args.delete_saved:
        try:
            delete_saved(args.delete_saved, SAVED_DIR)
            render_info(f"Deleted saved response '{args.delete_saved}'.")
        except SavedResponseError as e:
            render_error(str(e))
            sys.exit(1)
        return

    if args.recall:
        try:
            entry = recall_response(args.recall, SAVED_DIR)
            render_markdown(entry["response"])
        except SavedResponseError as e:
            render_error(str(e))
            sys.exit(1)
        return

    if args.stats:
        render_stats(load_stats(USAGE_STATS_PATH))
        return

    if args.stats_reset:
        reset_stats(USAGE_STATS_PATH)
        render_info("Statistics reset.")
        return

    # Build the query from positional args and/or piped stdin
    query_parts = list(args.query)
    if not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            query_parts.append(piped)
    query = " ".join(query_parts).strip()

    if not query:
        parser.print_help()
        sys.exit(0)

    if args.file or args.files:
        try:
            file_context = read_attachments(
                args.file or [],
                args.files or [],
                max_file_size=args.max_file_size * 1024,
            )
        except AttachmentError as e:
            render_error(str(e))
            sys.exit(1)
        if file_context:
            query = f"{file_context}\n\n{query}"

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
    try:
        system_prompt = resolve_system_prompt(
            template, args.quick, TEMPLATES_DIR, config.defaults.system_prompt
        )
    except TemplateError as e:
        render_error(str(e))
        sys.exit(1)

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
        try:
            run_agent(
                goal=query,
                provider=provider,
                model=model,
                max_tokens=max_tokens,
                base_system_prompt=system_prompt,
                max_steps=args.agent_max_steps,
                auto_approve=args.auto_approve,
                log_path=COMMANDS_LOG_PATH,
            )
        except AgentError as e:
            render_error(str(e))
            sys.exit(1)
        return

    history = ConversationHistory(HISTORY_PATH, config.defaults.history_ttl_hours)
    use_history = args.continue_session
    if use_history:
        history.load()
    else:
        history.start_new()

    output_mode = _determine_output_mode(args)

    try:
        response = run_query(
            query=query,
            provider=provider,
            model=model,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            history=history,
            use_history=use_history,
            output_mode=output_mode,
            # --quick disables reasoning tokens on models that support it (Qwen3.5
            # via Ollama, etc.) so the token budget doesn't get eaten by thinking.
            think=False if args.quick else None,
        )
    except ProviderError as e:
        hint = None
        if e.status_code == 401:
            hint = f"Set ASK_{provider_name.upper()}_API_KEY or add api_key to config."
        elif e.status_code == 429:
            hint = "Wait a moment and try again, or switch to a different provider."
        render_error(str(e), hint=hint)
        sys.exit(1)

    # --save: persist the response after a successful query
    if args.save and response:
        try:
            save_response(args.save, query, response, SAVED_DIR)
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
            log_command(command, COMMANDS_LOG_PATH)
            exit_code = run_command(command)
            if exit_code != 0:
                render_warning(f"Command exited with code {exit_code}.")
        else:
            if is_destructive(command):
                render_warning("Destructive command detected — confirmation required.")
                confirmation = input("Type 'yes' to execute: ").strip().lower()
                confirmed = confirmation == "yes"
            else:
                answer = input("Execute this command? [y/N]: ").strip().lower()
                confirmed = answer in ("y", "yes")
            if confirmed:
                log_command(command, COMMANDS_LOG_PATH)
                run_command(command)

    # --copy / --copy-code: send response or code block to clipboard
    if args.copy and response:
        try:
            pyperclip.copy(response)
            render_info("Response copied to clipboard.")
        except pyperclip.PyperclipException as e:
            render_warning(f"Clipboard unavailable: {e}. Install xclip or xsel.")

    if args.copy_code and response:
        code = extract_first_code_block(response)
        if code:
            try:
                pyperclip.copy(code)
                render_info("Code copied to clipboard.")
            except pyperclip.PyperclipException as e:
                render_warning(f"Clipboard unavailable: {e}. Install xclip or xsel.")
        else:
            render_warning("No code block found in response.")

    # Record usage stats after a successful query
    if response:
        record_query(USAGE_STATS_PATH, template or "default", len(query), len(response))
