# Changelog

All notable changes to ask-cli are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning
follows [SemVer](https://semver.org/).

## [Unreleased]

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

[Unreleased]: https://github.com/millifrikk/ask-cli/compare/v2.3.1...HEAD
[2.3.1]: https://github.com/millifrikk/ask-cli/compare/v2.3.0...v2.3.1
[2.3.0]: https://github.com/millifrikk/ask-cli/compare/v2.2.4...v2.3.0
[2.2.4]: https://github.com/millifrikk/ask-cli/compare/v2.2.3...v2.2.4
[2.2.3]: https://github.com/millifrikk/ask-cli/compare/v2.2.2...v2.2.3
[2.2.2]: https://github.com/millifrikk/ask-cli/compare/v2.2.1...v2.2.2
[2.2.1]: https://github.com/millifrikk/ask-cli/compare/v2.2.0...v2.2.1
[2.2.0]: https://github.com/millifrikk/ask-cli/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/millifrikk/ask-cli/compare/v2.0.0...v2.1.0
