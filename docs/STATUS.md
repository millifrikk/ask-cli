# ask-cli — Project Status

Living document. Update when we make meaningful changes so the next session can pick up without excavating chat history.

**Last updated:** 2026-04-15 · **Version:** v2.2.1

---

## Current version

**v2.2.1** — Windows/WSL context-aware system prompt; Windows-first answers on corporate workstation.

```bash
ask --version  # ask 2.2.1
```

Release history: v2.0.0 → v2.1.0 → v2.2.0 → v2.2.1. Tags pushed to GitHub.

---

## Deployed environments

### Dev laptop (Linux, `emil@ubuntu-dev`)

| Setting | Value |
|---|---|
| Provider | Anthropic |
| Default model | `claude-haiku-4-5-20251001` |
| `--smart` model | `claude-opus-4-6` |
| `--fast` model | `claude-haiku-4-5-20251001` (same as default — `--fast` is a no-op) |
| `--quick` max tokens | 1024 |
| API key location | `~/.bashrc` env var (`ASK_ANTHROPIC_API_KEY`) |
| Secondary providers | Z.ai (configured), Ollama (glm-5.1:cloud and qwen3.5:397b-cloud — rate-limited on free tier) |
| Context | Linux (default) |

### Work laptop (Windows via WSL, `fridriks@WKS0001100062`, Boehringer Ingelheim corporate)

| Setting | Value |
|---|---|
| Provider | Google Gemini |
| Default model | `gemini-3-flash-preview` |
| API key location | **⚠️ `~/.config/ask/config.json`** (should move to `ASK_GOOGLE_API_KEY` env var) |
| Context | Depends on entry point — Linux from WSL terminal, Windows from PowerShell |
| Windows integration | Path B (corporate-locked): User-scope env vars `ASK_CONTEXT=windows` + `WSLENV=ASK_CONTEXT/u`; PowerShell profile scripts blocked by Group Policy |
| Invocation from Windows | `wsl ask "..."` (not a wrapped `ask`, since AppLocker blocks user-path `.bat` files) |
| WSL-side symlink | Also at `/usr/local/bin/ask` (so non-interactive bash spawned by `wsl.exe` finds it) |

---

## Features shipped this release cycle (v2.1.0 — v2.2.1)

### v2.1.0
- Ollama reasoning-model support (`think: bool | None` kwarg threaded through provider stream)
- `--quick` now passes `think=False` so reasoning models don't exhaust the budget on hidden chain-of-thought
- `quick_max_tokens` raised from 256 → 1024 (absorbs preamble/thinking leakage)
- System prompt rewrite: tighter OS rule, response-discipline rules, shell safety guardrails, no hardcoded version
- `AskMarkdown` + `PlainCodeBlock` for click-friendly code rendering (triple-click selects exactly the code)
- `--cmd` auto-enables `--copy-code`
- Version wiring: single source of truth in `__init__.py`, `pyproject.toml` reads it dynamically
- `--version` flag
- `CLAUDE.md`: documented versioning & release workflow

### v2.2.0
- `system_prompt_windows` config field
- `_select_base_system_prompt(defaults)` — selects prompt based on `ASK_CONTEXT` env var
- PowerShell wrapper pattern documented

### v2.2.1
- Windows prompt rewrite: now **Windows-first** (default to Windows/PowerShell answers, only mention macOS/Linux when explicitly asked)
- Added Windows-specific destructive-command guardrail

### Docs
- `README.md` — 472-line comprehensive install + usage + troubleshooting reference

---

## Outstanding work

### Housekeeping (no urgency)
- [ ] Clean up duplicate `export PATH` lines in WSL `~/.bashrc` (166 PATH duplicates, cosmetic only)
- [ ] Move Google API key from `~/.config/ask/config.json` to `ASK_GOOGLE_API_KEY` env var in `~/.bashrc` on WSL laptop
- [ ] Untracked parked docs in `docs/` not yet committed:
  - `docs/feature-copy-code-from-terminal.md` (research, parked)
  - `docs/nifty-gliding-liskov.md` (stale plan duplicate)
  - `docs/plans/*.md` (symlinks to `/home/emil/.claude/plans/`)

### Process improvements we discussed but didn't wire up
- [ ] Auto-detect non-interactive WSL shells spawned from Windows, for more robust context detection (alternative to ASK_CONTEXT env var propagation)
- [ ] Fallback chain when primary provider returns 401/403/429 (e.g. Anthropic → Z.ai → error)

