# ask-cli

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-2.5.0-informational)](https://github.com/millifrikk/ask-cli/releases)
[![Providers](https://img.shields.io/badge/providers-Anthropic%20%7C%20GLM%20%7C%20Gemini%20%7C%20Ollama-orange)](#configuration)

A terminal AI assistant that lives where you work. Multi-provider, streaming, context-aware — designed for the command line first.

> If this saves you time, a ⭐ on GitHub goes a long way — it helps others find the project.

---

<!-- DEMO: replace this block with your asciinema GIF once recorded -->
<!-- Recommended: record with `asciinema rec`, convert with `agg`, embed as: -->
<!-- ![ask-cli demo](https://raw.githubusercontent.com/millifrikk/ask-cli/main/docs/demo.gif) -->
> 📽 **Demo GIF coming soon** — `ask "how do I find files over 100MB in /var/log"` streaming live in your terminal.

---

## Contents

- [Quick start](#quick-start)
- [Why ask-cli exists](#why-ask-cli-exists)
- [Cost in practice](#cost-in-practice)
- [Features](#features)
- [Installation — Linux / WSL](#installation--linux--wsl)
- [Configuration](#configuration)
- [Usage](#usage)
- [Upgrading](#upgrading)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [License](#license)
- [Credits](#credits)

---

## Quick start

```bash
# Install (Ubuntu / WSL)
sudo apt install -y python3-full python3-venv git xclip
git clone https://github.com/millifrikk/ask-cli.git ~/projects/ask-cli
python3 -m venv ~/.venvs/ask-cli
~/.venvs/ask-cli/bin/pip install -e ~/projects/ask-cli
sudo ln -sf ~/.venvs/ask-cli/bin/ask /usr/local/bin/ask

# Set your API key (pick any provider)
export ASK_ZAI_API_KEY="your-key"          # Z.ai — most cost-effective
export ASK_ANTHROPIC_API_KEY="sk-ant-..."  # Anthropic Claude
export ASK_GOOGLE_API_KEY="..."            # Google Gemini
# No key needed for local Ollama

# Ask away
ask "how do I find files over 100MB in /var/log"
ask --smart "explain the CAP theorem"
ask --cmd "restart nginx"                  # generates + copies command to clipboard
ask -c "and how about for the last 7 days" # continue the conversation
```

---

## Why ask-cli exists

The terminal AI tool space is full of excellent session-based assistants — `claude`, `gemini`, `codex`, and others are purpose-built for agentic coding workflows, long-running conversations, and tool-calling loops. They load you into a dedicated environment and drive the experience from there. That's the right design for those use cases.

ask-cli was built for a different moment: you're mid-command in your shell, you want a one-line answer or a generated command, and you want the response to appear in the same terminal you're already in — not in a new app, not in a wrapped UI, not in a session you have to exit. `ask "..."` streams the answer into stdout and returns you to your prompt. It's a plain pipe between you and a model, nothing in between.

That framing shaped every design decision:

- **Multi-provider** — Anthropic, OpenAI, Google, Z.ai, Ollama — pick the cheapest model that answers the question well
- **Always streaming** — responses feel immediate, not a 5-second stall then a wall of text
- **Click-friendly output** — code blocks render without padded backgrounds so triple-click copies exactly the code
- **`--cmd` and `--execute`** — generate a command with no prose, copy it, optionally run it (with safety checks on destructive patterns)
- **Short flags for short needs** — `--quick` for terse answers, `--smart` to escalate to the better model, `-c` to continue the last conversation

If you live in the shell and want an AI assistant that stays out of your way, this is for you. If you want an agent that drives a multi-file refactor, use one of the dedicated tools — they're better at that.

---

## Cost in practice

ask-cli interactions are typically one-shot questions or a short back-and-forth — not long agentic sessions that burn through tokens. A day of normal terminal use is rarely more than a handful of small exchanges, so paid-API costs stay negligible, and several providers' free tiers can comfortably cover that volume.

If you'd rather avoid paid APIs entirely, Ollama supports local models and a free cloud tier, both without a paid key. Switching between providers is a single config change (`ask --set-default-provider <name>`), so you can start on whichever free tier works for you and move only if your usage outgrows it.

---

## Features

| Capability | Details |
|---|---|
| **Multi-provider** | Anthropic, Z.ai, OpenAI, Google Gemini, Ollama (local + cloud) — single command, pick the one that fits |
| **Always streaming** | Responses render live via `rich.live`, not a wall of text after a 5-second pause |
| **Model tiers** | `--fast` / default / `--smart` per provider; `--quick` for terse one-liners |
| **Reasoning model support** | `--quick` auto-disables thinking tokens on Qwen3.5 / DeepSeek-R1 so the budget isn't eaten by hidden chain-of-thought |
| **Shell command generation** | `--cmd` generates a single command and auto-copies to clipboard; `--execute` runs safe commands automatically and asks you to type `yes` for destructive ones |
| **Conversation history** | `-c` continues the previous session; 1-hour TTL; `--clear` resets |
| **File attachments** | `-f path` or `-F glob` to attach files/globs as context |
| **Domain modes & templates** | `--docker`, `--git`, `--sql`, `--k8s`, `--aws`, `--security`, `--perf`, `--sap`; combine with `--explain` / `--fix` / `--optimize` or your own `--template NAME` |
| **Output modes** | `--markdown` (default), `--raw`, `--code-only`, `--json`, `--no-color`; piped output is written verbatim, errors go to stderr |
| **Click-friendly rendering** | Code blocks render without padded background, so triple-click selects exactly the code |
| **Clipboard integration** | `--copy` full response, `--copy-code` first code block |
| **Agent mode** | `--agent` runs a multi-step plan-and-execute loop (you approve the plan; `--dry-run` shows it without running anything) |
| **Save/recall** | `--save NAME` / `--recall NAME` to persist answers by name |
| **Usage stats** | `--stats` to see cumulative query counts and approximate token usage |

---

## Installation — Linux / WSL

### Prerequisites

```bash
sudo apt update
sudo apt install -y python3-full python3-venv git xclip
```

> `python3-full` is important on Ubuntu 24.04+ (Noble) — without it, `python3 -m venv` may silently produce a broken virtual environment.

### Clone and install

```bash
# Authenticate if the repo is private
gh auth login && gh auth setup-git

# Clone
git clone https://github.com/millifrikk/ask-cli.git ~/projects/ask-cli
cd ~/projects/ask-cli

# Create venv and install (without activating — cleaner and failure-visible)
python3 -m venv ~/.venvs/ask-cli
~/.venvs/ask-cli/bin/pip install -e .

# Put `ask` on PATH
mkdir -p ~/.local/bin
ln -sf ~/.venvs/ask-cli/bin/ask ~/.local/bin/ask

# Optional: also symlink into /usr/local/bin so non-interactive shells (cron, scripts) find it
sudo ln -sf ~/.venvs/ask-cli/bin/ask /usr/local/bin/ask
```

### Verify

```bash
ask --version      # should print: ask 2.2.4 (or newer)
ask "say hello"
```

If `ask` isn't found, ensure `~/.local/bin` is on your PATH:

```bash
grep -q '$HOME/.local/bin' ~/.bashrc || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### One-liner install

```bash
sudo apt update && sudo apt install -y python3-full python3-venv git xclip && \
git clone https://github.com/millifrikk/ask-cli.git ~/projects/ask-cli && \
python3 -m venv ~/.venvs/ask-cli && \
~/.venvs/ask-cli/bin/pip install -e ~/projects/ask-cli && \
mkdir -p ~/.local/bin && ln -sf ~/.venvs/ask-cli/bin/ask ~/.local/bin/ask && \
sudo ln -sf ~/.venvs/ask-cli/bin/ask /usr/local/bin/ask && \
ask --version
```

### WSL clipboard (optional)

On WSL, for `--copy` / `--copy-code` to reach the Windows clipboard, install `wslu` inside WSL:

```bash
sudo apt install -y wslu
```

`pyperclip` auto-detects WSL and routes through `clip.exe`.

---

## Configuration

### API keys — where to put them

Two places are supported; env vars override the config file when both are set.

**Recommended:** put keys in `~/.bashrc`. Keeps secrets out of files and lets you rotate per-shell.

```bash
cat >> ~/.bashrc << 'EOF'
export ASK_ANTHROPIC_API_KEY="sk-ant-..."
export ASK_ZAI_API_KEY="..."
export ASK_OPENAI_API_KEY="..."
export ASK_GOOGLE_API_KEY="..."
EOF
source ~/.bashrc
```

**Alternatively** (e.g. for cron jobs or other non-interactive shells that don't source `~/.bashrc`), set `api_key` per provider in `~/.config/ask/config.json` (chmod 600 is applied automatically).

Ollama (local or cloud) needs no key.

### Config file

On first run, ask-cli creates `~/.config/ask/config.json` (chmod 600) with sensible defaults. You can edit it to change providers, models, or defaults. Keys in the config file are only used if the corresponding env var is absent.

Common fields:

```json
{
  "default_provider": "anthropic",
  "providers": {
    "anthropic": {
      "default_model": "claude-haiku-4-5-20251001",
      "fast_model":    "claude-haiku-4-5-20251001",
      "smart_model":   "claude-opus-4-6"
    }
  },
  "defaults": {
    "max_tokens": 4096,
    "quick_max_tokens": 1024,
    "history_ttl_hours": 1
  }
}
```

### Change the default provider at any time

```bash
ask --set-default-provider anthropic
ask --list-providers           # see what's configured
ask --list-models              # see tiers for the current provider
ask -p zai --list-models       # or for another provider
```

---

## Usage

### Everyday

```bash
ask "what's the difference between rsync's -a and --archive"
ask --quick "list open TCP ports"          # terse, 1024-token cap
ask --smart "explain the CAP theorem"      # opus 4.6 on Anthropic
ask -c "and give me an example"            # continue the last conversation
ask --clear                                # reset conversation history
```

### With files

```bash
ask -f ~/project/main.py "spot the bug"
ask -F "src/**/*.py" "summarize this module's architecture"
echo "error log content..." | ask "what's going wrong"
```

### Shell commands

```bash
ask --cmd "restart nginx"                  # generates + auto-copies to clipboard
ask --cmd --dry-run "backup /etc to tarball"   # show command, don't run
ask --execute "list processes using port 80"   # run it (destructive commands ask for 'yes')
```

### Domain modes

```bash
ask --docker "minimal Alpine nginx Dockerfile"
ask --k8s   "pod stuck in CrashLoopBackOff — what do I check"
ask --git   "how do I split a commit into two"
ask --sql   "window function for running total"
```

### Templates

```bash
ask --explain "tar -xzvf archive.tar.gz"
ask --fix "why doesn't this regex work: ^[a-z]+.txt$"
ask --optimize "SELECT * FROM orders WHERE status='x' ORDER BY created DESC"
ask --docker --fix "container exits with code 137"   # a domain and a task combine
```

Your own templates live in `~/.local/share/ask/templates/NAME.yaml` (or under
`$XDG_DATA_HOME`) and need a `prompt:` field:

```yaml
prompt: You are a meticulous code reviewer. Point out bugs before style.
```

```bash
ask --template reviewer -f app.py "review this"
```

### Output modes

```bash
ask --code-only "write a python palindrome checker"   # only code blocks
ask --raw "summarize this paragraph"                  # no markdown rendering
ask --json "user info for user_id=42 as JSON" | jq .  # asks the model for JSON only
ask --no-color "..."                                  # strip ANSI for logs
ask "write a bash backup script" > backup.sh          # piped/redirected output is verbatim
```

Output modes are mutually exclusive, as are `--fast`/`--smart`/`-m` and the
domain flags: contradictory combinations are rejected rather than guessed.

### Save and recall

```bash
ask --save nginx-cmd --cmd "restart nginx"
ask --recall nginx-cmd
ask --list-saved
ask --delete-saved nginx-cmd
```

### Agent mode

```bash
ask --agent "find and archive log files older than 30 days in /var/log"
ask --agent --dry-run "..."                # show the plan, run nothing
ask --agent --auto-approve "..."           # skip per-step confirmation on safe steps (plan still needs approval)
ask --agent --agent-max-steps 20 "..."     # let it take more steps
```

### Version & help

```bash
ask --version
ask --help
```

---

## Upgrading

```bash
cd ~/projects/ask-cli
git pull
~/.venvs/ask-cli/bin/pip install -e . --upgrade
ask --version
```

---

## Development

### Setup

```bash
cd ~/projects/ask-cli
source ~/.venvs/ask-cli/bin/activate
pip install -e .[dev]
```

### Run tests

```bash
pytest -q
pytest --cov=src/ask_cli --cov-report=term-missing
```

Coverage target: 75%+ on core modules. 157 tests as of v2.2.4.

### Lint & format

```bash
ruff format src/ tests/
ruff check src/ tests/
```

Zero-warning policy. Run before every commit.

### Project structure

```
ask-cli/
├── src/ask_cli/
│   ├── cli.py              # argparse + main entry point (no business logic)
│   ├── config.py           # config loading, XDG paths, dataclasses
│   ├── output.py           # single rich.Console, AskMarkdown, render helpers
│   ├── exceptions.py       # typed exception hierarchy
│   ├── core/
│   │   ├── conversation.py # run_query() orchestrator
│   │   ├── history.py      # conversation history with TTL
│   │   ├── templates.py    # built-in + user templates
│   │   ├── files.py        # attachment globbing
│   │   ├── saved.py        # --save / --recall
│   │   ├── commands.py     # --cmd extraction + safety checks
│   │   ├── agent.py        # multi-step agent loop
│   │   └── stats.py        # --stats tracking
│   └── providers/
│       ├── base.py         # BaseProvider ABC
│       ├── anthropic.py    # native Anthropic
│       ├── zai.py          # Anthropic SDK, Z.ai base_url
│       ├── openai.py       # OpenAI SDK
│       ├── google.py       # google-genai
│       └── ollama.py       # OpenAI-compat, local or cloud
└── tests/
```

### Versioning & releases

Single source of truth: `src/ask_cli/__init__.py`. `pyproject.toml` reads it dynamically via hatch.

Release workflow:

```bash
vim src/ask_cli/__init__.py      # bump __version__
git add -A
git commit -m "chore: bump version to vX.Y.Z"
git tag vX.Y.Z
git push origin main --tags
gh release create vX.Y.Z --generate-notes    # optional
```

See `CLAUDE.md` for the full development contract.

### Commit convention

Conventional commits:

```
feat:   new feature
fix:    bug fix
refactor: refactoring without behavior change
test:   tests only
docs:   documentation only
chore:  tooling, version bumps
```

One logical change per commit. Never commit secrets, API keys, or the user config file.

---

## Troubleshooting

### `ask: command not found` after install

`~/.local/bin` isn't on your PATH. Check `echo $PATH | tr ':' '\n' | grep local`. If missing:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Ollama cloud: `403 — subscription required`

Free tier is rate-limited. Either wait it out, subscribe at https://ollama.com/upgrade, or use a different provider:

```bash
ask -p anthropic "..."
```

### Provider "not configured" error

API key is missing. Check with `ask --list-providers` and set the appropriate env var (`ASK_<PROVIDER>_API_KEY`).

### Config JSON parse error

You probably edited `~/.config/ask/config.json` and broke the syntax. Either fix the JSON, or reset:

```bash
mv ~/.config/ask/config.json ~/.config/ask/config.json.bak
ask "hello"    # recreates defaults
```

---

## License

[MIT](LICENSE) — use it, fork it, ship it. Attribution appreciated but not required.

---

## Credits

Built with [Anthropic Claude](https://www.anthropic.com/), [rich](https://github.com/Textualize/rich), and help from Claude Code. Provider flexibility made practical by [Z.ai](https://z.ai)'s Anthropic-compatible API.

---

*Found a bug or have an idea? [Open an issue](https://github.com/millifrikk/ask-cli/issues) — contributions welcome.*
