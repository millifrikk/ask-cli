# Ask CLI - Project Guidelines

This file is read by Claude Code at the start of every session. The architecture
rules below are firm; the rest describes how this project is worked on. If a rule
gets in the way of doing the right thing, say so rather than quietly working around it.

---

## Project Overview

`ask-cli` is a terminal AI assistant built as a proper Python package.
- PRD: `docs/ask-cli-prd-merged.md` — features and design intent
- Current state, deployed machines and open work: `docs/STATUS.md`
- What shipped when: `CHANGELOG.md`
- Installs as the `ask` command via `pip install -e .` (editable install in `~/.venvs/ask-cli`)

---

## Architecture Rules

### Separation of concerns
- `cli.py` — argument parsing, flag validation and dispatch only. Never imported by other modules.
- `output.py` — the only module that writes to the terminal or reads from it.
  - Answers go to stdout (`output.console`); errors, warnings, notices and prompts go to
    stderr (`output.err_console`), so `ask … | jq` and `ask … > file` get only the answer.
  - When stdout is not a terminal, responses are written verbatim (no Rich wrapping,
    padding or Markdown rendering).
  - Reference consoles as `output.console` at call time — `--no-color` rebinds them.
- `core/` — business logic. Never prints, prompts, calls `sys.exit()` or reads the config
  file. Where it needs the user (agent loop, `--cmd` confirmation) it takes a small UI
  protocol (`AgentUI`, `CommandUI`) that `output.ConsoleUI` implements.
- `config.py` — config read once at startup and passed down as `AppConfig`; XDG paths are
  resolved once into `AppPaths`. Problems that shouldn't stop a run are returned in
  `AppConfig.warnings`, not printed. No global state.
- `providers/` — one module per backend, all `BaseProvider` subclasses registered in
  `providers/__init__.py`. Z.ai and Ollama subclass the Anthropic and OpenAI providers.

### Provider pattern
Every provider implements `BaseProvider`, declares `provider_id` / `display_name`, and
records `last_stop_reason`. New providers are drop-in additions. Provider-specific logic
stays in `providers/`; SDK errors are translated in `providers/errors.py`.

### Error handling
- Business logic raises typed exceptions from `exceptions.py`, each with an optional
  `hint` set where the right advice is known (PRD §10: problem + cause + suggestion).
- `cli.main()` is the single error boundary: `AskCLIError` → message + hint, exit 1;
  Ctrl+C → exit 130; usage errors → exit 2. Nothing else catches-and-exits.
- Never swallow exceptions silently; never use bare `except:` or `except Exception`.
- API and transport errors (including connections dropped mid-stream) are re-raised as
  `ProviderError` at the provider layer.
- Local state files go through `core/storage.py` (atomic, owner-only writes).

---

## Code Style

### Tooling
- `ruff format` and `ruff check` — zero warnings. The lint selection enforces several
  rules in this file: no `print()` (T20), no blind except (BLE), annotated signatures
  (ANN), bandit security checks (S). Tests are exempt from ANN/ARG/S.
- CI (`.github/workflows/ci.yml`) runs ruff and pytest on Python 3.11–3.13.

### Python
- **Minimum version:** Python 3.11+
- **Strings:** f-strings. No `.format()` or `%`.
- **Line length:** 100
- **Types:** annotate every function signature and class attribute in `src/`; skip obvious
  locals. Use `X | Y`, not `Optional`/`Union`.

### Docstrings and comments
- One-line module docstring required.
- Short docstrings are welcome where they say something the name doesn't (contract,
  side effects, why). Don't restate the function name.
- Inline comments only for non-obvious reasoning.

### Naming
- `snake_case` files/functions/variables, `PascalCase` classes, `UPPER_SNAKE_CASE` constants.
- No abbreviations: `conversation_history`, not `conv_hist`.

---

## Testing

### Working loop (TDD)
For every fix or feature:
1. **Red:** write a test that reproduces the bug or specifies the behaviour; watch it fail
   for the right reason.
2. **Green:** smallest change that passes.
3. **Refactor**, then run the full gate: `pytest -q`, `ruff check src/ tests/`,
   `ruff format --check src/ tests/`.
4. One conventional commit per logical change.

### Isolation (non-negotiable)
Tests must never touch the real user environment. Autouse fixtures in `tests/conftest.py`
strip `ASK_*`/`WSL_*`/`XDG_*` env vars, point `HOME` and XDG dirs at `tmp_path`, stub the
clipboard and reset output state. Keep it that way:
- Never read real API keys, `~/.config/ask` or `~/.local/share/ask` from a test.
- All network calls are mocked. Provider tests use real SDK clients over
  `httpx.MockTransport` (helpers in `tests/providers/conftest.py`).
- CLI tests use the `run_cli` fixture, which calls `main(argv)` with the model, agent,
  history and shell stubbed and fails on unexpected confirmation prompts.

### Standards
- Test files mirror source: `src/ask_cli/core/agent.py` → `tests/core/test_agent.py`.
- Test error paths, not just happy paths. Names describe behaviour.
- Assert real behaviour — never just `is not None`.
- Coverage target: 80% on core modules and providers (soft target).

