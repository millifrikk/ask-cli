# One-off: restore API keys in config.json on WSL dual-entry machines

## Background

The earlier `migrate-api-keys-to-env.md` one-off moved API keys from
`~/.config/ask/config.json` → `~/.bashrc` env vars. That's the right
pattern for most Linux dev machines.

It breaks on **WSL laptops where you invoke `ask` from both WSL (`ask "..."`)
and Windows PowerShell (`wsl ask "..."`)** because non-interactive bash
(what `wsl.exe` spawns from PowerShell) doesn't source `~/.bashrc`. The
env vars only exist for interactive shells, so PowerShell invocations
get "Provider is not configured".

## Fix: keep the keys in both places

- Interactive WSL → `~/.bashrc` env vars win (env overrides config)
- `wsl ask` from PowerShell → `config.json` is read (no env vars present)

`config.json` is chmod 0o600 under `~/.config/ask/` (now chmod 0o700 on
v2.3.2+), so this isn't a secrets-exposure regression — it's the same
posture as any env-var-free install.

## Step 1 — Copy env var values back into config.json

```bash
python3 << 'PY'
import json, os, pathlib
p = pathlib.Path.home() / ".config/ask/config.json"
d = json.loads(p.read_text())
env_map = {
    "zai": "ASK_ZAI_API_KEY",
    "anthropic": "ASK_ANTHROPIC_API_KEY",
    "openai": "ASK_OPENAI_API_KEY",
    "google": "ASK_GOOGLE_API_KEY",
}
restored = []
for provider, env_var in env_map.items():
    value = os.environ.get(env_var, "")
    if value and provider in d.get("providers", {}):
        d["providers"][provider]["api_key"] = value
        restored.append(provider)
p.write_text(json.dumps(d, indent=2))
p.chmod(0o600)
print(f"Restored: {restored}" if restored else "Nothing to restore.")
PY
```

## Step 2 — Verify `wsl ask` works from PowerShell

On the Windows side, in a fresh PowerShell:

```powershell
wsl ask "hello in one line"
```

Should stream a response instead of "Provider is not configured".

## Step 3 — Optional: keep the `~/.bashrc` exports

There's no harm in keeping them — env vars override the config-file
values, so interactive WSL sessions still read the env. Two upsides:

- Rotating a key: edit once in `~/.bashrc` and `source`. Non-interactive
  still reads the old value from config.json until you update that too.
- If you'd rather have one source of truth, remove the exports from
  `~/.bashrc` and rely on config.json exclusively. Command:

```bash
sed -i -E '/^export ASK_[A-Z_]+_API_KEY=/d' ~/.bashrc
```

(This leaves `ASK_CONTEXT` alone.)

## Cleanup

Delete this file when done:

```bash
rm docs/one-off/restore-api-keys-for-wsl-dual-entry.md
```
