# Deployment Guide

This document describes everything required to deploy this project on a new machine.
Without these steps the scripts will fail silently or produce confusing errors.

---

## 1. Python dependencies

```bash
pip install pyyaml pyrogram
```

- **PyYAML** — required by candidate schema parsing
- **Pyrogram** — required by `read-topic.py` and `archive-batch-v2.py` for Telegram access

Python 3.10+ is required.

---

## 2. Telegram userbot session

Place a valid Pyrogram userbot session at:

```
$OPENCLAW_OPS_DIR/userbot.session
```

Default path (when env var is not set):

```
~/.openclaw/workspace/ops/userbot.session
```

Without this file `read-topic.py` and `archive-batch-v2.py` will fail with
`SessionPasswordNeeded` or `AuthKeyUnregistered`.

---

## 3. Skill commands require Claude Code CLI

Slash commands like `/archive-context`, `/read-context`, `/read-topic` are
**OpenClaw skills**. They work only when a **Claude Code CLI session is running
and connected** to the OpenClaw gateway.

### How it works

```
Telegram message → openclaw-gateway → Claude Code CLI (meridian-openclaw)
                                              ↓
                                     Skill executed via CLI
```

When CLI is not running, the agent responds with:

```
I can't use the tool "skill" here because it isn't available.
```

### Required: keep CLI running

```bash
# Start the CLI session (adjust path to your install)
node ~/meridian-openclaw/dist/cli.js
```

The process should stay alive (e.g., via systemd user unit or tmux) as long as
you need skill commands to work from Telegram.

### What works without CLI

Even without CLI, the following work directly in Telegram:
- Bash tool (file system, git, Python scripts)
- `read-topic.py` via direct invocation
- All MCP tools (sessions history, scheduler, etc.)

Skills (`/archive-context`, `/read-context`, `/read-topic`) do **not** work
without an active CLI session.

---

## 4. Bootstrap project directory

```bash
bash setup.sh --target /path/to/project
```

This creates the `.agent/memory/` skeleton required by all write scripts.

**macOS note:** `setup.sh` requires `realpath` or Python 3 for path resolution.
The script auto-detects and falls back to Python if GNU coreutils are absent.
No extra install needed.

---

## 5. Environment variables (optional overrides)

| Variable             | Default                             | Purpose                                        |
| -------------------- | ----------------------------------- | ---------------------------------------------- |
| `OPENCLAW_OPS_DIR`   | `~/.openclaw/workspace/ops`         | Location of `userbot.session` and checkpoints  |
| `OPENCLAW_STATE_DIR` | `$OPENCLAW_OPS_DIR/checkpoints`     | Checkpoint files for `read-topic --resume`     |
| `PYTHON`             | `python3`                           | Python interpreter override for `setup.sh`     |

---

## 6. Verify installation

```bash
# 1. Check Python deps
python3 -c "import yaml, pyrogram; print('deps ok')"

# 2. Check session exists
ls ~/.openclaw/workspace/ops/userbot.session

# 3. Dry-run setup.sh
bash setup.sh --target /tmp/test-deploy --dry-run

# 4. Read a topic directly (replace IDs with your values)
python3 scripts/context_access/read-topic.py 15222 --chat-id -1003596522926 --limit 5

# 5. Run test suite
python3 -m unittest discover -s tests -v

# 6. Check CLI is running (for skill commands)
pgrep -a node | grep meridian-openclaw
```

All steps should complete without errors. Step 6 is optional if you don't need
slash-command skills from Telegram.

---

## Known issues

### `@dataclass` fails under `importlib` dynamic load

**Symptom:**
```
AttributeError: 'NoneType' object has no attribute '__dict__'. Did you mean: '__dir__'?
```

**Cause:** `read-topic.py` loads `archive-batch-v2.py` via `importlib.util.spec_from_file_location`
but did not register it in `sys.modules`. Python's `@dataclass` decorator needs
the module in `sys.modules` to resolve its own namespace.

**Fix:** Applied in `read-topic.py` — the module is now registered before `exec_module`:
```python
sys.modules["archive_batch_v2"] = mod  # required for @dataclass to resolve module
spec.loader.exec_module(mod)
```

This is already fixed in the current codebase. If you see this error,
ensure you are on a recent commit (post `fix/telegram-native-skills`).
