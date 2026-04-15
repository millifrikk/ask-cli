# Release Checklist

A reproducible task list to run before shipping a release. Scoped by
release type so you don't over-invest on a patch or under-invest on a
feature bump.

| Type | Scope | Rough time |
|---|---|---|
| **Patch** (x.y.**Z**) | Bug fixes, no new surface | ~15 min |
| **Feature** (x.**Y**.0) | New flags, new files, new I/O, new dependencies | ~45 min |
| **Major / public / annual** | Everything below + full audits | 2–4 hours |

---

## 1. Pre-flight

Applies to every release.

- [ ] Working tree clean: `git status --short` shows only the changes you intend to ship
- [ ] On `main` and up-to-date with `origin`: `git fetch && git status`
- [ ] Tests green: `pytest -q`
- [ ] Lint clean: `ruff check src/ tests/ && ruff format --check src/ tests/`

## 2. Scope review

Applies to every release. Patches can keep this very short.

- [ ] List everything shipping: `git log v<PREV>..HEAD --oneline`
- [ ] Note the categories: feature / fix / refactor / docs / security
- [ ] For anything non-trivial, re-read the diff: `git diff v<PREV>..HEAD -- src/`

## 3. Targeted security review

**Skip for pure-docs patches. Required for feature releases.** Scope is
the diff since the last tag — not the whole codebase.

- [ ] New `subprocess.run` / `os.system` / `eval` / `exec` calls? Trace user input through each one. If user input reaches a shell, verify the `is_destructive()` gate applies or add one.
- [ ] New CLI arguments that become file paths, URLs, or shell tokens? Check for path traversal (`..`), URL validation, shell metacharacter handling.
- [ ] New API endpoints / providers / `base_url` fields? Verify the scheme check in `_validate_base_url` still covers them.
- [ ] New `write_text` / `open(..., "w")` / `open(..., "a")` calls? Verify `chmod 0o600` after write if the file can contain user-visible prompts, responses, commands, credentials, or logs.
- [ ] New `mkdir` calls? If the directory holds sensitive data, use `_ensure_private_dir()` (chmod 0o700).
- [ ] New error messages / log output? Verify no API keys, file contents, or user-identifying strings get interpolated.
- [ ] New dependencies in `pyproject.toml`? Add an upper bound (`<N+1`) and note the addition in the CHANGELOG.

## 4. Tool-based scans

Applies to feature releases. Patches can skip Semgrep unless they touched
`src/ask_cli/core/commands.py` or `agent.py`.

- [ ] **Secret sweep on new commits** (should be instant):
  ```bash
  git log v<PREV>..HEAD -p | grep -oE \
    'sk-[A-Za-z0-9]{40,}|ghp_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|glpat-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{20,}'
  ```
  Expected output: empty. Any hit = investigate before tagging.

- [ ] **Semgrep** (core rulesets, fast):
  ```bash
  semgrep scan \
    --config p/python --config p/security-audit --config p/command-injection \
    --exclude '.venv' --exclude '__pycache__' --exclude '.ruff_cache' --exclude '.pytest_cache' \
    --metrics=off --quiet .
  ```
  Expected: 2 known `shell=True` findings in `commands.py`. Any third finding = triage.

- [ ] Triage new findings: **fix now**, **document in SECURITY.md**, or **accept with a one-line rationale in the commit message** (rare).

## 5. Docs & metadata

Applies to every release.

- [ ] Version bumped in `src/ask_cli/__init__.py` only (pyproject.toml reads it dynamically)
- [ ] `CHANGELOG.md`: new `[X.Y.Z]` section with Added/Changed/Fixed/Security subsections, plus updated link refs at the bottom
- [ ] `README.md` version badge bumped: `[version-X.Y.Z-informational]`
- [ ] `SECURITY.md` updated if new trade-offs, known limitations, or reportable incidents
- [ ] `docs/STATUS.md` refreshed if deployed-env state, outstanding work, or architectural decisions changed
- [ ] For feature releases: skim `CLAUDE.md` for anything that's drifted (new flags → "What NOT to Do", new file layout → "File & Directory Layout")

## 6. Build & install verification

Applies to every release.

- [ ] Full test suite still green after doc/version changes: `pytest -q`
- [ ] Editable install picks up the new version: `pip install -e . && ask --version` matches `__version__`
- [ ] Smoke test the common path: `ask "say hi in one line"`, `ask --quick "list open ports"`, `ask --smart "explain the CAP theorem"` as appropriate
- [ ] File perms haven't regressed: `ls -la ~/.config/ask/ ~/.local/share/ask/` (expect `drwx------` on dirs, `-rw-------` on files)

## 7. Ship

```bash
git add -A   # or specific files
git commit -m "<conventional-commit-msg with v<X.Y.Z> in title>"
git tag v<X.Y.Z>
git push origin main --tags
gh release create v<X.Y.Z> --generate-notes
gh release view v<X.Y.Z>   # sanity check the generated notes
```

## 8. Post-ship follow-through

- [ ] Pull on every deployed machine: `cd ~/projects/ask-cli && git pull --tags && ~/.venvs/ask-cli/bin/pip install -e . && ask --version`
- [ ] Run one `ask` invocation on each machine if the release touched file I/O (`_migrate_permissions` runs on `load_config`)
- [ ] Update `docs/STATUS.md` "Deployed environments" rows if any machine will linger on an older version > 1 day

---

## When to run the full audit (not per release)

Reserve these for **first public release**, **major version bumps**,
**security-impacting refactors**, or **annual cadence**. They take hours
and produce gitignored artifacts (`*AUDIT*.md`, `SEMGREP-SCAN.md`).

- `/pre-release-audit` skill (three-track: security / quality / OSS readiness)
- Full file I/O enumeration — trace every `read_text` / `write_text` / `open` / `mkdir` in the codebase
- Full git history secrets sweep — pickaxe across all refs, not just the release diff
- Semgrep with all 10 rulesets (`p/python`, `p/security-audit`, `p/owasp-top-ten`, `p/command-injection`, `p/secrets`, `p/insecure-transport`, `p/jwt`, `p/sql-injection`, `p/xss`, `p/cwe-top-25`)
- Data-flow trace for any command-execution, clipboard, or external-process path

The v2.3.x cycle's artifacts are the last reference point for what those
outputs look like when things are clean.
