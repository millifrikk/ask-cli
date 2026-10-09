# Changelog

All notable changes to ask-cli are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning
follows [SemVer](https://semver.org/).

## [Unreleased]

## [2.4.1] — 2026-10-09

### Fixed
- The `base_url` safety warning compared string prefixes, so
  `http://localhost.evil.com`, `http://localhost@evil.com` and
  `http://127.0.0.1.nip.io` counted as local. It now checks the parsed
  hostname, and no longer warns about plain `http://` to a LAN host when the
  provider has no API key to leak (e.g. Ollama on another machine).
- `output.code_theme` is now applied to all code blocks (it was ignored); an
  unknown theme is reported as a config error instead of crashing mid-render.
- WSL context detection treats clustered shell options (`bash -lc`,
  `zsh -ic`) as a command-string launcher, keeping the Windows prompt there.
- OpenAI requests always use `max_completion_tokens` (`max_tokens` is
  deprecated by OpenAI), so new model families no longer risk a 400.
- A non-shell code block before the command no longer hides it from `--cmd`.

### Changed
- Removed config options that never did anything: `offline_fallback`,
  `output.markdown`, `features.syntax_highlighting`. Existing config files
  that contain them still load.
- Usage stats label `cmd`, `quick` and `agent` runs (agent runs weren't
  recorded before).
- Internal: `cli.py` is back to parsing and dispatch (provider registry,
  context detection, `--cmd` flow and config editing moved to their own
  modules); Z.ai and Ollama now subclass the Anthropic and OpenAI providers;
  one fence parser; config and `core/` never print. `pygments` is declared as
  a direct dependency (already required by `rich`).

## [2.4.0] — 2026-10-09

### Added
- `--template NAME` uses your own template from
  `~/.local/share/ask/templates/NAME.yaml` (a `prompt:` field). User templates
  were documented before but unreachable.
- A domain flag and a task template now combine: `ask --docker --fix "…"`
  uses both prompts (previously only one was silently applied).

### Changed
- **Contradictory flags are rejected (exit 2) instead of silently resolved:**
  `-m`/`--fast`/`--smart`; `--markdown`/`--raw`/`--code-only`/`--json`;
  `--explain`/`--fix`/`--optimize`; more than one domain flag; more than one
  management action (`--stats`, `--clear`, `--recall`, …) or one with a
  question; `--auto-approve`/`--agent-max-steps` without `--agent`;
  `--agent` with `--save`/`-c`/`--copy`/`--copy-code`/`--cmd`/`--execute`;
  `--execute` with `--dry-run`. `-p`/`--set-default-provider` only accept
  known providers; `--max-file-size` and `--agent-max-steps` must be ≥ 1.
  **Scripts that relied on a silently ignored flag will now fail fast.**
- `--execute` implies `--cmd`. On its own it previously did nothing; it now
  runs non-destructive generated commands automatically, as its help text
  always said. Destructive ones still require typing `yes`.
- Agent mode: the plan always needs your approval (`--auto-approve` now only
  skips per-step confirmation of non-destructive commands, matching the PRD).
- Commands run under `/bin/bash` (falling back to `sh`) since the model is
  told to write bash; `/bin/sh` is dash on Debian/Ubuntu.

### Fixed
- `--agent --dry-run` executed every step; it now shows the plan and stops.
- The agent ignored the system prompt, templates, domain flags, `--quick` and
  the Windows context; they now apply to both the planning and execution
  steps.
- Agent steps can no longer hang on interactive commands (`git commit`,
  `npm init`, `tail -f`): stdin is `/dev/null` and each step times out after
  120 s. Non-UTF-8 output no longer crashes the agent, and long output is
  truncated before being sent back to the model.
- `--cmd` auto-copy respects `features.clipboard` and no longer copies twice
  with `--copy`.

### Security
- The destructive-command list (which gates `--execute` and
  `--auto-approve`) is matched after stripping quotes and backslashes, so
  `r\m` / `'rm'` no longer bypass it, and it now also covers `mv`, `shred`,
  `rsync --delete`, `tee`, file redirects (except `/dev/null`, `/tmp` scratch
  files and `2>&1`), `git checkout/restore/branch -D/stash drop/push`,
  `crontab -r`, `systemctl stop`, code piped or passed inline to interpreters
  (`| python3`, `python -c`, `bash -lc`, `node -e`), `eval`, `curl`/`wget`
  uploads, `docker rm`/`prune` and `kubectl delete`. It remains a best-effort
  list, not a sandbox. `ls 2>/dev/null` is no longer a false positive.

## [2.3.7] — 2026-10-09

### Fixed
- **No more tracebacks.** Every ask-cli error now goes through one handler
  that prints the problem plus an actionable hint and exits 1; Ctrl+C exits
  130 (the partial answer is still saved to history). Previously a corrupt
  `history.json` with `-c`, any provider error in `--agent` mode, a dropped
  connection mid-answer, piped stdin with `--cmd`, unreadable attachments and
  wrongly-shaped config files all crashed with a Python traceback.
- **Dropped connections and network failures** (mid-stream resets, timeouts,
  unreachable hosts) are reported per provider; Ollama no longer says "is it
  running?" when a request merely timed out. Gemini errors map to auth / rate
  limit / model-not-found instead of a catch-all.
- **Actionable messages.** A missing key names the exact env var and config
  key; an unknown model suggests `ask -p <provider> --list-models`; invalid
  config says which key is wrong and warns not to delete a file that holds
  API keys.
- **State files are written atomically** (temp file + rename, created 0600),
  so Ctrl+C or two concurrent runs can't corrupt history, stats, saved
  responses or the config. Corrupt files are reported with a fix
  (`ask --clear`, `ask --stats-reset`) instead of crashing; `--list-saved`
  shows unreadable entries instead of hiding them.
- **Errors are no longer swallowed.** Failing to write stats or the command
  log now warns (the answer is kept); `--stats-reset` no longer claims
  success on failure; an empty, filtered or token-limit-truncated response
  is reported instead of exiting silently.
- **Attachments:** permission errors and directories get clear messages; only
  `--max-file-size` bytes are read (a huge log isn't loaded into memory);
  files named twice are included once; blocks are labelled by path; content
  containing triple backticks gets a longer fence.
- **stdin:** only read from a pipe or file, fixing a hang when launched with
  a never-closing stdin (IDE tasks, some `wsl.exe` launchers); piped text is
  joined to the question with a blank line; no question → usage on stderr
  and exit 2.
- `--cmd` with piped stdin refuses to prompt instead of crashing; the agent's
  destructive-command prompt now requires the exact word `yes` (it accepted
  `y`); command failures after confirmation are reported.
- `--save` validates the name before calling the model and exits 1 if saving
  fails; `-c` says when it starts a new conversation because history expired.

### Changed
- `main()` is now `main(argv) -> int` (the `ask` entry point is unchanged).
- `httpx` is declared as a direct dependency (it was already installed
  transitively via the provider SDKs).

## [2.3.6] — 2026-10-09

### Fixed
- **Piped and redirected output is written verbatim.** When stdout is not a
  terminal, responses were rendered by Rich at 80 columns: long lines got hard
  newlines (breaking `ask --json … | jq` and `ask --code-only … > script.py`),
  lines were space-padded with no trailing newline, and `--markdown > file.md`
  wrote rendered text instead of Markdown. Now plain/markdown/raw output streams
  the model's text unchanged, `--code-only` writes only the code blocks, and
  `--recall` is verbatim too.
- **`--json` asks for JSON.** It previously behaved exactly like `--raw`. JSON
  mode now adds a JSON-only system instruction, strips a single surrounding
  code fence when piped, and warns on stderr if the response doesn't parse.
- **`--no-color` removes all colour.** The response kept its colours (the
  streaming code held a stale console), and errors printed literal
  `[bold red]` tags. Both are fixed.
- **Diagnostics go to stderr.** Errors, warnings, the "Saved response" and
  "copied to clipboard" notices no longer end up inside piped stdout.
- Error, warning and info messages escape Rich markup, so a path like
  `app/[slug]/page.tsx` keeps its brackets and a stray `[/red]` in a provider
  error no longer crashes the error renderer.
- `--list-models` stars only the default tier instead of every tier sharing
  the default model id.

### Changed
- Response rendering moved from `core/conversation.py` into
  `output.ResponseDisplay`; `run_query` now streams chunks to a callback.
  Fenced-code parsing lives in `core/fences.py` and handles tags like `c++`.

## [2.3.5] — 2026-10-09

### Security
- `load_config` no longer writes API keys from `ASK_*_API_KEY` env vars into
  the in-memory `DEFAULT_CONFIG`. A shallow-copying merge let env overrides
  mutate the defaults, so any later first-run config write in the same
  process persisted real keys to disk (observed via the test suite writing
  keys into pytest temp dirs). The merge now deep-copies.

### Changed
- XDG config/data paths are resolved at startup into an `AppPaths` object and
  passed down, instead of module-level constants frozen at import time.

### Fixed
- Test suite is now isolated from the host: an autouse fixture strips
  `ASK_*`/`WSL_*`/`XDG_*` env vars, redirects `HOME`/XDG dirs to a temp dir,
  and stubs the clipboard. Previously tests read real API keys (one test
  failed whenever `ASK_ZAI_API_KEY` was set), incremented the real
  `stats.json`, and overwrote the system clipboard.

## [2.3.4] — 2026-04-15

### Fixed
- `wsl ask "..."` from PowerShell now correctly uses the Windows prompt
  again. v2.3.3's WSL-interactive override relied on `isatty()`, but
  Windows Terminal + WSL2 + ConPTY proxies a TTY through to Linux, so
  both interactive WSL and wsl.exe-spawned processes see TTYs and the
  heuristic flipped both to Linux context. v2.3.4 adds a third signal:
  the parent process's cmdline. `wsl.exe` invokes `bash -c "<cmd>"` (or
  exec's from `/init`); an interactive WSL shell has a parent with no
  `-c` flag. All three signals (WSL marker + TTY + non-`-c` parent) must
  agree before overriding to Linux context. Interactive WSL still gets
  Linux, `wsl ask` from PowerShell stays Windows.

## [2.3.3] — 2026-04-15

### Fixed
- Interactive WSL shells no longer receive the Windows system prompt when
  `ASK_CONTEXT=windows` has been propagated via `WSLENV=ASK_CONTEXT/u`.
  Previously the User-scope env var leaked `ASK_CONTEXT=windows` into every
  WSL session — including terminals a user typed into directly — and
  ask-cli had no way to tell "called from PowerShell via `wsl.exe`" from
  "typed into a WSL terminal". A new `_invocation_is_interactive_wsl()`
  heuristic checks for a WSL marker (`WSL_DISTRO_NAME` / `WSL_INTEROP`)
  plus at least one of stdin/stdout being a TTY — if both are true, the
  Windows context is overridden back to Linux. `wsl.exe`-proxied
  invocations have no TTY anywhere and stay Windows-first as intended.
  Explicit `ASK_CONTEXT=linux` overrides always win.

## [2.3.2] — 2026-04-15

### Security
- `~/.config/ask/` and `~/.local/share/ask/` (including `saved/`) are now
  created with `0o700`, preventing other local users from enumerating
  filenames in the saved-responses directory. Previously only file
  *contents* were protected (0o600); listings were world-readable by
  default under typical umasks.
- `--set-default-provider` now re-applies `chmod 0o600` after rewriting
  `config.json`. Previously, a rewrite could leave the file with looser
  permissions if it had been copied in or tampered with.
- `log_command()` in the `--cmd --execute` and `--agent` flows now
  applies `chmod 0o600` on every append, not only on first creation.
  Previously, a pre-v2.3.0 `executed_commands.log` retained its
  original 0o644 permissions forever (observed in the wild on the dev
  host during audit).
- Added one-shot permission migration on every `load_config()` call.
  Pre-existing files and dirs with group/other bits set are tightened
  to 0o600 (files) or 0o700 (dirs) automatically. No user action
  required to adopt v2.3.2 security posture.

## [2.3.1] — 2026-04-15

### Security
- `extract_command()` no longer falls back to the last non-empty line of
  the response when no fenced block is present. Previously, if the model
  ignored the `--cmd` format directive, arbitrary prose could become a
  shell command under `--execute`. Now returns `None`, producing a clear
  "Could not extract a command" message instead.
- Clipboard content (`--copy` and `--copy-code`) is now stripped of
  trailing newlines (pastejacking: trailing `\n` auto-executes the
  command when pasted into a shell prompt) and carriage returns
  (which can hide content from pre-paste previews on some terminals).
- `--agent` command previews and command outputs are now escaped
  before being rendered through rich. An LLM that emits `[link=...]`
  or `[bold red]FAKE[/bold red]` inside a command or output string no
  longer has those tags rendered by rich — they display as literal
  text. Prevents UI spoofing during the agent preview.

### Docs
- `SECURITY.md` expanded with concrete examples of `is_destructive()`
  regex bypasses (shell obfuscation, user-directory targets, non-`rm`
  deletion), multi-line fence semantics, prompt-injection risk via
  attachments, clipboard hygiene, and API-key / user-data storage.

## [2.3.0] — 2026-04-15

### Security
- Expanded `DESTRUCTIVE_PATTERNS` in `--cmd --execute` safety check to
  cover `chmod`, `chown`, `chattr`, `sudo`, `doas`, `find -delete`,
  `find -exec`, `git reset --hard`, `git clean`, `git push --force`,
  piped shell installers (`curl | sh`, `wget | bash`, etc.), redirects
  to system paths (`/etc`, `/boot`, `/usr`, `/bin`, `/sbin`, `/dev`),
  `tee` to system paths, and fork bombs. Previously only caught 11
  specific binaries.
- History, saved responses, stats, and command logs are now written
  with `chmod 0o600` so other local users on shared hosts cannot read
  your prompts and responses.
- Provider `base_url` configuration now warns on first use if the URL
  is not `https://` or `http://localhost`. An attacker-controlled
  `base_url` would otherwise exfiltrate the API key on the next request.
- Added `SECURITY.md` with vulnerability reporting process and documented
  design tradeoffs around `--cmd --execute`, `--agent`, and attachments.

### Changed
- Pinned dependency upper bounds in `pyproject.toml` (`anthropic<1`,
  `rich<16`, `pyyaml<7`, `openai<3`, `google-genai<2`, `pyperclip<2`)
  so a breaking major-version release from a provider SDK cannot
  suddenly break installs.

### Docs
- Added `CHANGELOG.md` (this file).
- `.gitignore` now excludes `last_session.txt` (Claude Code resume pointer).

## [2.2.4] — 2026-04-15

### Changed
- Relicensed under MIT. Added `LICENSE` file with MIT text and declared
  `license = "MIT"` in `pyproject.toml`.
- Rewrote README `Why` section to position the project around one-shot,
  stay-in-your-shell usage without disparaging session-based tools like
  `claude` / `gemini` / `codex`.

### Docs
- Refreshed README with badges, quick-start, TOC, affordability pitch,
  and credits section.
- Added `CONTRIBUTING.md` with bug-report, feature-request, and PR
  guidelines.

## [2.2.3] — 2026-04-15

### Added
- Dim `ask` rule rendered above every streamed response (TTY only) so
  the assistant's response boundary is visible when scrolling back
  through long prompts.

## [2.2.2] — 2026-04-15

### Fixed
- OpenAI provider now uses `max_completion_tokens` for GPT-5 family and
  o-series reasoning models (which reject `max_tokens`). Legacy models
  (gpt-4, gpt-4o, gpt-3.5) continue using `max_tokens`.

## [2.2.1] — 2026-04-15

### Changed
- Windows context system prompt rewritten to be Windows-first (default
  to Windows/PowerShell answers instead of OS-agnostic multi-OS dumps).

## [2.2.0] — 2026-04-15

### Added
- Context-aware system prompts. `ASK_CONTEXT=windows` selects a Windows
  prompt; any other value or unset selects the Linux prompt. Configure
  via `WSLENV=ASK_CONTEXT/u` on the Windows side so the env var crosses
  into WSL.
- `system_prompt_windows` config field alongside `system_prompt`.

## [2.1.0] — 2026-04-15

### Added
- Ollama reasoning-model support via `think: bool | None` kwarg threaded
  through the provider stack. `--quick` passes `think=False` so
  reasoning models don't eat the token budget on hidden chain-of-thought.
- `--version` flag reading from `src/ask_cli/__init__.py` via
  `hatch.version` dynamic.
- Click-friendly code rendering: `PlainCodeBlock` removes rich's padded
  background so triple-click selects exactly the code.
- `--cmd` now auto-enables `--copy-code`.

### Changed
- `quick_max_tokens` default raised from 256 → 1024 so reasoning models
  don't silently return empty responses.
- System prompt rewritten with tighter OS rule, response discipline, and
  shell-safety guardrails.

## [2.0.0] — earlier

- Initial packaged release with multi-provider support (Anthropic, Z.ai,
  OpenAI, Google Gemini, Ollama), streaming, domain modes, conversation
  history, save/recall, agent mode, and XDG-compliant config.

[Unreleased]: https://github.com/millifrikk/ask-cli/compare/v2.4.1...HEAD
[2.4.1]: https://github.com/millifrikk/ask-cli/compare/v2.4.0...v2.4.1
[2.4.0]: https://github.com/millifrikk/ask-cli/compare/v2.3.7...v2.4.0
[2.3.7]: https://github.com/millifrikk/ask-cli/compare/v2.3.6...v2.3.7
[2.3.6]: https://github.com/millifrikk/ask-cli/compare/v2.3.5...v2.3.6
[2.3.5]: https://github.com/millifrikk/ask-cli/compare/v2.3.4...v2.3.5
[2.3.4]: https://github.com/millifrikk/ask-cli/compare/v2.3.3...v2.3.4
[2.3.3]: https://github.com/millifrikk/ask-cli/compare/v2.3.2...v2.3.3
[2.3.2]: https://github.com/millifrikk/ask-cli/compare/v2.3.1...v2.3.2
[2.3.1]: https://github.com/millifrikk/ask-cli/compare/v2.3.0...v2.3.1
[2.3.0]: https://github.com/millifrikk/ask-cli/compare/v2.2.4...v2.3.0
[2.2.4]: https://github.com/millifrikk/ask-cli/compare/v2.2.3...v2.2.4
[2.2.3]: https://github.com/millifrikk/ask-cli/compare/v2.2.2...v2.2.3
[2.2.2]: https://github.com/millifrikk/ask-cli/compare/v2.2.1...v2.2.2
[2.2.1]: https://github.com/millifrikk/ask-cli/compare/v2.2.0...v2.2.1
[2.2.0]: https://github.com/millifrikk/ask-cli/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/millifrikk/ask-cli/compare/v2.0.0...v2.1.0
