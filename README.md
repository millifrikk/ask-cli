# ask-cli

A terminal AI assistant that lives where you work. Multi-provider, streaming, context-aware — designed for the command line first.

```bash
ask "how do I find files over 100MB in /var/log"
ask --smart "why is quicksort O(n log n) average"
ask --cmd "restart nginx"          # generates + copies the command
ask -c "and how about for the last 7 days"   # continue the conversation
```

## Why ask-cli exists

The terminal AI tool space is full of excellent session-based assistants — `claude`, `gemini`, `codex`, and others are purpose-built for agentic coding workflows, long-running conversations, and tool-calling loops. They load you into a dedicated environment and drive the experience from there. That's the right design for those use cases.

ask-cli was built for a different moment: you're mid-command in your shell, you want a one-line answer or a generated command, and you want the response to appear in the same terminal you're already in — not in a new app, not in a wrapped UI, not in a session you have to exit. `ask "..."` streams the answer into stdout and returns you to your prompt. It's a plain pipe between you and a model, nothing in between.

That framing shaped every design decision:

- **Multi-provider** — Anthropic, OpenAI, Google, Z.ai, Ollama — pick the cheapest model that answers the question well
- **Always streaming** — responses feel immediate, not a 5-second stall then a wall of text
- **Click-friendly output** — code blocks render without padded backgrounds so triple-click copies exactly the code
- **Context-aware prompts** — the system prompt adapts when invoked from Windows-via-WSL vs. a native Linux shell
- **`--cmd` and `--execute`** — generate a command with no prose, copy it, optionally run it (with safety checks on destructive patterns)
- **Short flags for short needs** — `--quick` for terse answers, `--smart` to escalate to the better model, `-c` to continue the last conversation

If you live in the shell and want an AI assistant that stays out of your way, this is for you. If you want an agent that drives a multi-file refactor, use one of the dedicated tools — they're better at that.

---

## Features

| Capability | Details |
|---|---|
| **Multi-provider** | Anthropic, Z.ai, OpenAI, Google Gemini, Ollama (local + cloud) — single command, pick the one that fits |
| **Always streaming** | Responses render live via `rich.live`, not a wall of text after a 5-second pause |
| **Model tiers** | `--fast` / default / `--smart` per provider; `--quick` for terse one-liners |
| **Context-aware prompts** | Different system prompt when invoked from Windows via WSL vs. a Linux terminal |
| **Reasoning model support** | `--quick` auto-disables thinking tokens on Qwen3.5 / DeepSeek-R1 so the budget isn't eaten by hidden chain-of-thought |
| **Shell command generation** | `--cmd` generates a single command and auto-copies to clipboard; `--execute` runs it with safety checks against destructive patterns |
| **Conversation history** | `-c` continues the previous session; 1-hour TTL; `--clear` resets |
| **File attachments** | `-f path` or `-F glob` to attach files/globs as context |
| **Domain modes** | `--docker`, `--git`, `--sql`, `--k8s`, `--aws`, `--security`, `--perf`, `--sap` |
| **Output modes** | `--markdown`, `--raw`, `--code-only`, `--json`, `--no-color` |
| **Click-friendly rendering** | Code blocks render without padded background, so triple-click selects exactly the code |
| **Clipboard integration** | `--copy` full response, `--copy-code` first code block |
| **Agent mode** | `--agent` runs a multi-step plan-and-execute loop (with approval gates) |
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

# Also symlink into /usr/local/bin so non-interactive shells (like wsl ask from Windows) find it
sudo ln -sf ~/.venvs/ask-cli/bin/ask /usr/local/bin/ask
```

### Verify

```bash
ask --version      # should print: ask 2.2.0 (or newer)
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

---

## Configuration

### API keys — use environment variables, not the config file

Put keys in `~/.bashrc` (Linux) or equivalent. Environment variables **override** anything in the config file, and they keep secrets out of files.

```bash
cat >> ~/.bashrc << 'EOF'
export ASK_ANTHROPIC_API_KEY="sk-ant-..."
export ASK_ZAI_API_KEY="..."
export ASK_OPENAI_API_KEY="..."
export ASK_GOOGLE_API_KEY="..."
EOF
source ~/.bashrc
```

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

