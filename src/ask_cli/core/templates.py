"""Built-in templates and system prompt resolution for ask-cli."""

import re
from collections.abc import Sequence
from pathlib import Path

import yaml

from ask_cli.exceptions import TemplateError

_TEMPLATE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")

QUICK_SUFFIX = (
    "Give the shortest possible answer. "
    "For commands, return only the command. "
    "No explanation unless absolutely critical."
)

JSON_SYSTEM_SUFFIX = (
    "Output mode: JSON. Respond with a single valid JSON document and nothing else — "
    "no prose, no explanation, and no Markdown code fence, even if earlier "
    "instructions ask you to fence code."
)

BUILTIN_TEMPLATES: dict[str, str] = {
    "explain": (
        "You are an expert technical explainer. "
        "Break down the concept or code clearly and concisely, "
        "using plain language. Include examples where helpful."
    ),
    "fix": (
        "You are an expert debugger. "
        "Identify the bug or problem, explain what's wrong, "
        "and provide a corrected version with a brief explanation of the fix."
    ),
    "optimize": (
        "You are a performance and code quality expert. "
        "Analyze the given code or system, identify inefficiencies, "
        "and provide an optimized version with a brief explanation of the changes."
    ),
    "sap": (
        "You are an expert SAP consultant specialising in SAP ECC, S/4HANA, and EWM. "
        "Reference transaction codes, ABAP concepts, and SAP-specific terminology. "
        "Provide concise, practical answers focused on SAP environments."
    ),
    "docker": (
        "You are a Docker and containerisation expert. "
        "Focus on Dockerfile best practices, docker-compose, container security, "
        "networking, and volume management. Provide production-ready solutions."
    ),
    "sql": (
        "You are a SQL and database expert. "
        "Focus on query optimisation, indexing, schema design, and database-specific syntax. "
        "Specify which RDBMS your answer targets when it matters."
    ),
    "git": (
        "You are a Git expert. "
        "Focus on version control workflows, branching strategies, "
        "rebasing, and conflict resolution. "
        "Show exact commands with flags, not just concepts."
    ),
    "k8s": (
        "You are a Kubernetes expert. "
        "Focus on pod lifecycle, deployments, services, RBAC, troubleshooting, and YAML manifests. "
        "Provide kubectl commands and manifest snippets where relevant."
    ),
    "aws": (
        "You are an AWS cloud expert. "
        "Focus on services, IAM, networking, cost optimisation, and CLI commands. "
        "Prefer AWS CLI examples over console instructions."
    ),
    "security": (
        "You are a security expert. "
        "Focus on threat analysis, CVEs, hardening, authentication, and secure coding practices. "
        "Flag risk levels clearly and provide actionable mitigations."
    ),
    "perf": (
        "You are a performance engineering expert. "
        "Focus on profiling, bottleneck identification, and optimisation for CPU, memory, I/O, "
        "and network. Prefer measurable recommendations over vague suggestions."
    ),
}


def resolve_system_prompt(
    templates: Sequence[str],
    quick: bool,
    user_templates_dir: Path,
    default_system_prompt: str = "",
) -> str | None:
    """Compose the system prompt: base → each template in order → quick suffix.

    Template names are built-ins or user YAML files in user_templates_dir.
    Returns None if nothing is active.
    """
    parts: list[str] = []

    if default_system_prompt:
        parts.append(default_system_prompt)

    for name in templates:
        if name in BUILTIN_TEMPLATES:
            parts.append(BUILTIN_TEMPLATES[name])
        else:
            parts.append(_load_user_template(name, user_templates_dir))

    if quick:
        parts.append(QUICK_SUFFIX)

    return "\n\n".join(parts) if parts else None


def _load_user_template(name: str, templates_dir: Path) -> str:
    """Load a user-defined template from templates_dir/<name>.yaml."""
    # The name becomes a file name: allow nothing that could leave templates_dir
    if not _TEMPLATE_NAME_RE.fullmatch(name):
        raise TemplateError(
            f"Invalid template name '{name}'.",
            hint="Use letters, digits, '-' and '_' only (the file is <name>.yaml).",
        )
    template_path = templates_dir / f"{name}.yaml"
    if not template_path.exists():
        raise TemplateError(
            f"Template '{name}' not found.",
            hint=f"Built-in templates: {', '.join(BUILTIN_TEMPLATES)}. "
            f"For your own, create {template_path} with a 'prompt:' field.",
        )

    try:
        data = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise TemplateError(f"Failed to parse template '{name}': {e}") from e
    except (OSError, UnicodeDecodeError) as e:
        raise TemplateError(f"Failed to read template '{name}': {e}") from e

    prompt = data.get("prompt") if isinstance(data, dict) else None
    if not isinstance(prompt, str) or not prompt.strip():
        raise TemplateError(
            f"Template '{name}' needs a non-empty text 'prompt' field.",
            hint=f"Edit {template_path}, e.g. prompt: You are a careful code reviewer.",
        )
    return prompt
