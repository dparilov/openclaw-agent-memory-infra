# Pyrogram Userbot: Flood-Wait and Lock Handling

## Overview

> **Extension point.** For topics fully covered by OpenClaw session files,
> Pyrogram is not needed — use `archive-batch-v2.py` (source 2 in `FALLBACK_ORDER.md`).
> Pyrogram becomes relevant only for reading pre-OpenClaw Telegram history.
> `read-topic.py` is planned to become part of this repo as a first-class fallback tool.

`read-topic.py` uses a Pyrogram userbot session to read Telegram messages
directly. Two failure modes are common in production use:

1. **Telegram flood-wait** — Telegram rate-limits the account and returns
   `FloodWait(seconds=N)`. The client must sleep for N seconds before retrying.
2. **SQLite session lock** — Pyrogram stores session state in a SQLite file
   (`userbot.session`). If two processes open the same session file concurrently,
   one gets `database is locked`.

---

## Flood-Wait

### Symptoms
```
pyrogram.errors.exceptions.flood_420.FloodWait: Telegram says: wait X seconds
```

### Cause
Reading many messages in a short time triggers Telegram's rate limiter. The
limit varies by account age, activity, and whether the account is flagged.

### Handling strategy

**In `read-topic.py`:** catch `FloodWait` and sleep for the required duration.

```python
from pyrogram.errors import FloodWait
import time

try:
    async for message in client.get_chat_history(chat_id, limit=200):
        ...
except FloodWait as e:
    print(f"FloodWait: sleeping {e.value}s", file=sys.stderr)
    time.sleep(e.value + 2)   # +2s safety margin
    # then retry or exit gracefully
```

**Caller-side (agent or script):** if `read-topic.py` exits with a non-zero
code and stderr contains "FloodWait", wait and retry. Suggested retry policy:

| Attempt | Wait before retry |
|---------|-------------------|
| 1st     | As reported by Telegram + 5s |
| 2nd     | 60s |
| 3rd     | Give up; fall back to transcript read (source 2 in `FALLBACK_ORDER.md`) |

### Prevention
- Prefer transcript read (`archive-batch-v2.py`) over live Pyrogram read
  whenever session files exist — it generates zero Telegram API calls.
- If live read is necessary, read in batches with `--limit` and add a short
  sleep between batches (0.5–1s).
- Do not run multiple concurrent `read-topic.py` processes for the same account.

---

## SQLite Session Lock

### Symptoms
```
sqlite3.OperationalError: database is locked
```
or Pyrogram's equivalent:
```
aiosqlite.OperationalError: database is locked
```

### Cause
Two processes opened the same `userbot.session` SQLite file simultaneously.
This happens when:
- A previous `read-topic.py` process crashed without releasing the lock.
- Two agent sessions run `read-topic.py` concurrently.

### Handling strategy

**Prevention:** only one process should use the session file at a time. Use a
lockfile before starting:

```bash
LOCKFILE=/tmp/userbot-session.lock
exec 200>"$LOCKFILE"
flock -n 200 || { echo "userbot already in use"; exit 1; }
python3 read-topic.py "$@"
```

**Recovery:** if a lock file is stale (process died), remove it:
```bash
rm -f /tmp/userbot-session.lock
```

**Agent-side:** if `read-topic.py` fails with "database is locked", wait 10s
and retry once. If it fails again, fall back to transcript read.

---

## Summary table

| Failure | Exit code | Stderr contains | Action |
|---------|-----------|-----------------|--------|
| FloodWait | 1 | `FloodWait` | Sleep N+5s, retry up to 2x, then fallback |
| SQLite lock | 1 | `database is locked` | Wait 10s, retry once, then fallback |
| Auth expired | 1 | `SessionPasswordNeeded` / `AuthKeyUnregistered` | Manual reauth required; fallback |
| Topic not found | 1 | `PeerIdInvalid` | Check topic ID; use numeric ID |

---

## Fallback

When Pyrogram read fails for any reason, fall back to **source 2**
(OpenClaw transcript read via `archive-batch-v2.py`). See `FALLBACK_ORDER.md`.