## Windows integration (via WSL)

ask-cli runs inside WSL. You call it from Windows PowerShell or cmd. When invoked from Windows, ask-cli switches to a **general-purpose assistant prompt** (not the Linux-command-focused one).

The integration has two setup paths depending on your Windows environment.

### Path A — Personal / unmanaged Windows (easy)

Add a PowerShell function to your profile — works in any new PowerShell window.

```powershell
# Open your PowerShell profile (creates the file if needed)
notepad $PROFILE
```

Paste this and save:

```powershell
function ask {
    $env:WSLENV = "ASK_CONTEXT/u:$env:WSLENV"
    $env:ASK_CONTEXT = "windows"
    wsl ask @args
}
```

Then in a new PowerShell window:

```powershell
ask "what OS are you assuming I'm on?"
```

> If you get `File ... cannot be loaded` / execution policy errors, your machine is locked down — use Path B.

### Path B — Corporate-managed Windows (PowerShell profile blocked)

Group Policy on corporate machines often blocks PowerShell profile scripts. Bypass it by setting persistent user-scope environment variables — this writes to `HKCU\Environment` without any script execution.

In PowerShell:

```powershell
[Environment]::SetEnvironmentVariable("ASK_CONTEXT", "windows", "User")
[Environment]::SetEnvironmentVariable("WSLENV", "ASK_CONTEXT/u", "User")
```

**Close all Windows Terminal windows** (not just tabs — the whole app) so new ones inherit the updated environment. Then:

```powershell
wsl ask "what OS am I on?"
```

You'll type `wsl ask "..."` instead of `ask "..."` (four extra characters) — small price to pay on a locked-down machine.

### WSL clipboard (optional, both paths)

For `--copy` / `--copy-code` from Windows to work against the Windows clipboard, install `wslu` inside WSL:

```bash
sudo apt install -y wslu
```

`pyperclip` auto-detects WSL and routes through `clip.exe`.

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
ask --cmd --execute "list processes using port 80"   # run after confirmation
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
```

### Output modes

```bash
ask --code-only "write a python palindrome checker"   # only code blocks
ask --raw "summarize this paragraph"                  # no markdown rendering
ask --json "return user info as JSON for user_id=42"  # raw, for piping
ask --no-color "..."                                  # strip ANSI for logs
```

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
ask --agent --auto-approve "..."           # skip confirmation on safe steps
ask --agent --agent-max-steps 20 "..."     # let it take more steps
```

### Version & help

```bash
ask --version
ask --help
```

---

## Contexts — Linux vs Windows prompts

The system prompt adapts to where you're calling from.

| Entry point | `ASK_CONTEXT` value | System prompt behavior |
|---|---|---|
| WSL terminal / native Linux | (unset) or anything else | Linux/Ubuntu focused, shell-command-friendly, GNU coreutils assumptions, destructive-command guardrails |
| Windows PowerShell / cmd (via `wsl ask` or wrapper) | `windows` | General assistant, no OS assumptions, answers across topics — technical, conceptual, writing, analysis |

You can override at any time by setting `ASK_CONTEXT` manually:

```bash
ASK_CONTEXT=windows ask "anything"    # force Windows prompt
```

Custom prompts live in `~/.config/ask/config.json` under `defaults.system_prompt` and `defaults.system_prompt_windows`.

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

Coverage target: 75%+ on core modules. 154 tests as of v2.2.0.

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

### `ask: command not found` from `wsl ask` (Windows side)

Non-interactive WSL shells don't source `~/.bashrc`. Symlink into a system path:

```bash
sudo ln -sf ~/.venvs/ask-cli/bin/ask /usr/local/bin/ask
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

### PowerShell profile blocked (corporate machine)

Group Policy prevents loading `$PROFILE`. Use the User-scope env var approach in the [Windows integration — Path B](#path-b--corporate-managed-windows-powershell-profile-blocked) section.

---

## License

[MIT](LICENSE) — use it, fork it, ship it. Attribution appreciated but not required.

---

## Credits

Built with [Anthropic Claude](https://www.anthropic.com/), [rich](https://github.com/Textualize/rich), and help from Claude Code.
