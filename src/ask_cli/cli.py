"""Argument parsing and entry point for ask-cli."""

import argparse
import os
import stat
import sys
from dataclasses import dataclass

from ask_cli import __version__
from ask_cli.config import (
    KEYED_PROVIDERS,
    AppConfig,
    AppPaths,
    api_key_env_var,
    load_config,
    resolve_model,
    resolve_paths,
    set_default_provider,
)
from ask_cli.core.agent import run_agent
from ask_cli.core.commands import (
    CMD_SYSTEM_SUFFIX,
    extract_first_code_block,
    handle_generated_command,
)
from ask_cli.core.context import select_base_system_prompt
from ask_cli.core.conversation import check_completeness, run_query
from ask_cli.core.fences import is_json_response
from ask_cli.core.files import read_attachments
from ask_cli.core.history import ConversationHistory
from ask_cli.core.saved import (
    delete_saved,
    list_saved,
    recall_response,
    save_response,
    validate_name,
)
from ask_cli.core.stats import load_stats, record_query, reset_stats
from ask_cli.core.templates import JSON_SYSTEM_SUFFIX, join_prompt, resolve_system_prompt
from ask_cli.exceptions import (
    AskCLIError,
    ConfigError,
    ModelNotFoundError,
    ProviderError,
    SavedResponseError,
    StorageError,
)
from ask_cli.output import (
    ConsoleUI,
    ResponseDisplay,
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
    set_code_theme,
)
from ask_cli.providers import PROVIDER_CLASSES, get_provider, provider_statuses
from ask_cli.providers.base import BaseProvider

DOMAIN_FLAGS = ("sap", "docker", "sql", "git", "k8s", "aws", "security", "perf")


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


TASK_FLAGS = ("explain", "fix", "optimize")

DEFAULT_AGENT_MAX_STEPS = 10

# Flags that perform a one-off action and exit; at most one per run, and no question.
MANAGEMENT_FLAGS = (
    "clear",
    "list_providers",
    "list_models",
    "set_default_provider",
    "list_saved",
    "delete_saved",
    "recall",
    "stats",
    "stats_reset",
)

# Flags that only make sense for a normal answer, not for --agent.
NOT_WITH_AGENT = ("save", "continue_session", "copy", "copy_code", "cmd", "execute")


def _determine_output_mode(args: argparse.Namespace) -> str:
    if args.raw:
        return "raw"
    if args.code_only:
        return "code"
    if args.json:
        return "json"
    return "markdown"


def _determine_templates(args: argparse.Namespace) -> list[str]:
    # Domain first, then the task, then a user template: each refines the previous one
    names = [name for name in (*DOMAIN_FLAGS, *TASK_FLAGS) if getattr(args, name)]
    if args.template:
        names.append(args.template)
    return names


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' is not a whole number") from None
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {value}")
    return value


