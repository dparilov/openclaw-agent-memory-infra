#!/usr/bin/env python3
"""
read-topic.py — Читает историю топика через Pyrogram userbot.

Использование:
  python3 scripts/context_access/read-topic.py <topic_id|topic_name> [options]

Примеры:
  python3 scripts/context_access/read-topic.py telemost
  python3 scripts/context_access/read-topic.py 7301 --limit 300
  python3 scripts/context_access/read-topic.py 7301 --since-id 15800
  python3 scripts/context_access/read-topic.py 7301 --batch-format

Выходные форматы:
  (default)       raw transcript — строки вида [DD.MM HH:MM] sender: text
  --batch-format  структурированный вывод для передачи в archive-batch-v2.py

Переменные окружения:
  OPENCLAW_AGENTS   путь к ~/.openclaw/agents/ (default: ~/.openclaw/agents)
  PYROGRAM_SESSION  путь к файлу .session (default: ~/.openclaw/workspace/ops/userbot)
  PYROGRAM_VENV     путь к site-packages pyrogram (auto-detect если не задан)
"""
import argparse
import asyncio
import importlib.util
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def find_pyrogram():
    """Locate pyrogram in known venv locations or system."""
    candidates = [
        Path.home() / ".openclaw/workspace/.venv/lib/python3.12/site-packages",
        Path.home() / ".openclaw/workspace/.venv/lib/python3.11/site-packages",
        Path(os.environ.get("PYROGRAM_VENV", "")),
    ]
    for c in candidates:
        if c.exists() and (c / "pyrogram").exists():
            return str(c)
    return None  # rely on system python path


def checkpoint_path(topic_id: str) -> Path:
    """Path to sub-batch checkpoint file for this topic."""
    ops_dir = Path.home() / ".openclaw/workspace/ops"
    ops_dir.mkdir(parents=True, exist_ok=True)
    return ops_dir / f"read-topic-checkpoint-{topic_id}.json"


def load_checkpoint(topic_id: str) -> int | None:
    """Return last processed message_id from checkpoint, or None."""
    import json as _json
    cp = checkpoint_path(topic_id)
    if cp.exists():
        try:
            data = _json.loads(cp.read_text())
            return int(data["last_message_id"])
        except Exception:
            return None
    return None


