"""Multi-step terminal agent — plan, approve, execute, adapt."""

from pathlib import Path

from rich.live import Live
from rich.markup import escape

from ask_cli.core.commands import (
    extract_command,
    is_destructive,
    log_command,
    run_command_with_output,
)
from ask_cli.output import AskMarkdown, console, render_info, render_warning
from ask_cli.providers.base import BaseProvider

AGENT_PLAN_SYSTEM = (
    "You are a terminal task planner. Given a goal, output a concise numbered plan "
    "of shell commands to accomplish it. One command per step. No prose, no explanation."
)

AGENT_EXEC_SYSTEM = (
    "You are an autonomous terminal agent executing a multi-step plan. "
    "At each turn, output ONLY a single shell command in a ```bash ... ``` block, "
    "or output the single word DONE if the task is complete. "
    "Do not explain. Adapt to command output."
)


def _stream_to_text(
    provider: BaseProvider,
    messages: list[dict[str, str]],
    model: str,
    max_tokens: int,
    system: str,
) -> str:
    """Stream a provider response and return the full text."""
    accumulated: list[str] = []
    with Live(console=console, refresh_per_second=15) as live:
        for chunk in provider.stream(messages, model, max_tokens, system):
            accumulated.append(chunk)
            live.update(AskMarkdown("".join(accumulated)))
    return "".join(accumulated)


def _confirm(prompt: str) -> bool:
    """Prompt user on stdin, return True if they answered y/yes."""
    try:
        answer = input(prompt).strip().lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def _error_recovery_choice() -> str:
    """Ask the user whether to skip the failed step or abort. Returns 'skip' or 'abort'."""
    console.print("[dim]  [s] Skip this step and continue  [a] Abort agent[/dim]")
    try:
        choice = input("Choice [s/a]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "abort"
    return "skip" if choice == "s" else "abort"


def run_agent(
    *,
    goal: str,
    provider: BaseProvider,
    model: str,
    max_tokens: int,
    base_system_prompt: str | None,
    max_steps: int,
    auto_approve: bool,
    log_path: Path,
) -> None:
    """Run the multi-step agent loop: plan, approve, execute, adapt."""
    # Phase 1: generate the plan
    plan_messages: list[dict[str, str]] = [{"role": "user", "content": f"Goal: {goal}"}]
    render_info("Agent: generating plan…")
    plan_text = _stream_to_text(provider, plan_messages, model, max_tokens, AGENT_PLAN_SYSTEM)

    if not auto_approve and not _confirm("Proceed with this plan? [y/N]: "):
        render_info("Agent aborted.")
        return

    # Phase 2: execution loop
    exec_messages: list[dict[str, str]] = [
        {
            "role": "user",
            "content": f"Goal: {goal}\nPlan:\n{plan_text}\nBegin execution.",
        }
    ]

    for step in range(1, max_steps + 1):
        response = _stream_to_text(provider, exec_messages, model, max_tokens, AGENT_EXEC_SYSTEM)

        if response.strip().upper() == "DONE":
            render_info("Agent: task complete.")
            break

        command = extract_command(response)
        if command is None:
            render_warning("No command found in agent response. Stopping.")
            break

        console.print(f"[bold]Step {step}/{max_steps}:[/bold] [cyan]{escape(command)}[/cyan]")

        # Confirmation logic
        if is_destructive(command):
            render_warning("Destructive command — requires explicit confirmation.")
            if not _confirm("Type 'yes' to execute: "):
                exec_messages += [
                    {"role": "assistant", "content": response},
                    {"role": "user", "content": "Step skipped. Continue."},
                ]
                continue
        elif not auto_approve:
            if not _confirm("Execute? [y/N]: "):
                choice = _error_recovery_choice()
                if choice == "abort":
                    render_info("Agent aborted.")
                    break
                exec_messages += [
                    {"role": "assistant", "content": response},
                    {"role": "user", "content": "Step skipped. Continue."},
                ]
                continue

        log_command(command, log_path)
        output, exit_code = run_command_with_output(command)

        if output:
            console.print(f"[dim]{escape(output)}[/dim]")

        if exit_code != 0:
            render_warning(f"Command failed (exit {exit_code}).")
            choice = _error_recovery_choice()
            if choice == "abort":
                render_info("Agent aborted.")
                break
            exec_messages += [
                {"role": "assistant", "content": response},
                {"role": "user", "content": f"Step failed: {output}. Skip and continue."},
            ]
            continue

        exec_messages += [
            {"role": "assistant", "content": response},
            {"role": "user", "content": f"Output (exit {exit_code}):\n{output}\nContinue."},
        ]
    else:
        render_warning(f"Agent reached max steps ({max_steps}).")
