# ask-cli — Project Status

Living document. Update when we make meaningful changes so the next session can pick up without excavating chat history.

**Last updated:** 2026-04-15 · **Version:** v2.3.3

---

## Current version

**v2.3.3** — Fixed interactive WSL shell incorrectly getting Windows prompt when `ASK_CONTEXT` propagates via WSLENV.

```bash
ask --version  # ask 2.3.3
```

Release history:
`v2.0.0` → `v2.1.0` → `v2.2.0` → `v2.2.1` → `v2.2.2` → `v2.2.3` → `v2.2.4` →
`v2.3.0` → `v2.3.1` → `v2.3.2` → `v2.3.3`. All tags pushed; GitHub releases created for each.

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
| Secondary providers | Z.ai (configured), Ollama (glm-5.1:cloud, rate-limited on free tier) |
| Context | Linux (default) |
| File perms | Migrated to 0o600/0o700 on v2.3.2 first-run (verified) |

### Work laptop (Windows via WSL, `fridriks@WKS0001100062`, Boehringer Ingelheim corporate)

| Setting | Value |
|---|---|
| Provider | Google Gemini (default); Z.ai and Anthropic also configured |
| Default model | `gemini-3-flash-preview` |
| API keys | `~/.bashrc` env vars (`ASK_ZAI_API_KEY`, `ASK_ANTHROPIC_API_KEY`, `ASK_GOOGLE_API_KEY`). Migrated 2026-04-15 via `docs/one-off/migrate-api-keys-to-env.md`; `api_key` fields in config.json blanked. |
| `.bashrc` cleanup | Duplicate `export` lines deduped 2026-04-15 (kept last occurrence per name). |
| Installed version | **v2.3.0** (pending pull to v2.3.2 for the security hardening + permission migration) |
| Context | Depends on entry point — Linux from WSL terminal, Windows from PowerShell |
| Windows integration | Path B (corporate-locked): User-scope env vars `ASK_CONTEXT=windows` + `WSLENV=ASK_CONTEXT/u`; PowerShell profile scripts blocked by Group Policy |
| Invocation from Windows | `wsl ask "..."` (AppLocker blocks user-path `.bat` files) |
| WSL-side symlink | Also at `/usr/local/bin/ask` (non-interactive bash spawned by `wsl.exe` finds it) |

### Personal PC (Linux/WSL, `emil@millifrikk`)

| Setting | Value |
|---|---|
| Provider | OpenAI (after `v2.2.2` fix), Anthropic, Google Gemini, Z.ai, Ollama all configured |
| API keys | env vars in `~/.bashrc` |
| Installed version | v2.3.0 on last pull (pending upgrade to v2.3.2) |

---

## Features shipped this release cycle (v2.1.0 → v2.3.2)

### v2.1.0 — reasoning models + click-friendly rendering
- Ollama reasoning-model support: `think: bool | None` threaded through BaseProvider.stream
- `--quick` auto-sends `think=False` so reasoning budget doesn't get eaten by hidden chain-of-thought
- `quick_max_tokens` raised 256 → 1024
- `AskMarkdown` + `PlainCodeBlock` for triple-click-copyable code
- `--cmd` auto-enables `--copy-code`
- Single-source-of-truth version wiring via `hatch.version` dynamic
- `--version` flag

### v2.2.0 → v2.2.1 — Windows/WSL context awareness
- `system_prompt_windows` config field
- `_select_base_system_prompt()` reads `ASK_CONTEXT` env var at startup
- v2.2.1: Windows prompt rewritten as Windows-first (parallel to Linux-first behavior)

### v2.2.2 — OpenAI GPT-5 family
- `max_completion_tokens` for GPT-5 / o-series (they reject `max_tokens`)
- Legacy gpt-4, gpt-4o, gpt-3.5 keep using `max_tokens`

### v2.2.3 — response boundary marker
- Dim `── ask ──` rule rendered above every streamed response in TTY mode so the assistant's reply is visible after a long prompt

### v2.2.4 — license + README refresh
- Relicensed from proprietary to **MIT**
- README restructured with badges, TOC, quick-start, "Why ask-cli exists", affordability pitch
- Added `CONTRIBUTING.md`

### v2.3.0 — security hardening (from pre-release audit)
- `DESTRUCTIVE_PATTERNS` expanded 11 → 26 regexes (`chmod`, `sudo`, `curl | sh`, `find -delete`, `git reset --hard`, system-path redirects, fork bombs, etc.)
- History, saved responses, stats, command logs all written chmod 0o600
- Provider `base_url` warns if not `https://` or `http://localhost`
- Dependency upper bounds pinned (`anthropic<1`, `rich<16`, `pyyaml<7`, `openai<3`, `google-genai<2`, `pyperclip<2`)
- `SECURITY.md` added with vulnerability reporting process
- `CHANGELOG.md` added (Keep-a-Changelog format)

