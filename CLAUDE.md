# Ask CLI - Project Guidelines

This file is read by Claude Code at the start of every session.
All coding standards and decisions documented here must be followed without exception.
When in doubt, ask before deviating.

---

## Project Overview

`ask-cli` is a terminal AI assistant built as a proper Python package.
- PRD: `docs/ask-cli-prd-merged.md` — the authoritative source for features and design decisions
- Design decisions log: see memory files (linked from PRD discussions)
- Installs as `ask` command via `pip install -e .`, replacing `~/bin/ask`

---

## Architecture Rules (non-negotiable)

### Separation of concerns
- `cli.py` — argument parsing only. No business logic. Never imported by other modules.
- `providers/` — one file per provider. All conform to `BaseProvider` abstract class.
- `core/` — business logic. Never calls `sys.exit()`, `print()`, or reads config.
- `config.py` — config read once at startup, passed as an object. No global state.
- `output.py` — single `rich.Console` instance. All user-facing output goes through here.

### Provider pattern
Every provider must implement `BaseProvider`. New providers are drop-in additions.
Never add provider-specific logic outside `providers/`.

### Error handling
- Never swallow exceptions silently.
- Never use bare `except:` — always catch specific exception types.
- Business logic raises typed exceptions (`AskCLIError`, `ProviderError`, `ConfigError`).
- CLI layer catches typed exceptions and renders them via `rich` with actionable messages.
- API errors are caught at the provider layer and re-raised as `ProviderError`.

---

## Code Style

### Tooling
- **Formatter:** `ruff format` — run before every commit
- **Linter:** `ruff check` — zero warnings policy
- **No other linters** — ruff replaces flake8, isort, pyupgrade

### Python
- **Minimum version:** Python 3.11+
- **Strings:** f-strings always. No `.format()`, no `%` formatting.
- **Line length:** 100 characters
- **Imports:** stdlib → third-party → local, blank line between groups (ruff enforces this)

### Type hints
- **Pragmatic** — annotate all function signatures and class attributes
- Skip obvious locals (`x = []`, `count = 0`, etc.)
- No `mypy --strict` — but signatures must be annotated
- Use `X | Y` union syntax (Python 3.10+), not `Optional[X]` or `Union[X, Y]`

### Docstrings
- **None** — code must be self-documenting through good naming
- Add inline comments only where logic is non-obvious
- Exception: module-level docstrings (one line) are required

### Naming
- `snake_case` for files, functions, variables
- `PascalCase` for classes
- `UPPER_SNAKE_CASE` for constants
- No abbreviations: `conversation_history` not `conv_hist`, `provider_config` not `prov_cfg`
- One primary class per module where practical

---

## Output & UX

- **All output** goes through `rich.Console` — never raw `print()`
- **Streaming** is always on — use `rich.live` with Anthropic streaming API
- **Colors/formatting** disabled automatically when stdout is not a TTY (piped output)
- **`--no-color`** flag disables rich formatting
- Error messages follow the pattern in PRD §10: problem + cause + actionable suggestion

---

## Testing

### Framework: pytest

### What to test
- **Core modules** (providers, config, conversation): meaningful coverage required
- **CLI glue code** (`cli.py`, output formatting): lighter coverage acceptable — these fail loudly
- All **API calls must be mocked** — tests never make real HTTP requests
- Test **error paths**, not just happy paths

### Standards
- Test file mirrors source: `src/ask_cli/providers/zai.py` → `tests/providers/test_zai.py`
- Shared fixtures in `conftest.py`, never duplicated
- Coverage target: 80% on core modules (soft target, reviewed per phase — no hard CI gate)
- Test names describe behaviour: `test_provider_raises_on_missing_api_key`, not `test_provider_1`

---

## Git & Commits

### Conventional commits — required format:
```
feat: add --quick flag for terse responses
fix: handle missing config file gracefully
refactor: extract provider base class
test: add coverage for conversation history expiry
docs: update command reference in PRD
chore: add ruff to pyproject.toml
```

### Rules
- One logical change per commit
- Never commit: secrets, API keys, `.env` files, `__pycache__/`, `*.pyc`
- Config file (`~/.config/ask/config.json`) never committed — contains API keys
- Review `git diff` before committing — no accidental debug prints or temp code

---

## Versioning & Releases

### Single source of truth
The package version lives in **one place**: `src/ask_cli/__init__.py`.
```python
__version__ = "2.1.0"
```
`pyproject.toml` reads it dynamically via hatch — never hardcode the version there.