### Manual verification
Unit tests can't see terminal rendering. After user-visible changes, smoke-test the real
binary with `XDG_DATA_HOME` pointed at a scratch dir: piped output (`| cat -A`, `| jq`),
`--no-color` in a pty (`script -qec`), and the error paths you touched. Keep live API calls
few and cheap (the fast tier).

---

## Git, Releases & Versioning

### Commits
Conventional commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`), one
logical change each. Never commit secrets, `.env`, `__pycache__/`, or `config.json`
(it may hold API keys). Review `git diff` before committing.

### Branches and releases
- Non-trivial work goes on a branch (`fix/…`, `feat/…`, `refactor/…`) and is
  fast-forward merged to `main` when its release is ready.
- Run the `/release-check` skill (wraps `docs/RELEASE-CHECKLIST.md`) before each release.
- This is a personal project: the owner has authorised releasing autonomously —
  bump, tag, push and `gh release create` without stopping for review. Still stop for
  anything destructive (force-push, deleting tags/branches, rewriting history).

### Versioning
- `__version__` in `src/ask_cli/__init__.py` is the single source of truth (hatch reads it).
- SemVer: patch = fixes; minor = new features or behaviour changes users may notice
  (e.g. a flag combination now rejected); major = incompatible config or removed flags.
- Every bump gets a tag, a `CHANGELOG.md` entry, the README badge and `docs/STATUS.md`.
- Tags map 1:1 to versions and are never reused.

---

## File & Directory Layout

```
ask-cli/
├── CLAUDE.md · README.md · CHANGELOG.md · pyproject.toml
├── .github/workflows/ci.yml
├── src/ask_cli/
│   ├── __init__.py          # __version__
│   ├── cli.py               # parsing, flag validation, dispatch, error boundary
│   ├── config.py            # AppPaths, load_config, validation, set_default_provider
│   ├── output.py            # consoles, ResponseDisplay, ConsoleUI, confirm, renderers
│   ├── exceptions.py        # AskCLIError hierarchy (with hints)
│   ├── core/
│   │   ├── conversation.py  # run_query, completeness check
│   │   ├── history.py       # -c conversation history
│   │   ├── templates.py     # built-in + user templates, prompt composition
│   │   ├── commands.py      # --cmd flow, destructive patterns, command execution
│   │   ├── agent.py         # --agent loop (AgentUI protocol)
│   │   ├── files.py         # -f / -F attachments
│   │   ├── fences.py        # fenced code block parsing
│   │   ├── saved.py         # --save / --recall
│   │   ├── stats.py         # --stats
│   │   └── storage.py       # atomic owner-only JSON files
│   └── providers/
│       ├── __init__.py      # registry, get_provider
│       ├── base.py · errors.py
│       └── anthropic.py · zai.py · openai.py · ollama.py · google.py
├── tests/                   # mirrors src/; conftest.py holds shared fixtures
└── docs/                    # PRD, STATUS, RELEASE-CHECKLIST, one-off guides
```

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Config location | XDG (`~/.config/ask/`, `~/.local/share/ask/`) | Linux standard |
| Default max_tokens | 4096 | 1024 was too restrictive |
| `--quick` max_tokens | 1024 | Terse answers; reasoning models need headroom |
| Streaming | Always on | Foundational UX |
| Piped output | Verbatim text, diagnostics on stderr | `\| jq`, `> file` must just work |
| Conflicting flags | Usage error (exit 2) | Never silently guess which flag wins |
| State files | Atomic temp-file + rename, 0600 | No corruption, never world-readable |
| Commands | Run under bash; agent steps get no stdin and a timeout | Models write bash; nothing hangs |
| Agent | Plan always approved; destructive steps need "yes" | `--auto-approve` is not a blank cheque |
| Platform | Linux only (incl. WSL as a Linux shell) | Windows context switching removed in v2.5.0 — unused |
| UI library | `rich` only | |
| Interactive mode | Deferred | `-c` covers terminal use |
| Type hints | Signatures annotated, enforced by ruff | |
| Coverage | Soft 80% on core + providers | Meaningful tests over numbers |

---

## Workflow

- **Plan before code** for anything non-trivial (new features, refactors, multi-file
  changes): use plan mode, get the plan approved, then implement with the TDD loop.
  Small, obvious fixes can go straight to red → green.
- Plans live in `~/.claude/plans/` (optionally symlinked into the gitignored
  `docs/plans/`). They are working notes, not repo history: decisions worth keeping go
  into this file, `CHANGELOG.md` or `docs/STATUS.md`.

## What NOT to Do

- Don't add features beyond the current scope without discussing them.
- Don't write to the terminal outside `output.py`, and never use `print()`.
- Don't read the config more than once, or hardcode API keys, base URLs or model names
  outside config/provider files.
- Don't add dependencies without declaring them in `pyproject.toml` (with an upper bound)
  and mentioning them in the CHANGELOG. Import only what's declared.
- Don't catch exceptions just to re-raise the same exception, and don't swallow them.
- Don't write tests that touch the real environment or only assert `is not None`.