### v2.3.1 — close unsanitized paths
- `extract_command()` no longer falls back to "last non-empty line" (could turn prose into a shell command under `--execute`)
- Clipboard content stripped of trailing `\n` (pastejacking) and `\r` (preview-hiding) before `pyperclip.copy()`
- `--agent` command previews and outputs now run through `rich.markup.escape()` (prevents LLM-emitted markup from spoofing the approval preview)

### v2.3.2 — file I/O permission gaps
- XDG dirs (`~/.config/ask/`, `~/.local/share/ask/`, `saved/`) created with 0o700 — filename enumeration no longer possible on shared hosts
- `log_command()` re-chmods the log on every append (was only on first creation)
- `--set-default-provider` re-applies chmod 600 to `config.json`
- One-shot `_migrate_permissions()` pass on every `load_config()` — upgrades from earlier versions tighten automatically

### Docs
- `README.md` — 560 lines, Linux/WSL install + Windows Path A/B + troubleshooting
- `CONTRIBUTING.md` — bug report, feature request, PR setup, no-docstrings policy
- `SECURITY.md` — reporting process + documented design trade-offs
- `CHANGELOG.md` — full v2.0.0 → v2.3.2 history

---

## Security posture

Three formal audits run in v2.3.x cycle; all findings patched or documented:

| Audit | Date | Outcome |
|---|---|---|
| Pre-release audit (`pre-release-audit` skill) | 2026-04-15 | 1 High, 3 Medium, 3 Low findings → all addressed in v2.3.0 |
| File I/O audit | 2026-04-15 | 4 gaps (dir perms, log re-chmod, set-default-provider chmod, migration) → all addressed in v2.3.2 |
| Git history secrets sweep | 2026-04-15 | Clean — no real credentials in any commit |
| Semgrep scan (10 rulesets, 33 files) | 2026-04-15 | 2 findings, both `subprocess.run(shell=True)` in `--cmd --execute` / `--agent`. Expected by design, documented in `SECURITY.md`. |

Audit artifacts (`AUDIT-REPORT.md`, `FILE-IO-AUDIT.md`, `GIT-HISTORY-SECRETS-AUDIT.md`, `SEMGREP-SCAN.md`) are gitignored as dev-only.

---

## Outstanding work

### Pending user actions (not delegated to Claude)
- [ ] Pull v2.3.2 on work laptop (WSL corporate): `cd ~/projects/ask-cli && git pull --tags && ~/.venvs/ask-cli/bin/pip install -e . && ask --version`. One `ask` invocation afterward runs the permission migration.
- [ ] Pull v2.3.2 on personal PC (WSL): same command.
- [x] ~~Move Google API key on WSL laptop from `~/.config/ask/config.json` → `ASK_GOOGLE_API_KEY` in `~/.bashrc`.~~ Done 2026-04-15 — all three configured keys (zai, anthropic, google) migrated; config.json blanked.

### Housekeeping (no urgency)
- [x] ~~Clean up duplicate `export PATH` lines in WSL `~/.bashrc` (cosmetic)~~ Done 2026-04-15 via `/tmp/dedupe-command.txt` heredoc — all duplicate exports deduped.

### Process improvements we discussed but didn't wire up
- [x] ~~Auto-detect non-interactive WSL shells from Windows for more robust context detection~~ Shipped in v2.3.3 — `_invocation_is_interactive_wsl()` heuristic overrides `ASK_CONTEXT=windows` back to Linux when both (a) we're in WSL and (b) at least one of stdin/stdout is a TTY.
- [ ] Provider fallback chain on 401/403/429 (e.g. Anthropic → Z.ai → error)

---

## Open questions / parked decisions

### Ollama free-tier reliability
- `glm-5.1:cloud` and others hit 403 rate-limits on the free tier
- Decision: Anthropic for daily work, Ollama as experimental/backup
- Alternative: https://ollama.com/upgrade (not needed yet)

### Windows-native port
- Options: (A) WSL-only, (B) cross-platform fork, (C) native distribution
- **Current direction: Option A** — v2.2.0 context-switching handles it
- Revisit if Windows-native users ask, or WSL integration becomes limiting

