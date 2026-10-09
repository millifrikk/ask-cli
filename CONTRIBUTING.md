# Contributing to ask-cli

Thanks for taking the time. ask-cli is a solo project but contributions are welcome — bug reports, feature ideas, and pull requests all help.

---

## Reporting a bug

Open an issue and include:

- **OS and shell** — e.g. Ubuntu 24.04, WSL2 on Windows 11, bash 5.2
- **Python version** — `python3 --version`
- **ask-cli version** — `ask --version`
- **Provider and model** — e.g. `zai / glm-5.1`, `anthropic / claude-haiku-4-5`
- **The exact command you ran**
- **The full error output** — copy from the terminal, don't paraphrase it

If the bug is intermittent, note whether it's reproducible and under what conditions.

---

## Suggesting a feature

Open an issue and describe:

- **The use case** — what you're trying to do and why the current behaviour falls short
- **What you'd expect instead** — a concrete description of the desired outcome
- **Any providers or flags this would affect**

Feature requests framed around a real workflow get prioritised over abstract ones.

---

## Submitting a pull request

### Setup

```bash
git clone https://github.com/millifrikk/ask-cli.git
cd ask-cli
python3 -m venv ~/.venvs/ask-cli
~/.venvs/ask-cli/bin/pip install -e .[dev]
source ~/.venvs/ask-cli/bin/activate
```

### Before you push

```bash
# Format and lint — zero warnings required
ruff format src/ tests/
ruff check src/ tests/

# Run the test suite
pytest -q
```

Coverage target is 75%+ on core modules. If your change adds new behaviour, add a test for it.

### PR guidelines

- **One logical change per PR** — keep scope tight so review is fast
- **Conventional commit messages** — `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`
- **No secrets or API keys** — never commit `~/.config/ask/config.json` or any file containing credentials
- **Update the README** if your change affects user-facing behaviour or adds a new flag
- **Update the CHANGELOG** under the `[Unreleased]` section

Small, focused PRs get merged faster than large ones. If you're unsure whether something is worth building, open an issue first.

### Code style

ask-cli follows the conventions documented in `CLAUDE.md`. Worth knowing up front:

- **Docstrings only where they add value.** Prefer clear names; add a short docstring when it says something the name doesn't (a contract, a side effect, the why). Every module has a one-line docstring.
- **Tests first.** Write a failing test for the bug or behaviour, then make it pass. Tests must never touch your real environment — the fixtures in `tests/conftest.py` handle that; see `CLAUDE.md` → Testing.
- **No `print()`.** All user-facing output goes through `rich.Console` via helpers in `ask_cli/output.py`.
- **Typed signatures, pragmatic locals.** Annotate function signatures and class attributes; skip obvious locals (`count = 0`, `items = []`).
- **`X | Y` over `Optional[X]`** — Python 3.10+ union syntax, always.
- **100-character line length**, double quotes, ruff-formatted.
- **Security reports.** If you find a vulnerability, please follow `SECURITY.md` rather than filing a public issue.

---

## Development reference

See the project structure and release workflow in the [Development section of the README](README.md#development).
The full development contract lives in `CLAUDE.md`.
