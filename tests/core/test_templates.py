"""Tests for template resolution — built-ins, quick mode, user YAML."""

from pathlib import Path

import pytest

from ask_cli.core.templates import BUILTIN_TEMPLATES, QUICK_SUFFIX, resolve_system_prompt
from ask_cli.exceptions import TemplateError


@pytest.fixture
def user_templates_dir(tmp_path) -> Path:
    return tmp_path / "templates"


def test_no_template_no_quick_returns_none(user_templates_dir):
    result = resolve_system_prompt(None, quick=False, user_templates_dir=user_templates_dir)
    assert result is None


def test_quick_only_returns_quick_suffix(user_templates_dir):
    result = resolve_system_prompt(None, quick=True, user_templates_dir=user_templates_dir)
    assert result == QUICK_SUFFIX


def test_builtin_explain(user_templates_dir):
    result = resolve_system_prompt("explain", quick=False, user_templates_dir=user_templates_dir)
    assert result == BUILTIN_TEMPLATES["explain"]
    assert "explain" in result.lower() or "explainer" in result.lower()


def test_builtin_fix(user_templates_dir):
    result = resolve_system_prompt("fix", quick=False, user_templates_dir=user_templates_dir)
    assert result == BUILTIN_TEMPLATES["fix"]


def test_builtin_optimize(user_templates_dir):
    result = resolve_system_prompt("optimize", quick=False, user_templates_dir=user_templates_dir)
    assert result == BUILTIN_TEMPLATES["optimize"]


def test_template_plus_quick_composes(user_templates_dir):
    result = resolve_system_prompt("explain", quick=True, user_templates_dir=user_templates_dir)
    assert BUILTIN_TEMPLATES["explain"] in result
    assert QUICK_SUFFIX in result


def test_unknown_template_raises_template_error(user_templates_dir):
    with pytest.raises(TemplateError, match="not found"):
        resolve_system_prompt("nonexistent", quick=False, user_templates_dir=user_templates_dir)


def test_user_yaml_template_loaded(user_templates_dir):
    user_templates_dir.mkdir(parents=True)
    template_file = user_templates_dir / "mytmpl.yaml"
    template_file.write_text("name: mytmpl\ndescription: test\nprompt: Custom prompt here.\n")

    result = resolve_system_prompt("mytmpl", quick=False, user_templates_dir=user_templates_dir)
    assert result == "Custom prompt here."


def test_user_yaml_missing_prompt_raises(user_templates_dir):
    user_templates_dir.mkdir(parents=True)
    template_file = user_templates_dir / "bad.yaml"
    template_file.write_text("name: bad\ndescription: no prompt field\n")

    with pytest.raises(TemplateError, match="prompt"):
        resolve_system_prompt("bad", quick=False, user_templates_dir=user_templates_dir)


def test_user_yaml_invalid_yaml_raises(user_templates_dir):
    user_templates_dir.mkdir(parents=True)
    template_file = user_templates_dir / "broken.yaml"
    template_file.write_text("{\nnot: valid: yaml: at: all\n")

    with pytest.raises(TemplateError):
        resolve_system_prompt("broken", quick=False, user_templates_dir=user_templates_dir)


# --- default_system_prompt composition tests ---


def test_default_system_prompt_alone(user_templates_dir):
    result = resolve_system_prompt(None, False, user_templates_dir, "Be concise.")
    assert result == "Be concise."


def test_no_args_with_empty_default_returns_none(user_templates_dir):
    result = resolve_system_prompt(None, False, user_templates_dir, "")
    assert result is None


def test_default_plus_template_composes(user_templates_dir):
    result = resolve_system_prompt("explain", False, user_templates_dir, "Linux user.")
    assert result is not None
    assert result.startswith("Linux user.")
    assert BUILTIN_TEMPLATES["explain"] in result


def test_default_plus_quick_composes(user_templates_dir):
    result = resolve_system_prompt(None, True, user_templates_dir, "Linux user.")
    assert result is not None
    assert "Linux user." in result
    assert QUICK_SUFFIX in result


def test_all_three_compose(user_templates_dir):
    result = resolve_system_prompt("fix", True, user_templates_dir, "Linux user.")
    assert result is not None
    assert "Linux user." in result
    assert BUILTIN_TEMPLATES["fix"] in result
    assert QUICK_SUFFIX in result


def test_parts_joined_with_blank_line(user_templates_dir):
    result = resolve_system_prompt(None, True, user_templates_dir, "Context.")
    assert result == f"Context.\n\n{QUICK_SUFFIX}"


# --- domain mode tests ---


def test_domain_sap_resolves(user_templates_dir):
    result = resolve_system_prompt("sap", quick=False, user_templates_dir=user_templates_dir)
    assert result is not None
    assert "SAP" in result


def test_domain_docker_resolves(user_templates_dir):
    result = resolve_system_prompt("docker", quick=False, user_templates_dir=user_templates_dir)
    assert result is not None
    assert "Docker" in result


def test_domain_composes_with_quick(user_templates_dir):
    result = resolve_system_prompt("docker", quick=True, user_templates_dir=user_templates_dir)
    assert result is not None
    assert BUILTIN_TEMPLATES["docker"] in result
    assert QUICK_SUFFIX in result
