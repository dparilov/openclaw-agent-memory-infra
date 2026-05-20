# Pyrogram Optional Capability

Pyrogram is an **optional** capability for all agent roles (CODER, REVIEWER, ASSISTANT). Its absence does not block role initialization or normal operation.

---

## What Pyrogram enables

| Feature | Description |
|---------|-------------|
| Auto-handoff dispatch | Send handoff notifications to Telegram topics via a Pyrogram user session |
| Telegram history import | Read Telegram message history for memory restore via `refresh-memory.py` |

Without Pyrogram, both features fall back gracefully:

| Feature | Fallback |
|---------|----------|
| Auto-handoff dispatch | Manual handoff notification (agent posts summary; human forwards to target topic) |
| Telegram history import | Local memory only (read from `~/.assistant-memory` or project workspace directly) |

---

## Canonical session storage

```text
~/.agent-secrets/pyrogram/
  userbot.session
  registry.yaml
```

Permissions:

```bash
chmod 700 ~/.agent-secrets/pyrogram
chmod 600 ~/.agent-secrets/pyrogram/userbot.session
```

`registry.yaml` must not contain the session content. It contains metadata only:

```yaml
version: 1
scope: global
secrets:
  - id: telegram.pyrogram.userbot
    type: pyrogram_session
    location: ~/.agent-secrets/pyrogram/userbot.session
    purpose: Pyrogram user session for handoff dispatch and Telegram history import.
    access_policy: local_only
    owner: human
```

---

## Compatibility path

`scripts/read-topic.py` (and some legacy invocations) look for the session at:

```text
~/.openclaw/workspace/ops/userbot.session
```

If the session exists only at the canonical path, the agent MAY normalize the legacy path by creating a symlink:

```bash
mkdir -p ~/.openclaw/workspace/ops
ln -sf ~/.agent-secrets/pyrogram/userbot.session \
       ~/.openclaw/workspace/ops/userbot.session
```

If the session exists only at the legacy path, the agent MAY normalize it to canonical storage:

```bash
mkdir -p ~/.agent-secrets/pyrogram
cp ~/.openclaw/workspace/ops/userbot.session \
   ~/.agent-secrets/pyrogram/userbot.session
chmod 600 ~/.agent-secrets/pyrogram/userbot.session
# create the symlink back
ln -sf ~/.agent-secrets/pyrogram/userbot.session \
       ~/.openclaw/workspace/ops/userbot.session
```

---

## Capability check procedure

Perform at bootstrap, before reporting READY.

### Step 1 — Check Pyrogram import

```bash
python3 -c "import pyrogram" 2>/dev/null && echo "installed" || echo "not installed"
```

If not installed: capability is `unavailable`. Skip steps 2–3. Report and continue.

### Step 2 — Find session

Check candidates in order:

1. `$PYROGRAM_SESSION` (environment variable), if set
2. `~/.agent-secrets/pyrogram/userbot.session`
3. `~/.openclaw/workspace/ops/userbot.session`
4. Any `~/.openclaw/workspace/**/*.session`

First valid file found is the active session.

### Step 3 — Normalize (optional)

If a valid session exists outside canonical storage, the agent MAY normalize it:

```bash
mkdir -p ~/.agent-secrets/pyrogram
cp <found-session> ~/.agent-secrets/pyrogram/userbot.session
chmod 600 ~/.agent-secrets/pyrogram/userbot.session
ln -sf ~/.agent-secrets/pyrogram/userbot.session \
       ~/.openclaw/workspace/ops/userbot.session
```

Do not print session contents. Do not commit session files.

---

## READY capability report

Include in the role's READY output after `Context loaded` or equivalent last field before `Next safe action`.

**Pyrogram ready:**

```
Pyrogram capability: ready
Session: ~/.agent-secrets/pyrogram/userbot.session
Features: auto-handoff dispatch enabled; Telegram history import enabled
```

**Pyrogram unavailable (not installed):**

```
Pyrogram capability: unavailable (pyrogram not installed)
Affected features: auto-handoff dispatch disabled; Telegram history import disabled
Fallback: manual handoff notification; local memory only
```

**Pyrogram unavailable (session not found):**

```
Pyrogram capability: unavailable (session not found)
Affected features: auto-handoff dispatch disabled; Telegram history import disabled
Fallback: manual handoff notification; local memory only
```

**Pyrogram unavailable — role is not blocked:**

Missing Pyrogram or a missing session is **never** a blocking condition for role initialization. The role reports READY with `Pyrogram capability: unavailable` and continues normally.

---

## Security rules

Agents must not:

- Print session file contents.
- Commit `.session` files to any repository.
- Include session contents in memory files, handoffs, PRs, or chat.
- Ask the human to paste a Telegram login code or password in normal chat.
- Copy session strings into `ACTIVE.md` or any handoff artifact.
- Leave session files world-readable (enforce `600`).

If a session must be created from scratch:

1. Instruct the human to generate it manually (via a local `pyrogram` script or the secret-placement flow in `docs/security/SECRETS_REGISTRY_PROTOCOL.md`).
2. Use the exchange directory flow: agent writes a template to `~/.agent-secrets/exchange/templates/`; human uploads completed session to `~/.agent-secrets/exchange/incoming/`.
3. Agent installs from `incoming/` to canonical path, sets `600`, never prints the file.

---

## Related docs

- [SECRETS_REGISTRY_PROTOCOL.md](SECRETS_REGISTRY_PROTOCOL.md) — registry format and missing-secret flow
- [AGENT_SECRET_ACCESS_RULES.md](AGENT_SECRET_ACCESS_RULES.md) — agent access rules for secrets
- [WINDOWS_TO_LINUX_SECRET_PLACEMENT.md](WINDOWS_TO_LINUX_SECRET_PLACEMENT.md) — uploading session files from Windows
- [HANDOFF_DISPATCH_CONFIG.md](../agent-collaboration/HANDOFF_DISPATCH_CONFIG.md) — handoff dispatch configuration