### `--execute` safety model
- `is_destructive()` regex list is documented as a **best-effort allowlist, not a sandbox**
- Known bypasses (shell obfuscation, user-directory targets, non-`rm` deletion) enumerated in `SECURITY.md`
- Alternative: flip model so `--execute` always prompts unless explicit `--yes` passed. Not shipped — current model preserves the one-shot ergonomics for trusted queries. Revisit if users report incidents.

### Local model viability on old laptops
- Tested Gemma 4, CodeQwen, Qwen3.5 variants
- Conclusion: 7B+ doesn't fit 8GB no-GPU laptops; smaller models unreliable for command help
- Decision: cloud-first, Ollama cloud as the only "local feel"

---

## Key architectural decisions

### System prompt composition
Resolves in layers (`templates.py::resolve_system_prompt`):
1. Base prompt — picked at startup by `_select_base_system_prompt()` based on `ASK_CONTEXT`
2. Template prompt — if `--explain`, `--fix`, `--docker`, etc.
3. `QUICK_SUFFIX` — if `--quick`

Joined with `\n\n`. Each layer optional.

### Context detection
- `ASK_CONTEXT=windows` → Windows prompt
- Anything else (including unset) → Linux prompt
- `WSLENV=ASK_CONTEXT/u` on Windows propagates it into WSL

### Version as single source of truth
- `src/ask_cli/__init__.py::__version__`
- `pyproject.toml` uses `dynamic = ["version"]` via `[tool.hatch.version]`
- CLI `--version` reads `__version__` directly

### Secrets policy
- **Single-entry machines** (native Linux, WSL used only as a terminal): env vars in `~/.bashrc` are canonical; config file values are used only when the env var is absent.
- **Dual-entry machines** (WSL invoked from both WSL terminal and PowerShell via `wsl ask`): env vars alone **do not work** because non-interactive bash spawned by `wsl.exe` doesn't source `~/.bashrc`. API keys must live in `~/.config/ask/config.json`. Having them in both places is fine — env vars still win in interactive WSL.
- Config file is chmod 0o600; `_check_permissions` warns if loose
- Data dirs chmod 0o700; history/saved/stats/commands.log all chmod 0o600 (v2.3.2)

### Dev artifact policy
- Plans (`~/.claude/plans/*.md`) are local only; optional symlink into `docs/plans/` is gitignored
- Audit reports (`*AUDIT*.md`, `SEMGREP-SCAN.md`) are gitignored
- `CLAUDE.md` → `CHANGELOG.md` → `STATUS.md` are the durable decision trail

---

## Incidents & learnings this cycle

| Incident | Learning |
|---|---|
| Anthropic API key leaked twice in chat when pasted into malformed config JSON | Never paste secrets during a session; use self-serve instructions with `<YOUR-KEY>` placeholders |
| GitHub PAT leaked in `git remote -v` output | Never embed credentials in remote URLs — use `gh auth login` |
| Fresh WSL install produced a broken venv | `python3 -m venv` needs `python3-full` on Ubuntu 24.04+ |
| `wsl ask` failed with "command not found" despite `~/.local/bin` symlink | Non-interactive bash doesn't source `~/.bashrc`; also symlink to `/usr/local/bin/` |
| PowerShell `$PROFILE` blocked on corporate Windows | Group Policy can block script execution entirely; fall back to User-scope env vars + explicit `wsl ask` |
| Windows Terminal overrides `WSLENV` with session IDs | Close ALL WT windows (not just tabs) after setting User-scope env vars |
| v2.2.0 Windows prompt produced multi-OS answer dumps | Neutral ≠ Windows-first; explicit OS defaults matter |
| OpenAI GPT-5 family rejected `max_tokens` with 400 | They require `max_completion_tokens`; detect by model prefix |
| File I/O audit found `executed_commands.log` at 0o664 from pre-v2.3.0 era | `is_new` guard in `log_command()` let old perms persist; one-shot migration fixes this retroactively |
| Semgrep flagged 2 `shell=True` in `commands.py` | Expected — core of `--cmd --execute` feature; already `# noqa: S602` and documented in `SECURITY.md` |

---

## How to resume work

1. **Read this file first** — catches you up on current state.
2. **`git log --oneline -10`** — see what's been committed recently.
3. **`ask --version`** — confirm local installed version matches `main`.
4. **`ls -la ~/.local/share/ask/ ~/.config/ask/`** — confirm 0o700 dirs + 0o600 files (should be clean on v2.3.2).
5. **For Windows-side changes**, test from both WSL terminal (`ask`) and PowerShell (`wsl ask`) to verify context-switching is intact.
6. **Before shipping a release**, see `CLAUDE.md` → "Versioning & Releases" for bump/tag/push/`gh release` workflow.