### SemVer rules
- **Patch** (`2.1.0 → 2.1.1`) — bug fixes, no user-visible behavior change
- **Minor** (`2.1.0 → 2.2.0`) — new features, backward compatible
- **Major** (`2.1.0 → 3.0.0`) — breaking changes (removed flags, incompatible config)

### Release workflow (every release)

Follow the full [Release Checklist](docs/RELEASE-CHECKLIST.md) — scoped
by release type (patch / feature / major). Short version:

```bash
# 1. Pre-flight: tests + lint green, working tree clean
pytest -q && ruff check src/ tests/

# 2. Bump version
vim src/ask_cli/__init__.py        # edit __version__

# 3. Update CHANGELOG.md and the README version badge

# 4. Commit + tag
git add -A
git commit -m "chore: bump version to v2.1.1"
git tag v2.1.1
git push origin main --tags

# 5. GitHub release page
gh release create v2.1.1 --generate-notes
```

### CLI exposure
`ask --version` reads `__version__` directly — always matches the package. No drift between `--version` output and installed metadata.

### Rules
- Never bump version without tagging — untagged bumps leave no release record
- Never tag without bumping — tags must map 1:1 with `__version__` values
- Never reuse a tag — once `v2.1.0` is pushed, the next release is `v2.1.1` or higher
- The `main` branch always reflects a released or in-progress version — feature branches for anything non-trivial

---

## File & Directory Layout

```
ask-cli/
├── CLAUDE.md                  # This file
├── pyproject.toml             # Package definition, deps, ruff config
├── README.md
├── src/
│   └── ask_cli/
│       ├── __init__.py
│       ├── cli.py             # Argument parsing only
│       ├── config.py          # Config loading, XDG paths
│       ├── output.py          # rich Console instance, rendering helpers
│       ├── exceptions.py      # Typed exception hierarchy
│       ├── core/
│       │   ├── conversation.py
│       │   ├── templates.py
│       │   └── history.py
│       └── providers/
│           ├── base.py        # BaseProvider abstract class
│           ├── zai.py
│           ├── anthropic.py
│           ├── openai.py
│           ├── google.py
│           └── ollama.py
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_cli.py
│   ├── core/
│   │   └── test_conversation.py
│   └── providers/
│       ├── test_zai.py
│       └── test_base.py
└── docs/
    └── ask-cli-prd-merged.md
```

---

## Key Technical Decisions (summary)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Config location | XDG (`~/.config/ask/`, `~/.local/share/ask/`) | Linux standard, distributable |
| Default max_tokens | 4096 | 1024 was too restrictive |
| `--quick` max_tokens | 256 | Terse one-liner answers |
| Streaming | Always on, no flag | Foundational UX |
| UI library | `rich` only | Replaces pygments + prompt_toolkit |
| Interactive mode | Deferred v3.0 | `-c` flag covers terminal use cases better |
| RAG | Deferred, optional extra | Too heavy for core install |
| Voice input | Removed | Conflicts with terminal-first philosophy |
| Type hints | Pragmatic | Signatures annotated, obvious locals skipped |
| Docstrings | None | Self-documenting code + inline comments only |
| Coverage | Soft 80% on core | Meaningful tests over hitting numbers |

Full decisions log: `.claude/memory/decisions.md`

---

## Workflow: Plan Before Code

**Always enter plan mode before writing any code.** No exceptions, regardless of how small the task seems.

### Process
1. **Enter plan mode** — explore the codebase, understand the scope, design the approach
2. **Write the plan** — Claude Code saves plans to `~/.claude/plans/` with a generated filename
3. **Get approval** — present the plan and wait for explicit user sign-off
4. **(Optional, local only)** — symlink the plan into `docs/plans/<descriptive-name>.md` for easier navigation during the session. These symlinks are **gitignored** because they point outside the repo and don't resolve on other clones.
5. **Then code** — only start implementation after the plan is approved

### Why plans aren't in git
Plans are working notes tied to a specific conversation. They capture state that's often stale a week later (known gaps, provisional decisions, file paths that may have moved). They're valuable locally while the work is live; they're noise in the repo's permanent history. Decisions worth preserving go into `CLAUDE.md` (architecture), `CHANGELOG.md` (what shipped), or `docs/STATUS.md` (current state).

---

## What NOT to Do

- Do not add features beyond the current phase without discussion
- Do not use `print()` anywhere — always `console.print()` via output module
- Do not read config more than once (at startup)
- Do not add dependencies without updating `pyproject.toml` and discussing the addition
- Do not hardcode API keys, base URLs, or model names outside config/provider files
- Do not catch exceptions in business logic just to re-raise the same exception
- Do not write tests that only assert `is not None` — test actual behaviour
