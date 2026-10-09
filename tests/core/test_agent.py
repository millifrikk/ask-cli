"""Tests for the multi-step terminal agent, driven through a fake UI."""

from collections.abc import Iterable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ask_cli.core.agent import AGENT_EXEC_SYSTEM, AGENT_PLAN_SYSTEM, run_agent
from ask_cli.exceptions import StorageError


class FakeUI:
    def __init__(self, answers: Iterable[bool] = (), recovery: str = "abort") -> None:
        self.answers = list(answers)
        self.recovery = recovery
        self.prompts: list[tuple[str, str | None]] = []
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.steps: list[str] = []
        self.outputs: list[str] = []
        self.recovery_asked = 0

    def stream(self, chunks: Iterable[str]) -> str:
        return "".join(chunks)

    def confirm(self, prompt: str, exact: str | None = None) -> bool:
        self.prompts.append((prompt, exact))
        return self.answers.pop(0) if self.answers else False

    def choose_recovery(self) -> str:
        self.recovery_asked += 1
        return self.recovery

    def info(self, message: str) -> None:
        self.infos.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)

    def show_step(self, step: int, max_steps: int, command: str) -> None:
        self.steps.append(command)

    def show_output(self, output: str) -> None:
        self.outputs.append(output)


def _provider(*responses: str) -> MagicMock:
    provider = MagicMock()
    provider.stream.side_effect = [iter([response]) for response in responses]
    return provider


def _run(provider, ui, tmp_path: Path, **overrides) -> None:
    options = {
        "goal": "do something",
        "provider": provider,
        "model": "test-model",
        "max_tokens": 512,
        "base_system_prompt": None,
        "max_steps": 5,
        "auto_approve": True,
        "dry_run": False,
        "think": None,
        "log_path": tmp_path / "log.txt",
        "ui": ui,
    }
    options.update(overrides)
    run_agent(**options)


@pytest.fixture
def run_step():
    with patch("ask_cli.core.agent.run_command_with_output", return_value=("hi", 0)) as run:
        yield run


def test_plan_needs_approval_even_with_auto_approve(tmp_path, run_step):
    provider = _provider("1. echo hi", "```bash\necho hi\n```")
    ui = FakeUI(answers=[False])
    _run(provider, ui, tmp_path, auto_approve=True)
    assert ui.prompts[0][0].startswith("Proceed with this plan")
    assert provider.stream.call_count == 1
    run_step.assert_not_called()


def test_dry_run_shows_the_plan_and_executes_nothing(tmp_path, run_step):
    provider = _provider("1. rm -rf /tmp/x")
    ui = FakeUI()
    _run(provider, ui, tmp_path, dry_run=True)
    assert provider.stream.call_count == 1
    assert ui.prompts == []
    run_step.assert_not_called()
    assert any("Dry run" in message for message in ui.infos)


def test_base_prompt_and_think_reach_every_model_call(tmp_path, run_step):
    provider = _provider("1. echo hi", "```bash\necho hi\n```", "DONE")
    _run(provider, FakeUI(answers=[True]), tmp_path, base_system_prompt="BASE", think=False)
    plan_call, *exec_calls = provider.stream.call_args_list
    assert plan_call.args[3] == f"BASE\n\n{AGENT_PLAN_SYSTEM}"
    assert all(call.args[3] == f"BASE\n\n{AGENT_EXEC_SYSTEM}" for call in exec_calls)
    assert all(call.kwargs["think"] is False for call in provider.stream.call_args_list)


def test_auto_approve_runs_safe_steps_without_asking(tmp_path, run_step):
    provider = _provider("1. echo hi", "```bash\necho hi\n```", "DONE")
    ui = FakeUI(answers=[True])
    _run(provider, ui, tmp_path)
    assert len(ui.prompts) == 1  # the plan only
    run_step.assert_called_once()
    assert any("complete" in message for message in ui.infos)


def test_destructive_step_needs_the_exact_word_even_with_auto_approve(tmp_path, run_step):
    provider = _provider("1. rm /tmp/x", "```bash\nrm /tmp/x\n```", "DONE")
    ui = FakeUI(answers=[True, False])
    _run(provider, ui, tmp_path)
    assert ui.prompts[1][1] == "yes"
    run_step.assert_not_called()


def test_declined_step_can_be_skipped(tmp_path, run_step):
    provider = _provider("1. echo a", "```bash\necho a\n```", "DONE")
    ui = FakeUI(answers=[True, False], recovery="skip")
    _run(provider, ui, tmp_path, auto_approve=False)
    run_step.assert_not_called()
    last_exec_messages = provider.stream.call_args_list[-1].args[0]
    assert last_exec_messages[-1]["content"].startswith("Step skipped")


def test_declined_step_can_abort(tmp_path, run_step):
    provider = _provider("1. echo a", "```bash\necho a\n```")
    ui = FakeUI(answers=[True, False], recovery="abort")
    _run(provider, ui, tmp_path, auto_approve=False)
    assert any("aborted" in message for message in ui.infos)
    assert provider.stream.call_count == 2


def test_failed_step_reports_and_feeds_back_output(tmp_path):
    provider = _provider("1. false", "```bash\nfalse\n```", "DONE")
    ui = FakeUI(answers=[True], recovery="skip")
    with patch("ask_cli.core.agent.run_command_with_output", return_value=("boom", 3)):
        _run(provider, ui, tmp_path)
    assert any("exit 3" in warning for warning in ui.warnings)
    feedback = provider.stream.call_args_list[-1].args[0][-1]["content"]
    assert "boom" in feedback


def test_command_output_is_truncated_before_reaching_the_model(tmp_path):
    provider = _provider("1. cat big", "```bash\ncat big\n```", "DONE")
    with patch("ask_cli.core.agent.run_command_with_output", return_value=("x" * 50_000, 0)):
        _run(provider, FakeUI(answers=[True]), tmp_path)
    feedback = provider.stream.call_args_list[-1].args[0][-1]["content"]
    assert len(feedback) < 10_000


def test_stops_at_max_steps(tmp_path, run_step):
    provider = _provider("1. echo hi", *["```bash\necho hi\n```"] * 3)
    ui = FakeUI(answers=[True])
    _run(provider, ui, tmp_path, max_steps=3)
    assert any("max steps" in warning for warning in ui.warnings)


def test_stops_when_no_command_found(tmp_path, run_step):
    provider = _provider("1. do the thing", "some prose without a fenced block")
    ui = FakeUI(answers=[True])
    _run(provider, ui, tmp_path)
    assert any("No command" in warning for warning in ui.warnings)


def test_log_failure_warns_and_still_runs(tmp_path, run_step):
    provider = _provider("1. echo hi", "```bash\necho hi\n```", "DONE")
    ui = FakeUI(answers=[True])
    with patch("ask_cli.core.agent.log_command", side_effect=StorageError("Command not logged")):
        _run(provider, ui, tmp_path)
    run_step.assert_called_once()
    assert "Command not logged" in ui.warnings


def test_core_agent_has_no_terminal_io():
    source = (Path(__file__).parents[2] / "src/ask_cli/core/agent.py").read_text()
    for forbidden in ("input(", "Live(", "console", "render_"):
        assert forbidden not in source, forbidden
