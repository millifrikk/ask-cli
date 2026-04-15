# Security Policy

## Reporting a vulnerability

Email security issues to **emil@millicentral.com**.

Please do **not** open a public GitHub issue for security bugs. A private
email gives us time to ship a fix before the details become public.

Include:

- What the issue is and why it matters
- Steps to reproduce
- The version of ask-cli you tested against (`ask --version`)
- Your preferred credit line for the release notes (or "anonymous")

You can expect an acknowledgement within a few days. For confirmed
vulnerabilities, we'll coordinate a fix and a release before publishing
details.

## Supported versions

Security fixes are applied to the latest released minor version. Older
versions are not back-patched — upgrade to receive fixes.

## Known limitations

The following are documented design tradeoffs, not vulnerabilities:

- **`--cmd --execute`** runs the LLM-generated command via a shell. The
  `is_destructive()` pattern list catches common footguns but is not
  exhaustive. Treat `--execute` like `curl | sh` — only use it when you
  trust the prompt and provider, and review the command before it runs
  when in doubt. `--dry-run` shows the command without running it.
- **`--agent`** runs a multi-step plan that executes commands in
  sequence with per-step confirmation (or `--auto-approve` to skip
  non-destructive prompts). The same caveats apply.
- **Attachments (`-f`, `-F`)** send file contents to the configured
  LLM provider over HTTPS. Don't attach files containing secrets unless
  you intend for the provider to see them.
- **API keys** are read from environment variables or `~/.config/ask/config.json`
  (chmod 600). Conversation history, saved responses, and command logs
  are written chmod 600 to `~/.local/share/ask/`.
