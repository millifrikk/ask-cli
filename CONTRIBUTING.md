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

Small, focused PRs get merged faster than large ones. If you're unsure whether something is worth building, open an issue first.

---

## Development reference

See the project structure and release workflow in the [Development section of the README](README.md#development).
The full development contract lives in `CLAUDE.md`.
