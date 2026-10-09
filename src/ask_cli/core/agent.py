"""Multi-step terminal agent — plan, approve, execute, adapt."""

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from ask_cli.core.commands import (
    extract_command,
    is_destructive,
    log_command,
    run_command_with_output,
    truncate_for_model,
)
from ask_cli.exceptions import StorageError
from ask_cli.providers.base import BaseProvider

AGENT_PLAN_SYSTEM = (
    "Agent mode, planning step. Given a goal, output a concise numbered plan "
    "of shell commands to accomplish it. One command per step. No prose, no explanation."
)

AGENT_EXEC_SYSTEM = (
    "Agent mode, execution step. You are executing a multi-step plan. "
    "At each turn, output ONLY a single shell command in a ```bash ... ``` block, "
    "or output the single word DONE if the task is complete. "
    "Do not explain. Adapt to command output."
)


class AgentUI(Protocol):
    """Everything the agent needs from the terminal, so core/ stays free of I/O."""

    def stream(self, chunks: Iterable[str]) -> str: ...

    def confirm(self, prompt: str, exact: str | None = None) -> bool: ...

    def choose_recovery(self) -> str: ...

    def info(self, message: str) -> None: ...

    def warning(self, message: str) -> None: ...

    def show_step(self, step: int, max_steps: int, command: str) -> None: ...

    def show_output(self, output: str) -> None: ...


def _compose(base: str | None, agent_instructions: str) -> str:
    # Agent instructions go last so they override the base prompt's response style
    return f"{base}\n\n{agent_instructions}" if base else agent_instructions


def run_agent(
    *,
    goal: str,
    provider: BaseProvider,
    model: str,
    max_tokens: int,
    base_system_prompt: str | None,
    max_steps: int,
    auto_approve: bool,
    dry_run: bool,
    think: bool | None,
    log_path: Path,
    ui: AgentUI,
) -> None:
    """Run the agent loop: plan, get approval, then execute and adapt step by step.

    The plan always needs approval; --auto-approve only skips per-step confirmation
    for non-destructive commands. Destructive commands always need the word "yes".
    """
    plan_system = _compose(base_system_prompt, AGENT_PLAN_SYSTEM)
    exec_system = _compose(base_system_prompt, AGENT_EXEC_SYSTEM)

    ui.info("Agent: generating plan…")
    plan_messages = [{"role": "user", "content": f"Goal: {goal}"}]
    plan_text = ui.stream(
        provider.stream(plan_messages, model, max_tokens, plan_system, think=think)
    )

    if dry_run:
        ui.info("Dry run — plan only, nothing executed.")
        return
    if not ui.confirm("Proceed with this plan? [y/N]: "):
        ui.info("Agent aborted.")
        return

    exec_messages = [
        {"role": "user", "content": f"Goal: {goal}\nPlan:\n{plan_text}\nBegin execution."}
    ]

    for step in range(1, max_steps + 1):
        response = ui.stream(
            provider.stream(exec_messages, model, max_tokens, exec_system, think=think)
        )

        if response.strip().upper() == "DONE":
            ui.info("Agent: task complete.")
            return

        command = extract_command(response)
        if command is None:
            ui.warning("No command found in agent response. Stopping.")
            return

        ui.show_step(step, max_steps, command)

        if is_destructive(command):
            ui.warning("Destructive command — requires explicit confirmation.")
            approved = ui.confirm("Type 'yes' to execute: ", exact="yes")
        else:
            approved = auto_approve or ui.confirm("Execute? [y/N]: ")

        if not approved:
            if ui.choose_recovery() == "abort":
                ui.info("Agent aborted.")
                return
            exec_messages += [
                {"role": "assistant", "content": response},
                {"role": "user", "content": "Step skipped. Continue."},
            ]
            continue

        try:
            log_command(command, log_path)
        except StorageError as error:
            ui.warning(str(error))
        output, exit_code = run_command_with_output(command)
        if output:
            ui.show_output(output)
        feedback = truncate_for_model(output)

        if exit_code != 0:
            ui.warning(f"Command failed (exit {exit_code}).")
            if ui.choose_recovery() == "abort":
                ui.info("Agent aborted.")
                return
            exec_messages += [
                {"role": "assistant", "content": response},
                {"role": "user", "content": f"Step failed: {feedback}\nSkip and continue."},
            ]
            continue

        exec_messages += [
            {"role": "assistant", "content": response},
            {"role": "user", "content": f"Output (exit {exit_code}):\n{feedback}\nContinue."},
        ]

    ui.warning(f"Agent reached max steps ({max_steps}).")