def _flag_name(dest: str) -> str:
    return "-c/--continue" if dest == "continue_session" else f"--{dest.replace('_', '-')}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ask",
        description="Terminal AI assistant",
    )

    parser.add_argument("--version", action="version", version=f"ask {__version__}")

    parser.add_argument("query", nargs="*", help="Question or prompt")

    # Provider selection
    provider_group = parser.add_argument_group("provider")
    provider_group.add_argument(
        "-p", "--provider", choices=PROVIDER_CLASSES, metavar="PROVIDER", help="Provider to use"
    )
    tier = provider_group.add_mutually_exclusive_group()
    tier.add_argument("-m", "--model", help="Explicit model name")
    tier.add_argument("--fast", action="store_true", help="Use the fast model tier")
    tier.add_argument("--smart", action="store_true", help="Use the smart model tier")

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
    output_mode = fmt_group.add_mutually_exclusive_group()
    output_mode.add_argument(
        "--markdown", action="store_true", help="Render output as markdown (default)"
    )
    output_mode.add_argument(
        "--raw", action="store_true", help="Print raw output with no formatting"
    )
    output_mode.add_argument(
        "--code-only", action="store_true", help="Extract and display only code blocks"
    )
    output_mode.add_argument(
        "--json", action="store_true", help="Ask the model for JSON and print only that"
    )
    fmt_group.add_argument(
        "--quick", action="store_true", help="Terse one-liner response (small token budget)"
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
        type=_positive_int,
        default=100,
        metavar="KB",
        help="Max size per file in KB (default: 100)",
    )

    # Templates: one task template, one domain, and/or one user template — they compose
    tmpl_group = parser.add_argument_group("templates (combine with a domain mode)")
    task = tmpl_group.add_mutually_exclusive_group()
    task.add_argument("--explain", action="store_true", help="Use the explain template")
    task.add_argument("--fix", action="store_true", help="Use the fix template")
    task.add_argument("--optimize", action="store_true", help="Use the optimize template")
    tmpl_group.add_argument(
        "--template",
        metavar="NAME",
        help="Use your own template from the templates directory (NAME.yaml)",
    )

    # Domain modes
    domain_group = parser.add_argument_group("domain modes")
    domain = domain_group.add_mutually_exclusive_group()
    for _flag in DOMAIN_FLAGS:
        domain.add_argument(f"--{_flag}", action="store_true", help=f"{_flag.upper()} expert mode")

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
        "--dry-run",
        action="store_true",
        help="Show the command (or, with --agent, the plan) without executing anything",
    )
    cmd_group.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Generate a command (implies --cmd) and run it if it doesn't match a destructive "
            "pattern. The pattern list is best-effort, not a sandbox — review before trusting."
        ),
    )

    # Agent
    agent_group = parser.add_argument_group("agent")
    agent_group.add_argument("--agent", action="store_true", help="Enable agent mode")
    agent_group.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve non-destructive commands in agent mode (the plan is always shown "
        "for approval)",
    )
    agent_group.add_argument(
        "--agent-max-steps",
        type=_positive_int,
        metavar="N",
        help=f"Max agent steps (default: {DEFAULT_AGENT_MAX_STEPS})",
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
    mgmt_group.add_argument(
        "--list-models", action="store_true", help="List models for a provider (see -p)"
    )
    mgmt_group.add_argument(
        "--set-default-provider",
        choices=PROVIDER_CLASSES,
        metavar="PROVIDER",
        help="Set the default provider",
    )

    return parser


def _validate_flag_combinations(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Reject combinations argparse groups can't express (exits with status 2)."""
    actions = [_flag_name(dest) for dest in MANAGEMENT_FLAGS if getattr(args, dest)]
    if len(actions) > 1:
        parser.error(f"{' and '.join(actions)} can't be combined; run them separately")
    if actions and args.query:
        parser.error(f"{actions[0]} doesn't take a question")

    if args.execute and args.dry_run:
        parser.error("--execute and --dry-run contradict each other")

    if args.agent:
        conflicts = [_flag_name(dest) for dest in NOT_WITH_AGENT if getattr(args, dest)]
        if conflicts:
            parser.error(f"{', '.join(conflicts)} can't be used with --agent")
    else:
        if args.auto_approve:
            parser.error("--auto-approve only applies to --agent")
        if args.agent_max_steps is not None:
            parser.error("--agent-max-steps only applies to --agent")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)
    _validate_flag_combinations(args, parser)
    if args.execute:
        args.cmd = True
    args.agent_max_steps = args.agent_max_steps or DEFAULT_AGENT_MAX_STEPS
    args.usage = parser.format_usage()
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.no_color:
        disable_color()

    # The single error boundary: business logic raises typed errors carrying an
    # actionable hint; nothing below this point prints a traceback or exits.
    try:
        return _run(args)
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


@dataclass
class _Request:
    query: str
    provider: BaseProvider
    model: str
    max_tokens: int
    system_prompt: str | None
    cmd_mode: bool
    stats_mode: str


def _run(args: argparse.Namespace) -> int:
    paths = resolve_paths()
    config = load_config(paths)
    set_code_theme(config.output.code_theme)
    for warning in config.warnings:
        render_warning(warning)
    provider_name = args.provider or config.default_provider

    if any(getattr(args, flag) for flag in MANAGEMENT_FLAGS):
        _run_management(args, config, paths, provider_name)
        return 0

    if args.save:
        validate_name(args.save)  # fail before spending an API call

    request = _prepare_request(args, config, paths, provider_name)
    if request is None:
        sys.stderr.write(args.usage)
        render_error("No question given.", hint='Try: ask "your question"  (or ask --help)')
        return 2

    if args.agent:
        run_agent(
            goal=request.query,
            provider=request.provider,
            model=request.model,
            max_tokens=request.max_tokens,
            base_system_prompt=request.system_prompt,
            max_steps=args.agent_max_steps,
            auto_approve=args.auto_approve,
            dry_run=args.dry_run,
            think=False if args.quick else None,
            log_path=paths.commands_log,
            ui=ConsoleUI(),
        )
        _record_stats(paths, request, response="")
        return 0

    return _answer(args, config, paths, request)


def _run_management(
    args: argparse.Namespace, config: AppConfig, paths: AppPaths, provider_name: str
) -> None:
    if args.clear:
        ConversationHistory(paths.history_file, config.defaults.history_ttl_hours).clear()
        render_info("Conversation history cleared.")
    elif args.list_providers:
        render_provider_table(provider_statuses(config))
    elif args.list_models:
        _handle_list_models(provider_name, config)
    elif args.set_default_provider:
        set_default_provider(paths.config_file, args.set_default_provider)
        render_info(f"Default provider set to '{args.set_default_provider}'.")
    elif args.list_saved:
        render_saved_list(list_saved(paths.saved_dir))
    elif args.delete_saved:
        delete_saved(args.delete_saved, paths.saved_dir)
        render_info(f"Deleted saved response '{args.delete_saved}'.")
    elif args.recall:
        render_markdown(recall_response(args.recall, paths.saved_dir)["response"])
    elif args.stats:
        render_stats(load_stats(paths.stats_file))
    elif args.stats_reset:
        reset_stats(paths.stats_file)
        render_info("Statistics reset.")


def _prepare_request(
    args: argparse.Namespace, config: AppConfig, paths: AppPaths, provider_name: str
) -> _Request | None:
    question = "\n\n".join(
        part for part in (" ".join(args.query).strip(), _read_piped_stdin()) if part
    )
    if not question:
        return None

    query = question
    if args.file or args.files:
        attachments = read_attachments(
            args.file or [], args.files or [], max_file_size=args.max_file_size * 1024
        )
        for warning in attachments.warnings:
            render_warning(warning)
        if attachments.text:
            query = f"{attachments.text}\n\n{question}"

    provider = get_provider(provider_name, config)
    model = resolve_model(
        config, provider_name, fast=args.fast, smart=args.smart, explicit=args.model
    )
    max_tokens = config.defaults.quick_max_tokens if args.quick else config.defaults.max_tokens

    templates = _determine_templates(args)
    system_prompt = resolve_system_prompt(
        templates, args.quick, paths.templates_dir, select_base_system_prompt(config.defaults)
    )
    cmd_mode = args.cmd or (args.dry_run and not args.agent)
    if cmd_mode:
        system_prompt = join_prompt(system_prompt, CMD_SYSTEM_SUFFIX)
    if _determine_output_mode(args) == "json":
        system_prompt = join_prompt(system_prompt, JSON_SYSTEM_SUFFIX)

    labels = [*templates]
    labels += [label for label, on in (("cmd", cmd_mode), ("quick", args.quick)) if on]
    stats_mode = "agent" if args.agent else "+".join(labels) or "default"

    return _Request(query, provider, model, max_tokens, system_prompt, cmd_mode, stats_mode)


def _answer(args: argparse.Namespace, config: AppConfig, paths: AppPaths, request: _Request) -> int:
    history = ConversationHistory(paths.history_file, config.defaults.history_ttl_hours)
    use_history = args.continue_session
    if use_history:
        if not history.load():
            render_info("No recent conversation to continue — starting a new conversation.")
    else:
        history.start_new()

    output_mode = _determine_output_mode(args)
    with ResponseDisplay(output_mode) as display:
        response = run_query(
            query=request.query,
            provider=request.provider,
            model=request.model,
            max_tokens=request.max_tokens,
            system_prompt=request.system_prompt,
            history=history,
            use_history=use_history,
            on_chunk=display.update,
            # --quick disables reasoning tokens on models that support it (Qwen3.5
            # via Ollama, etc.) so the token budget doesn't get eaten by thinking.
            think=False if args.quick else None,
        )

    stop_reason = request.provider.last_stop_reason
    if warning := check_completeness(response, stop_reason, request.max_tokens, args.quick):
        render_warning(warning)
    if output_mode == "json" and not is_json_response(response):
        render_warning("The model's response is not valid JSON.")

    exit_code = 0
    # A failed save is reported but doesn't skip the steps below
    if args.save:
        try:
            save_response(args.save, request.query, response, paths.saved_dir)
            render_info(f"Saved response as '{args.save}'.")
        except SavedResponseError as error:
            render_error(str(error), hint=error.hint)
            exit_code = 1

    if request.cmd_mode:
        handle_generated_command(
            response,
            dry_run=args.dry_run,
            auto_execute=args.execute,
            can_prompt=sys.stdin.isatty(),
            log_path=paths.commands_log,
            ui=ConsoleUI(),
        )

    if args.copy:
        copy_to_clipboard(response, "Response")
    # --cmd auto-copies the command unless disabled in config or --copy took the response
    auto_copy = request.cmd_mode and config.features.clipboard and not args.copy
    if args.copy_code or auto_copy:
        code = extract_first_code_block(response)
        if code:
            copy_to_clipboard(code, "Code")
        else:
            render_warning("No code block found in response.")

    _record_stats(paths, request, response)
    return exit_code


def _record_stats(paths: AppPaths, request: _Request, response: str) -> None:
    # A stats failure must never lose the answer: warn and move on
    try:
        record_query(paths.stats_file, request.stats_mode, len(request.query), len(response))
    except StorageError as error:
        render_warning(f"Usage statistics not recorded: {error}")
