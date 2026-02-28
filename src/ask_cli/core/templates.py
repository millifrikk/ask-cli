"""Built-in templates and system prompt resolution for ask-cli."""

from pathlib import Path

import yaml

from ask_cli.exceptions import TemplateError

QUICK_SUFFIX = (
    "Give the shortest possible answer. "
    "For commands, return only the command. "
    "No explanation unless absolutely critical."
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
    template: str | None,
    quick: bool,
    user_templates_dir: Path,
    default_system_prompt: str = "",
) -> str | None:
    """Resolve the system prompt from all active sources, joined with blank lines.

    Priority order (all compose, not override): default → template → quick suffix.
    Returns None if nothing is active.
    """
    parts: list[str] = []

    if default_system_prompt:
        parts.append(default_system_prompt)

    if template is not None:
        if template in BUILTIN_TEMPLATES:
            parts.append(BUILTIN_TEMPLATES[template])
        else:
            parts.append(_load_user_template(template, user_templates_dir))

    if quick:
        parts.append(QUICK_SUFFIX)

    return "\n\n".join(parts) if parts else None


def _load_user_template(name: str, templates_dir: Path) -> str:
    """Load a user-defined template from a YAML file."""
    template_path = templates_dir / f"{name}.yaml"
    if not template_path.exists():
        raise TemplateError(
            f"Template '{name}' not found. "
            f"Built-in templates: {', '.join(BUILTIN_TEMPLATES)}. "
            f"User templates should be placed in {templates_dir}/<name>.yaml"
        )

    try:
        data = yaml.safe_load(template_path.read_text())
    except yaml.YAMLError as e:
        raise TemplateError(f"Failed to parse template '{name}': {e}") from e
    except OSError as e:
        raise TemplateError(f"Failed to read template '{name}': {e}") from e

    if not isinstance(data, dict) or "prompt" not in data:
        raise TemplateError(
            f"Template '{name}' must be a YAML file with at least a 'prompt' field."
        )

    return str(data["prompt"])
