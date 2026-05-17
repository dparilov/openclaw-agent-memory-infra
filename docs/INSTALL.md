# Installation — Project Memory Extractor v1

---

## Prerequisites

| Dependency | Required for | Notes |
|---|---|---|
| `git` | cloning PME repo | any version |
| Python 3.10+ | all scripts | stdlib only for local modes |
| GitHub access | cloning private repo | SSH key or HTTPS token |
| Pyrogram userbot session | Telegram `--read-topic` mode only | not needed for local input modes |

---

## Install

```bash
git clone <PME_GIT_URL> "$HOME/projects/openclaw-agent-memory-infra"
```

Replace `<PME_GIT_URL>` with the private repository URL for this deployment.

If the repository is private, the agent or runtime must have GitHub access
configured (SSH key or HTTPS credential) before cloning.

---

## Set environment variables (optional)

These variables are optional. If not set, scripts default to
`$HOME/projects/openclaw-agent-memory-infra` and `$HOME/projects`.

```bash
# Add to ~/.bashrc, ~/.zshrc, or set in your agent runtime environment
export PME_REPO="${PME_REPO:-$HOME/projects/openclaw-agent-memory-infra}"
export PROJECTS_ROOT="${PROJECTS_ROOT:-$HOME/projects}"
```

---

## Verify installation

```bash
python3 "$PME_REPO/scripts/refresh-memory.py" --help
python3 "$PME_REPO/scripts/recover-memory.py" --help
```

Both should print usage without errors. No pip packages are required for
local input modes.

---

## Local mode (no Telegram, no extra dependencies)

Works immediately after clone. No additional setup.

```bash
python3 "$PME_REPO/scripts/refresh-memory.py" \
  --target "$PROJECTS_ROOT/<project-dir>" \
  --topic <id>:<role> \
  --input /path/to/context.md \
  --source-type markdown_export
```

---

## Telegram mode (requires Pyrogram)

Telegram `--read-topic` mode requires a configured Pyrogram userbot session.
The session file path is controlled by your Pyrogram configuration —
no specific path is hardcoded in the scripts.

Install Pyrogram in a virtualenv if needed:
```bash
python3 -m venv "$PME_REPO/.venv"
source "$PME_REPO/.venv/bin/activate"
pip install pyrogram
```

Then configure your Pyrogram session before using `--read-topic`.

---

## Bootstrap a target project

See [docs/V1_QUICKSTART.md](V1_QUICKSTART.md) for the full 4-step flow.

Minimal bootstrap:
```bash
mkdir -p "$PROJECTS_ROOT/<project-dir>/.agent/memory/working"
# Create .agent/AGENT_CONTEXT.md — see V1_QUICKSTART.md for template
```
