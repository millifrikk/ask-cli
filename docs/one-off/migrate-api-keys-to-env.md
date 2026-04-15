# One-off: move API keys from config.json → ~/.bashrc

Run these on the machine where the keys live in `~/.config/ask/config.json`.
Each step is self-contained. Open this file in a local editor
(`nano docs/one-off/migrate-api-keys-to-env.md` or your editor of
choice) and copy each fenced block individually — that avoids the
terminal-paste issues with multi-line content.

Every step is idempotent and safe to re-run.

---

## Step 1 — See which providers have keys set

```bash
python3 << 'PY'
import json, pathlib
d = json.loads(pathlib.Path.home().joinpath(".config/ask/config.json").read_text())
for p, c in d.get("providers", {}).items():
    print(f"  {p}: {'(set)' if c.get('api_key') else '(empty)'}")
PY
```

Expected: a list like `anthropic: (set)`, `google: (set)`, `openai: (empty)`, etc.

---

## Step 2 — Append export lines to ~/.bashrc

This generates `export ASK_<PROVIDER>_API_KEY=...` lines for every
provider that has a key set, and appends them to `~/.bashrc`. The
keys never print to the terminal.

```bash
python3 << 'PY' >> ~/.bashrc
import json, pathlib
d = json.loads(pathlib.Path.home().joinpath(".config/ask/config.json").read_text())
for p, c in d.get("providers", {}).items():
    if c.get("api_key"):
        print(f'export ASK_{p.upper()}_API_KEY={json.dumps(c["api_key"])}')
PY
```

---

## Step 3 — Verify the new lines landed (values masked)

```bash
tail -6 ~/.bashrc | sed -E 's/(ASK_[A-Z_]+=)["\x27]?[^"\x27]+["\x27]?/\1***/'
```

You should see lines like `export ASK_ANTHROPIC_API_KEY=***` for each
migrated provider.

---

## Step 4 — Reload and confirm env vars are set

```bash
source ~/.bashrc
env | grep '^ASK_' | sed -E 's/=.+$/=***/'
```

---

## Step 5 — Blank the keys in config.json

Ask-cli already prefers env vars over config-file values, so this is
belt-and-braces. It preserves the rest of the config (default provider,
models, prompts) and re-applies `chmod 0o600` for good measure.

```bash
python3 << 'PY'
import json, pathlib
p = pathlib.Path.home() / ".config/ask/config.json"
d = json.loads(p.read_text())
cleared = []
for name, c in d.get("providers", {}).items():
    if c.get("api_key"):
        c["api_key"] = ""
        cleared.append(name)
p.write_text(json.dumps(d, indent=2))
p.chmod(0o600)
print(f"Cleared: {cleared}" if cleared else "Nothing to clear.")
PY
```

---

## Step 6 — Smoke test

```bash
ask --list-providers
```

Every migrated provider should still show `configured`. If any shows
`not configured`, the env var didn't land — check step 4's output.

```bash
ask "hi in one line"
```

---

## Cleanup

Once verified, this file can be deleted — it's a one-off. It's kept
under `docs/one-off/` so it's discoverable but clearly non-permanent.
