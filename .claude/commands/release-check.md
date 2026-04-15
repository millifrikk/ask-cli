---
description: Run the ask-cli pre-release checklist (patch / feature / major)
argument-hint: [patch|feature|major]
---

Execute the pre-release checklist documented in `docs/RELEASE-CHECKLIST.md`.

**Release type:** $ARGUMENTS

If `$ARGUMENTS` is empty, ambiguous, or not one of `patch` / `feature` / `major`, ask the user which type before proceeding. Don't assume.

## Execution scope by release type

- **patch** — run phases 1, 2, 5, 6, 7, 8. **Skip** phase 3 (targeted security review) and phase 4 (tool-based scans) unless the patch touched `src/ask_cli/core/commands.py`, `src/ask_cli/core/agent.py`, or any provider file. If it did, include phase 3 and 4.
- **feature** — run all 8 phases.
- **major** — run all 8 phases, then additionally invoke the `pre-release-audit` skill, run a full git-history secret sweep (not just the release diff), and run Semgrep with all 10 rulesets listed in the checklist.

## Execution rules

1. Read `docs/RELEASE-CHECKLIST.md` first so you're using the current version of the checklist, not your memory of it.
2. For each phase, run the commands the checklist specifies. Report the actual output, not a summary of what you intend to do.
3. At the end of every phase, state clearly whether it passed, failed, or produced items for user decision. Don't advance to the next phase silently on a failure — flag it and ask.
4. Phase 5 (docs & metadata) and Phase 7 (ship) involve commits/tags/pushes. **Do not execute Phase 7 without explicit user approval**, even if every prior phase passed. Summarize what would be committed and wait for go/no-go.
5. Phase 8 (post-ship) requires the user to operate on their other machines. List the commands; don't try to run them.
6. When the checklist says "triage new findings" (phase 4), surface each finding with file, line, rule, and a short recommendation. Don't auto-fix unless the user asks.

## Output format

Use phase-by-phase section headers. At the very end, produce a summary table: phase → status (✅ pass / ⚠ needs user decision / ❌ fail) → one-line note. This is the single artifact the user will read if they scrolled past the details.