---

## Open questions / parked decisions

### Ollama free-tier reliability
- Both `glm-5.1:cloud` and `qwen3.5:397b-cloud` hit 403 rate-limits on the free tier
- Decision: use Anthropic for daily work, Ollama as experimental/backup only
- Alternative: subscribe at https://ollama.com/upgrade (not needed yet)

### Windows-native port
- Discussed three options: (A) WSL-only, (B) cross-platform fork, (C) native distribution
- **Current direction: Option A (WSL-only)** — v2.2.0 context-switching handles the Windows-from-PowerShell use case without a port
- Revisit if Windows-native users ask, or if WSL integration becomes limiting

### Corporate install pattern
- Learned: AppLocker on corporate Windows blocks `.bat` files in user directories
- Solution deployed: User-scope env vars + `wsl ask "..."` invocation (Path B in README)
- Not blocked: registry writes to `HKCU\Environment`, user-scope PATH updates, WSL invocation itself

### Local model viability on old laptops
- Tested with Gemma 4 research, CodeQwen, Qwen3.5 variants
- Conclusion: 7B+ models don't fit 8GB RAM / no-GPU laptops; anything below is unreliable for command help
- Decision: cloud-first, with Ollama cloud as the only "local feel" option

---

## Key architectural decisions

### System prompt composition
Prompt resolves in layers (templates.py:resolve_system_prompt):
1. Base prompt — picked at startup by `_select_base_system_prompt(defaults)` based on `ASK_CONTEXT` env var
2. Template prompt — if `--explain`, `--fix`, `--docker`, etc. is used
3. `QUICK_SUFFIX` — if `--quick` is used

All active layers are joined with `\n\n`. Each layer can be empty; composition handles that.

### Context detection
- `ASK_CONTEXT=windows` → Windows prompt
- Anything else (including unset) → Linux prompt
- Configured via `WSLENV=ASK_CONTEXT/u` on Windows side so it propagates into WSL

### Version as single source of truth
- `src/ask_cli/__init__.py::__version__` — the only place to edit
- `pyproject.toml` uses `dynamic = ["version"]` via `[tool.hatch.version]`
- CLI `--version` imports `__version__` directly from the package

### Secrets policy
- Env vars (`~/.bashrc`) are the canonical location
- Config file (`~/.config/ask/config.json`) is supported but discouraged
- Env vars override config file values in `load_config._apply_env_overrides`

---

## Incidents & learnings this session

| Incident | Learning |
|---|---|
| Anthropic API key leaked twice when pasted into config JSON with wrong quoting | Never paste secrets during a session; always give the user self-serve instructions with placeholders |
| GitHub PAT leaked in `git remote -v` output | Never embed credentials in remote URLs — use `gh auth login` which stores credentials in `gh`'s secure store |
| Fresh WSL install produced a broken venv (empty) | `python3 -m venv` needs `python3-full` on Ubuntu 24.04+ Noble; silent partial failures cascade into PEP 668 errors downstream |
| `wsl ask` failed with "command not found" despite symlink in `~/.local/bin` | Non-interactive bash invoked by `wsl.exe` doesn't source `~/.bashrc`; symlink also to `/usr/local/bin/` (system path always on PATH) |
| PowerShell `$PROFILE` blocked on corporate Windows | Group Policy can block script execution entirely; fall back to User-scope env vars + explicit `wsl ask` invocation |
| Windows Terminal overrides `WSLENV` with `WT_SESSION:WT_PROFILE_ID:` | Close ALL WT windows (not just tabs) after setting User-scope env vars so new sessions pick up registry values |
| v2.2.0 Windows prompt produced OS-agnostic multi-answer dumps | A neutral prompt isn't the same as a Windows-first prompt; explicit OS defaults matter |

---

## How to resume work

1. **Read this file first** — catches you up on current state.
2. **Check `git log --oneline -10`** — see what's been committed recently.
3. **Check `ask --version`** — confirm which version is installed locally.
4. **For Windows-side changes**, test from both WSL terminal (`ask`) and PowerShell (`wsl ask`) to verify context-switching is intact.
5. **Before shipping any release**, see `CLAUDE.md` → "Versioning & Releases" for the bump/tag/push workflow.
