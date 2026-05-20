#!/usr/bin/env python3
"""Handoff dispatcher: reads ACTIVE.md state and sends a Telegram trigger
via Pyrogram user session to the correct agent topic.

Default mode: dry-run (--send required for real Telegram dispatch).

Usage:
    python3 scripts/handoff-dispatch.py --target /path/to/project
    python3 scripts/handoff-dispatch.py --target /path/to/project --send
    python3 scripts/handoff-dispatch.py --target /path/to/project --send --force

Reference docs:
    docs/agent-collaboration/HANDOFF_DISPATCH_PROTOCOL.md
    docs/agent-collaboration/HANDOFF_DISPATCH_CONFIG.md
    docs/agent-collaboration/HANDOFF_DISPATCH_MESSAGES.md
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Dispatch table: (status, to_role) -> (topic_key, message_key)
# ---------------------------------------------------------------------------
DISPATCH_TABLE = {
    ("ready_for_implementation", "CODER"): ("coder", "ready_for_implementation"),
    ("changes_requested", "CODER"): ("coder", "changes_requested"),
    ("ready_for_review", "REVIEWER"): ("reviewer", "ready_for_review"),
    ("approved", "HUMAN"): ("human", "approved"),
}

DEFAULT_MESSAGES = {
    "ready_for_implementation": "Read ACTIVE handoff and implement the task.",
    "changes_requested": "Read ACTIVE handoff and fix reviewer blockers only.",
    "ready_for_review": "Read ACTIVE handoff and review the implementation.",
    "approved": "APPROVED. Human may merge after final checks.",
}


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def read_frontmatter(path: Path) -> dict:
    """Extract YAML frontmatter from a markdown file. Returns {} if none."""
    content = path.read_text(encoding="utf-8")
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return yaml.safe_load(parts[1]) or {}
    return {}


def update_frontmatter(path: Path, updates: dict) -> None:
    """Merge updates into YAML frontmatter of a markdown file."""
    content = path.read_text(encoding="utf-8")
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm = yaml.safe_load(parts[1]) or {}
            rest = "---" + parts[2]  # "---\nbody..."
        else:
            fm = {}
            rest = "---\n" + content
    else:
        fm = {}
        rest = "---\n" + content

    _deep_merge(fm, updates)
    path.write_text(
        "---\n" + yaml.dump(fm, default_flow_style=False) + rest,
        encoding="utf-8",
    )


def _deep_merge(base: dict, updates: dict) -> None:
    for k, v in updates.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Route ACTIVE.md handoff state to Telegram via Pyrogram.",
    )
    p.add_argument("--target", required=True, help="Project root path")
    p.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Print planned action without sending (default when --send is omitted)",
    )
    p.add_argument(
        "--send", action="store_true", default=False,
        help="Actually send the Telegram message via Pyrogram",
    )
    p.add_argument(
        "--force", action="store_true", default=False,
        help="Ignore idempotency metadata and send again",
    )
    p.add_argument("--config", default=None, help="Override config path")
    p.add_argument("--active", default=None, help="Override ACTIVE.md path")
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _print_dry_run(
    target, active_path, status, to_role, chat_id, topic_config,
    topic_is_name, topic_id, message, is_force, already_dispatched,
):
    if topic_is_name:
        resolved_line = "<requires --send for name resolution>"
    else:
        resolved_line = str(topic_id)

    if already_dispatched and not is_force:
        idempotency = "previously dispatched (--force not set)"
    elif is_force:
        idempotency = "--force bypasses idempotency"
    else:
        idempotency = "not previously dispatched"

    print(
        f"HANDOFF DISPATCH DRY RUN\n\n"
        f"Target: {target}\n"
        f"Active handoff: {active_path}\n"
        f"Status: {status}\n"
        f"To role: {to_role}\n"
        f"Chat: {chat_id}\n"
        f"Topic: {topic_config}\n"
        f"Resolved topic id: {resolved_line}\n"
        f"Message: {message}\n"
        f"Action: would send\n"
        f"Idempotency: {idempotency}"
    )


def _print_sent(status, to_role, chat_id, topic_config, topic_id, message_id):
    print(
        f"HANDOFF DISPATCH SENT\n\n"
        f"Status: {status}\n"
        f"To role: {to_role}\n"
        f"Chat: {chat_id}\n"
        f"Topic: {topic_config}\n"
        f"Resolved topic id: {topic_id}\n"
        f"Message id: {message_id}\n"
        f"ACTIVE.md dispatch metadata updated: yes"
    )


def _print_skipped(status, to_role):
    print(
        f"HANDOFF DISPATCH SKIPPED\n\n"
        f"Reason: already dispatched\n"
        f"Status: {status}\n"
        f"To role: {to_role}\n"
        f"Use --force to send again."
    )


def _print_failed(reason, status, to_role, message):
    print(
        f"HANDOFF DISPATCH FAILED\n\n"
        f"Reason: {reason}\n"
        f"Status: {status}\n"
        f"To role: {to_role}\n\n"
        f"Manual fallback:\n"
        f"Send this message to {to_role.lower()} topic manually:\n"
        f"{message}"
    )


def _print_blocked(topic_name, chat_id, message, detail=""):
    detail_section = f"\nReason detail: {detail}" if detail else ""
    print(
        f"HANDOFF DISPATCH BLOCKED\n\n"
        f"Reason: cannot resolve Telegram topic name `{topic_name}`\n"
        f"Chat: {chat_id}\n\n"
        f"Manual fix:\n"
        f"- provide exact topic id in .agent/config.yaml, or\n"
        f"- correct the topic name, or\n"
        f'- send manually: "{message}"{detail_section}'
    )


def _print_blocked_pyrogram(message):
    print(
        f"HANDOFF DISPATCH BLOCKED\n\n"
        f"Reason: Pyrogram topic-name resolution is unavailable in this environment.\n"
        f"Manual fix:\n"
        f"- provide numeric topic id in .agent/config.yaml, or\n"
        f'- send manually: "{message}"'
    )


# ---------------------------------------------------------------------------
# Pyrogram helpers  (only called from --send path)
# ---------------------------------------------------------------------------

def _resolve_topic_name(chat_id, topic_name, session_name, workdir):
    """Return (topic_id, None) on success, (None, error_str) on failure.

    Assumes Pyrogram 2.x client.get_forum_topics(chat_id) which returns
    a list of ForumTopic objects with .title and .id attributes.
    Falls back gracefully if the method is unavailable.
    """
    try:
        from pyrogram import Client
        import asyncio

        async def _run():
            async with Client(session_name, workdir=workdir) as client:
                topics = await client.get_forum_topics(chat_id)
                matches = [t for t in topics if t.title == topic_name]
                if len(matches) == 1:
                    return matches[0].id, None
                if len(matches) == 0:
                    return None, f"no topic titled {topic_name!r} in chat {chat_id}"
                return None, f"multiple topics titled {topic_name!r} in chat {chat_id}"

        return asyncio.run(_run())
    except ImportError:
        return None, "pyrogram not installed"
    except Exception as e:
        return None, f"Pyrogram topic-name resolution unavailable: {e}"


def _send_message(chat_id, topic_id, message, session_name, workdir):
    """Send message to a Telegram chat or forum topic. Returns message_id or None.

    For forum topics (topic_id > 0): passes reply_to_message_id=topic_id to
    Client.send_message, which routes the message into the correct topic thread
    (Pyrogram 2.x high-level API — message_thread_id is a Bot API parameter and
    is NOT accepted by Pyrogram's Client.send_message).

    For DMs or main group chat (topic_id falsy / 0): sends without reply_to.
    """
    try:
        from pyrogram import Client
        import asyncio

        async def _run():
            async with Client(session_name, workdir=workdir) as client:
                kwargs: dict = {"chat_id": chat_id, "text": message}
                if topic_id:
                    kwargs["reply_to_message_id"] = topic_id
                msg = await client.send_message(**kwargs)
                return msg.id

        return asyncio.run(_run())
    except Exception as e:
        print(f"ERROR: Pyrogram send failed: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Main dispatch logic
# ---------------------------------------------------------------------------

def dispatch(args):
    target = Path(args.target)
    if not target.exists():
        print(f"ERROR: Target path does not exist: {target}", file=sys.stderr)
        sys.exit(1)

    config_path = (
        Path(args.config) if args.config
        else target / ".agent" / "config.yaml"
    )
    active_path = (
        Path(args.active) if args.active
        else target / ".agent" / "handoffs" / "ACTIVE.md"
    )

    if not active_path.exists():
        print(f"ERROR: ACTIVE.md not found: {active_path}", file=sys.stderr)
        sys.exit(1)
    if not config_path.exists():
        print(f"ERROR: Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    # Load config
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    hd_cfg = raw.get("handoff_dispatch")
    if not hd_cfg:
        print("ERROR: Missing 'handoff_dispatch' section in config", file=sys.stderr)
        sys.exit(1)

    if not hd_cfg.get("enabled", True):
        print("HANDOFF DISPATCH SKIPPED\n\nReason: dispatch disabled in config (enabled: false)")
        sys.exit(0)

    # Load ACTIVE.md
    fm = read_frontmatter(active_path)
    status = fm.get("status", "")
    to_role = fm.get("to_role", "")
    dispatch_meta = fm.get("dispatch") or {}

    # Table lookup
    key = (status, to_role)
    if key not in DISPATCH_TABLE:
        print(
            f"ERROR: Unsupported status/to_role combination: "
            f"status={status!r}, to_role={to_role!r}",
            file=sys.stderr,
        )
        print("Supported combinations:", file=sys.stderr)
        for s, r in DISPATCH_TABLE:
            print(f"  status={s!r}, to_role={r!r}", file=sys.stderr)
        sys.exit(1)

    topic_key, message_key = DISPATCH_TABLE[key]

    # Message
    messages_cfg = hd_cfg.get("messages") or {}
    message = messages_cfg.get(message_key) or DEFAULT_MESSAGES[message_key]

    # Telegram config
    tg = hd_cfg.get("telegram") or {}
    chat_id = tg.get("chat_id")
    topics = tg.get("topics") or {}
    topic_config = topics.get(topic_key)

    if topic_config is None:
        print(
            f"ERROR: No topic configured for '{topic_key}' in "
            f"handoff_dispatch.telegram.topics",
            file=sys.stderr,
        )
        sys.exit(1)

    topic_is_name = isinstance(topic_config, str)
    topic_id = None if topic_is_name else int(topic_config)
    topic_name = topic_config if topic_is_name else None

    # Idempotency state
    already_dispatched = (
        dispatch_meta.get("last_status") == status
        and dispatch_meta.get("last_to_role") == to_role
    )

    # --- Dry-run path (default) ---
    if not args.send:
        if already_dispatched and not args.force:
            _print_skipped(status, to_role)
            sys.exit(0)
        _print_dry_run(
            target, active_path, status, to_role, chat_id, topic_config,
            topic_is_name, topic_id, message, args.force, already_dispatched,
        )
        return

    # --- Send path ---
    if already_dispatched and not args.force:
        _print_skipped(status, to_role)
        sys.exit(0)

    # Pyrogram config
    pyr = hd_cfg.get("pyrogram") or {}
    session_name = pyr.get("session_name", "handoff_dispatcher")
    workdir = os.path.expanduser(pyr.get("workdir", "~/.pyrogram"))

    # Check Pyrogram available
    try:
        import pyrogram  # noqa: F401
    except ImportError:
        _print_failed(
            reason="Pyrogram not installed. Run: pip install pyrogram",
            status=status,
            to_role=to_role,
            message=message,
        )
        sys.exit(1)

    # Resolve topic name if needed
    if topic_is_name:
        resolved_id, err = _resolve_topic_name(
            chat_id, topic_name, session_name, workdir
        )
        if err and "unavailable" in err:
            _print_blocked_pyrogram(message)
            sys.exit(1)
        if err:
            _print_blocked(topic_name, chat_id, message, detail=err)
            sys.exit(1)
        topic_id = resolved_id

    # Send
    message_id = _send_message(chat_id, topic_id, message, session_name, workdir)
    if message_id is None:
        _print_failed(
            reason="Pyrogram send failed",
            status=status,
            to_role=to_role,
            message=message,
        )
        sys.exit(1)

    # Update ACTIVE.md dispatch metadata
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    update_frontmatter(active_path, {
        "dispatch": {
            "last_status": status,
            "last_to_role": to_role,
            "dispatched_at": now,
            "transport": "pyrogram_user",
            "telegram_chat_id": chat_id,
            "telegram_topic_id": topic_id,
            "telegram_topic_name": topic_name or "",
            "telegram_message_id": message_id,
        }
    })

    _print_sent(status, to_role, chat_id, topic_config, topic_id, message_id)


def main():
    args = parse_args()
    dispatch(args)


if __name__ == "__main__":
    main()
