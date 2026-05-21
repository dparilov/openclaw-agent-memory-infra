# Pyrogram Capability

Pyrogram provides Telegram client-mode access. The OpenClaw multi-agent system uses it for two purposes:

1. **Handoff dispatch** — sending messages between CODER, REVIEWER, and ASSISTANT topic channels via a user session.
2. **Telegram history import** — reading message history for memory restore (`восстанови память из Telegram`).

Pyrogram is **optional**. Missing Pyrogram or a session file does not block agent bootstrap or READY reporting.

---

## Where to find Pyrogram

Check system Python first, then the OpenClaw-managed virtualenv
(`~/.openclaw/workspace/.venv/lib/python3.12/site-packages`):

```bash
# System Python
python3 -c "import pyrogram" 2>/dev/null && echo "system"

# OpenClaw venv
~/.openclaw/workspace/.venv/bin/python -c "import pyrogram" 2>/dev/null && echo "venv"
```

If neither location has Pyrogram: capability is `unavailable`. This does not block READY.

---

## Canonical session path

The canonical session file is:

```
~/.agent-secrets/pyrogram/userbot.session
```

If the session file exists at the legacy path `~/.openclaw/workspace/ops/userbot.session`
but not the canonical path, normalize it:

```bash
mkdir -p ~/.agent-secrets/pyrogram
cp ~/.openclaw/workspace/ops/userbot.session ~/.agent-secrets/pyrogram/userbot.session
chmod 600 ~/.agent-secrets/pyrogram/userbot.session
# Create symlink so legacy path still resolves
ln -sf ~/.agent-secrets/pyrogram/userbot.session ~/.openclaw/workspace/ops/userbot.session
```

If no session file found at either path: capability is `unavailable`. This does not block READY.

---

## Capability check procedure

Perform at bootstrap, before reporting READY.

### Step 1 — Check Pyrogram import

```bash
python3 -c "import pyrogram" 2>/dev/null && echo "system" ||   ~/.openclaw/workspace/.venv/bin/python -c "import pyrogram" 2>/dev/null && echo "venv" ||   echo "not installed"
```

If not installed: capability is `unavailable`. Skip step 2. Report and continue.

### Step 2 — Check session file

```bash
ls -la ~/.agent-secrets/pyrogram/userbot.session 2>/dev/null   || ls -la ~/.openclaw/workspace/ops/userbot.session 2>/dev/null   || echo "no session file found"
```

If no session file: capability is `unavailable`. Report and continue.

If session exists at legacy path only → normalize it (see above).

If both Pyrogram and session are present: capability is `ready`.

---

## READY report format

Include one of these lines in your READY response:

```
Pyrogram capability: ready (session: ~/.agent-secrets/pyrogram/userbot.session)
```

or

```
Pyrogram capability: unavailable (not installed / no session; affected: auto-handoff dispatch, Telegram history import; fallback: manual notification, local memory)
```

---

## What Pyrogram absence affects

| Feature | Without Pyrogram |
|---------|-----------------|
| Auto handoff dispatch | Manual notification required |
| Telegram history import | Not available; use local memory only |
| Local memory restore | ✅ Unaffected |
| CODER/REVIEWER bootstrap | ✅ Unaffected |
| ASSISTANT bootstrap | ✅ Unaffected |