def save_checkpoint(topic_id: str, last_message_id: int, sub_batch: int) -> None:
    """Write checkpoint after processing a sub-batch."""
    import json as _json
    cp = checkpoint_path(topic_id)
    cp.write_text(_json.dumps({
        "topic_id": topic_id,
        "last_message_id": last_message_id,
        "sub_batch": sub_batch,
        "ts": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, ensure_ascii=False))
    print(f"[read-topic] Checkpoint saved: last_message_id={last_message_id} sub_batch={sub_batch}", file=sys.stderr)


def clear_checkpoint(topic_id: str) -> None:
    cp = checkpoint_path(topic_id)
    if cp.exists():
        cp.unlink()
        print(f"[read-topic] Checkpoint cleared for topic {topic_id}", file=sys.stderr)


def find_session_file():
    """Locate userbot .session file."""
    explicit = os.environ.get("PYROGRAM_SESSION")
    if explicit:
        return str(Path(explicit).parent), Path(explicit).name.replace(".session", "")
    default = Path.home() / ".openclaw/workspace/ops"
    if (default / "userbot.session").exists():
        return str(default), "userbot"
    # search common locations
    for pattern in [
        Path.home() / ".openclaw/workspace" / "**" / "*.session",
    ]:
        import glob
        found = glob.glob(str(pattern), recursive=True)
        if found:
            p = Path(found[0])
            return str(p.parent), p.stem
    raise SystemExit("ERROR: userbot .session file not found. Set PYROGRAM_SESSION env var.")


def agents_base() -> Path:
    return Path(os.environ.get("OPENCLAW_AGENTS", Path.home() / ".openclaw/agents"))


# ---------------------------------------------------------------------------
# Import resolve_topic_id from archive-batch-v2 (hyphen in name → importlib)
# ---------------------------------------------------------------------------

def import_archive_batch():
    script = Path(__file__).parent / "archive-batch-v2.py"
    if not script.exists():
        raise SystemExit(f"ERROR: archive-batch-v2.py not found at {script}")
    spec = importlib.util.spec_from_file_location("archive_batch_v2", script)
    mod = importlib.util.module_from_spec(spec)
    import sys; sys.modules["archive_batch_v2"] = mod  # required for @dataclass to resolve module
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Discover chat_id from session metadata for a given topic_id
# ---------------------------------------------------------------------------

def discover_chat_id(topic_id: str, base: Path) -> str | None:
    """Extract Telegram chat_id from session files for this topic."""
    patterns = [
        str(base / "*" / "sessions" / f"*-topic-{topic_id}.jsonl"),
    ]
    import glob
    paths = []
    for p in patterns:
        paths.extend(glob.glob(p))
    if not paths:
        return None
    # read first file, grab chat_id from metadata
    for path in sorted(paths):
        text = Path(path).read_text(errors="replace")
        m = re.search(r'"chat_id"\s*:\s*"?(?:telegram:)?(-?\d+)"?', text)
        if m:
            return m.group(1)
        # fallback: conversation_label
        m = re.search(r'conversation_label[^:]*:\s*"[^"]*id:(-?\d+)', text)
        if m:
            return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Pyrogram reader with FloodWait retry
# ---------------------------------------------------------------------------

async def fetch_messages(
    chat_id: int,
    topic_id: int,
    limit: int,
    since_id: int | None,
    workdir: str,
    session_name: str,
) -> list[tuple]:
    """Fetch messages from Telegram topic. Returns list of (date, msg_id, sender, text)."""
    from pyrogram import Client
    from pyrogram.errors import FloodWait

    app = Client(session_name, workdir=workdir)
    messages = []

    max_retries = 4
    for attempt in range(max_retries):
        try:
            async with app:
                fetch_limit = min(limit * 4, 10000)  # fetch extra, filter by topic
                async for msg in app.get_chat_history(chat_id, limit=fetch_limit):
                    # filter by topic thread
                    thread_id = (
                        getattr(msg, "message_thread_id", None)
                        or getattr(msg, "reply_to_message_id", None)
                    )
                    if topic_id == 0:
                        if thread_id is not None and thread_id != 0:
                            continue
                    else:
                        if msg.id != topic_id and thread_id != topic_id:
                            continue

                    # delta filter
                    if since_id is not None and msg.id <= since_id:
                        continue

                    text = msg.text or msg.caption or ""
                    if not text and msg.media:
                        text = f"[{msg.media}]"

                    sender = "unknown"
                    if msg.from_user:
                        sender = (
                            msg.from_user.first_name
                            or msg.from_user.username
                            or str(msg.from_user.id)
                        )
                    elif msg.sender_chat:
                        sender = msg.sender_chat.title or "chat"

                    messages.append((msg.date, msg.id, sender, text))
                    if len(messages) >= limit:
                        break
            break  # success

        except FloodWait as e:
            wait = e.value
            if attempt < max_retries - 1:
                print(
                    f"[read-topic] FloodWait {wait}s (attempt {attempt+1}/{max_retries}), waiting...",
                    file=sys.stderr,
                )
                await asyncio.sleep(wait + 2)
            else:
                raise SystemExit(f"ERROR: FloodWait {wait}s exceeded max retries") from e

    messages.sort(key=lambda x: x[0])
    return messages


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def print_raw(messages: list[tuple], chat_id: int, topic_id: int) -> None:
    print(f"=== Топик {topic_id} в чате {chat_id} ({len(messages)} сообщений) ===\n")
    for date, mid, sender, text in messages:
        preview = text[:500].replace("\n", " ")
        print(f"[{date.strftime('%d.%m %H:%M')}] {sender}: {preview}")
    print("\n=== END ===")
    if messages:
        last_id = messages[-1][1]
        print(f"\n# last-message-id: {last_id}", file=sys.stderr)


def print_batch_format(messages: list[tuple], chat_id: int, topic_id: int) -> None:
    """Output as structured transcript block, suitable for LLM fact-extraction
    and downstream piping into archive-batch-v2.py --batch."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    print(f"## Transcript — {now}")
    print(f"## Source: telegram:{chat_id}:{topic_id} | messages: {len(messages)}")
    if messages:
        first_ts = messages[0][0].strftime("%Y-%m-%dT%H:%M:%S")
        last_ts = messages[-1][0].strftime("%Y-%m-%dT%H:%M:%S")
        last_id = messages[-1][1]
        print(f"## Range: {first_ts} → {last_ts} | last-id: {last_id}")
    print()
    for date, mid, sender, text in messages:
        ts = date.strftime("%Y-%m-%dT%H:%M")
        lines = text.strip().split("\n")
        for i, line in enumerate(lines):
            prefix = f"[{ts}] {sender}: " if i == 0 else " " * (len(ts) + len(sender) + 4)
            print(prefix + line)
    print()
    print("## END TRANSCRIPT")
    if messages:
        print(f"# Pipe this output to fact-extraction, then: archive-batch-v2.py <topic> --write", file=sys.stderr)
        print(f"# last-message-id: {messages[-1][1]}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Read Telegram topic history via Pyrogram userbot"
    )
    parser.add_argument("topic", help="Topic ID (numeric) or topic name (e.g. telemost)")
    parser.add_argument("--limit", type=int, default=500, help="Max messages to fetch (default: 500)")
    parser.add_argument("--since-id", type=int, default=None, help="Only fetch messages after this message ID")
    parser.add_argument("--chat-id", type=str, default=None, help="Override chat_id (skip auto-discovery)")
    parser.add_argument("--batch-format", action="store_true", help="Output structured transcript for write-pipeline")
    parser.add_argument("--sub-batch-size", type=int, default=200,
                        help="Max messages per output sub-batch (default: 200). If more fetched, "
                             "outputs first sub-batch and writes checkpoint for --resume.")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from checkpoint: use last saved message ID as --since-id.")
    parser.add_argument("--clear-checkpoint", action="store_true",
                        help="Clear checkpoint file for this topic and exit.")
    args = parser.parse_args()

    # 1. resolve topic name → numeric ID
    base = agents_base()
    ab = import_archive_batch()

    # Handle --clear-checkpoint early (before resolution if possible)
    if args.clear_checkpoint:
        # resolve first to get numeric id
        topic_id_str_early = ab.resolve_topic_id(args.topic, base)
        clear_checkpoint(topic_id_str_early)
        return

    topic_id_str = ab.resolve_topic_id(args.topic, base)
    topic_id_int = int(topic_id_str)

    # --resume: load since_id from checkpoint
    if args.resume and args.since_id is None:
        saved = load_checkpoint(topic_id_str)
        if saved is not None:
            print(f"[read-topic] Resuming from checkpoint: since_id={saved}", file=sys.stderr)
            args.since_id = saved
        else:
            print("[read-topic] No checkpoint found, reading from beginning", file=sys.stderr)

    # 2. discover chat_id
    chat_id_str = args.chat_id or discover_chat_id(topic_id_str, base)
    if not chat_id_str:
        raise SystemExit(
            f"ERROR: could not discover chat_id for topic {topic_id_str}. "
            "Use --chat-id to specify explicitly."
        )
    chat_id_int = int(chat_id_str)

    # 3. locate pyrogram
    venv = find_pyrogram()
    if venv:
        sys.path.insert(0, venv)

    # 4. locate session file
    workdir, session_name = find_session_file()

    print(
        f"[read-topic] chat={chat_id_int} topic={topic_id_int} limit={args.limit} since_id={args.since_id}",
        file=sys.stderr,
    )

    # 5. fetch
    messages = asyncio.run(
        fetch_messages(
            chat_id=chat_id_int,
            topic_id=topic_id_int,
            limit=args.limit,
            since_id=args.since_id,
            workdir=workdir,
            session_name=session_name,
        )
    )

    # 6. sub-batch split + checkpoint
    sub = args.sub_batch_size
    total = len(messages)
    if total > sub:
        # Output only the first sub-batch; checkpoint last message of that batch
        output_msgs = messages[:sub]
        remaining = total - sub
        last_id = output_msgs[-1][1]  # msg_id from tuple (date, msg_id, sender, text)
        print(
            f"[read-topic] {total} messages fetched, outputting sub-batch 0 ({sub} msgs). "
            f"Remaining: {remaining}. Run with --resume to continue.",
            file=sys.stderr,
        )
        save_checkpoint(topic_id_str, last_id, sub_batch=0)
    else:
        output_msgs = messages
        # If we had a checkpoint and finished all messages, clear it
        if args.resume:
            clear_checkpoint(topic_id_str)

    # 7. output
    if args.batch_format:
        print_batch_format(output_msgs, chat_id_int, topic_id_int)
    else:
        print_raw(output_msgs, chat_id_int, topic_id_int)


if __name__ == "__main__":
    main()
