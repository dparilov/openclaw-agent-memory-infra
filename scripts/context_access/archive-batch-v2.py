#!/usr/bin/env python3
"""
archive-batch-v2.py — deduplicating OpenClaw topic transcript batch reader.

Reads OpenClaw JSONL transcript files for a Telegram topic, merges them
chronologically, deduplicates overlapping reset-file history, and prints a
bounded batch for later memory extraction.

This script is read-only unless --mark-done or --reset is used. It does not
write memory markdown files.

Usage:
  python3 scripts/context_access/archive-batch-v2.py <topic_id|topic_name> --status
  python3 scripts/context_access/archive-batch-v2.py <topic_id|topic_name> --total
  python3 scripts/context_access/archive-batch-v2.py <topic_id|topic_name> --batch 0
  python3 scripts/context_access/archive-batch-v2.py <topic_id|topic_name> --batch 0 --batch-size 100
  python3 scripts/context_access/archive-batch-v2.py <topic_id|topic_name> --mark-done 0

  topic_id is REQUIRED — numeric ID (e.g. 7301) or topic name (e.g. telemost).
  Running without topic_id is not allowed.

Dedupe strategy:
  1. If Telegram inbound metadata is present in message text, dedupe by
     telegram:<chat_id>:<topic_id>:<message_id>:<role>.
  2. Otherwise fallback to role + minute timestamp bucket + normalized content hash.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_AGENTS_BASE = Path.home() / ".openclaw" / "agents"
DEFAULT_PROGRESS_DIR = Path.home() / ".openclaw" / "workspace" / "ops"


@dataclass(frozen=True)
class Message:
    ts_ms: int
    role: str
    text: str
    seq: str
    path: str
    dedupe_key: str


def iso_to_ms(value: str) -> int:
    try:
        s = value.rstrip("Z")
        fmt = "%Y-%m-%dT%H:%M:%S.%f" if "." in s else "%Y-%m-%dT%H:%M:%S"
        return int(datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).timestamp() * 1000)
    except Exception:
        return 0


def ts_to_str(ts_ms: int) -> str:
    if not ts_ms:
        return "?"
    try:
        return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return "?"


def content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(parts)
    return str(content or "")


def parse_jsonl_line(line: str) -> tuple[str, str, int, str] | None:
    try:
        obj = json.loads(line)
    except Exception:
        return None

    # Newer OpenClaw format.
    if obj.get("type") == "message" and isinstance(obj.get("message"), dict):
        inner = obj["message"]
        role = str(inner.get("role", ""))
        if role not in ("user", "assistant"):
            return None
        text = content_text(inner.get("content", ""))
        ts_raw = obj.get("timestamp", "")
        ts_ms = iso_to_ms(ts_raw) if isinstance(ts_raw, str) else int(ts_raw or 0)
        seq = str(obj.get("id", "?"))
        return role, text, ts_ms, seq

    # Older OpenClaw format.
    role = str(obj.get("role", ""))
    if role not in ("user", "assistant"):
        return None
    text = content_text(obj.get("content", ""))
    ts_raw = obj.get("timestamp", 0)
    ts_ms = iso_to_ms(ts_raw) if isinstance(ts_raw, str) else int(ts_raw or 0)
    seq = str(obj.get("__openclaw", {}).get("seq", "?"))
    return role, text, ts_ms, seq


def extract_inbound_meta(text: str) -> dict[str, str] | None:
    """Extract minimal trusted-looking inbound metadata embedded in user text.

    Transcript user messages contain an OpenClaw-generated metadata envelope.
    We only need chat/topic/message ids for dedupe. If parsing fails, return None.
    """
    message_id = re.search(r'"message_id"\s*:\s*"?(\d+)"?', text)
    if not message_id:
        return None

    # Prefer explicit chat_id if present; otherwise parse from conversation_label.
    chat_id = re.search(r'"chat_id"\s*:\s*"?(?:telegram:)?(-?\d+)"?', text)
    if not chat_id:
        chat_id = re.search(r'conversation_label"\s*:\s*"[^"]*id:(-?\d+)', text)

    topic_id = re.search(r'"topic_id"\s*:\s*"?(\d+)"?', text)
    if not topic_id:
        topic_id = re.search(r'conversation_label"\s*:\s*"[^"]*topic:(\d+)', text)

    return {
        "message_id": message_id.group(1),
        "chat_id": chat_id.group(1) if chat_id else "unknown-chat",
        "topic_id": topic_id.group(1) if topic_id else "unknown-topic",
    }


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def dedupe_key(role: str, text: str, ts_ms: int) -> str:
    meta = extract_inbound_meta(text)
    if meta:
        return f"telegram:{meta['chat_id']}:{meta['topic_id']}:{meta['message_id']}:{role}"
    bucket_ms = (ts_ms // 60000) * 60000 if ts_ms else 0
    digest = hashlib.sha256(normalize_text(text).encode("utf-8", "replace")).hexdigest()[:24]
    return f"fallback:{role}:{bucket_ms}:{digest}"


def discover_topic_names(agents_base: Path) -> dict[str, str]:
    """Scan session files to build a topic_name -> topic_id map.

    Reads the first 20 lines of each primary JSONL file looking for
    Telegram metadata containing topic_id and topic_name fields.
    Returns a dict mapping lowercase topic name to numeric topic id string.
    Multiple names may map to the same id (aliases are fine).
    """
    name_to_id: dict[str, str] = {}
    pattern = str(agents_base / "*" / "sessions" / "*.jsonl")
    for path in sorted(glob.glob(pattern)):
        if ".trajectory." in path or ".reset." in path:
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                checked = 0
                for line in f:
                    if checked >= 20:
                        break
                    parsed = parse_jsonl_line(line.strip())
                    if not parsed:
                        continue
                    role, text, _, _ = parsed
                    if role != "user":
                        checked += 1
                        continue
                    tid_m = re.search(r'"topic_id"\s*:\s*"?(\d+)"?', text)
                    tname_m = re.search(r'"topic_name"\s*:\s*"([^"]+)"', text)
                    if tid_m and tname_m:
                        tid = tid_m.group(1)
                        tname = tname_m.group(1).strip()
                        # Store both the original name (lowercased) and a simplified slug.
                        name_to_id[tname.lower()] = tid
                        slug = re.sub(r"[^a-z0-9]+", "-", tname.lower()).strip("-")
                        if slug and slug != tname.lower():
                            name_to_id[slug] = tid
                        break
                    checked += 1
        except Exception:
            continue
    return name_to_id


def resolve_topic_id(raw: str, agents_base: Path) -> str:
    """Resolve a topic id or name to a numeric topic id string.

    If raw is already numeric, return as-is.
    Otherwise scan session files for a matching topic_name.
    Raises SystemExit with a helpful message if not found.
    """
    if re.match(r"^\d+$", raw):
        return raw

    name_map = discover_topic_names(agents_base)
    key = raw.lower()

    # Exact match.
    if key in name_map:
        resolved = name_map[key]
        print(f"Resolved topic name '{raw}' -> topic_id:{resolved}", file=sys.stderr)
        return resolved

    # Partial match as last resort (only if unambiguous).
    matches = [(n, i) for n, i in name_map.items() if key in n or n in key]
    if len(matches) == 1:
        resolved = matches[0][1]
        print(
            f"Resolved topic name '{raw}' -> '{matches[0][0]}' -> topic_id:{resolved} (partial match)",
            file=sys.stderr,
        )
        return resolved

    available = "\n  ".join(f"{n} -> {i}" for n, i in sorted(name_map.items()))
    raise SystemExit(
        f"ERROR: topic name '{raw}' not found in session files.\n"
        f"Available topic names:\n  {available or '(none found)'}\n"
        f"Tip: Use numeric topic ID directly, or check {agents_base}/*/sessions/"
    )


def find_topic_paths(topic_id: str, agents_base: Path) -> list[str]:
    found: set[str] = set()
    for pattern in (
        str(agents_base / "*" / "sessions" / f"*-topic-{topic_id}.jsonl"),
        str(agents_base / "*" / "sessions" / f"*-topic-{topic_id}.jsonl.reset.*"),
    ):
        for p in glob.glob(pattern):
            if ".trajectory." not in p:
                found.add(p)
    return sorted(found, key=os.path.getmtime)


def load_messages(topic_id: str, agents_base: Path) -> tuple[list[Message], int, int, list[str]]:
    paths = find_topic_paths(topic_id, agents_base)
    if not paths:
        raise SystemExit(f"ERROR: no session files found for topic {topic_id} under {agents_base}")

    raw_count = 0
    duplicate_count = 0
    seen: dict[str, Message] = {}

    for path in paths:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                parsed = parse_jsonl_line(line.strip())
                if not parsed:
                    continue
                role, text, ts_ms, seq = parsed
                raw_count += 1
                if not normalize_text(text):
                    duplicate_count += 1
                    continue
                key = dedupe_key(role, text, ts_ms)
                msg = Message(ts_ms=ts_ms, role=role, text=text, seq=seq, path=path, dedupe_key=key)
                old = seen.get(key)
                if old is None:
                    seen[key] = msg
                else:
                    duplicate_count += 1
                    # Keep the earliest timestamp; if equal, keep current only if it has more text.
                    if (msg.ts_ms and old.ts_ms and msg.ts_ms < old.ts_ms) or len(msg.text) > len(old.text):
                        seen[key] = msg

    messages = sorted(seen.values(), key=lambda m: (m.ts_ms, m.role, m.dedupe_key))
    return messages, raw_count, duplicate_count, paths


def progress_file(progress_dir: Path, topic_id: str) -> Path:
    return progress_dir / f"archive-progress-{topic_id}-v2.json"


def load_progress(path: Path, topic_id: str) -> dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {"topic_id": topic_id, "last_completed_batch": -1, "total_batches": None, "updated": None}


def save_progress(path: Path, progress: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + "\n")


def print_stats(topic_id: str, paths: list[str], raw_count: int, deduped_count: int, duplicate_count: int, batch_size: int, total_batches: int) -> None:
    print("=" * 60)
    print(f"ARCHIVE SOURCE STATS  [topic:{topic_id}]")
    print(f"  Session files : {len(paths)}")
    print(f"  Raw messages  : {raw_count}")
    print(f"  Duplicates    : {duplicate_count}")
    print(f"  Deduped msgs  : {deduped_count}")
    print(f"  Batch size    : {batch_size}")
    print(f"  Total batches : {total_batches}")
    print("=" * 60)


def message_preview(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return text
    return text if len(text) <= max_chars else text[:max_chars] + "\n...[truncated]"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deduplicating archive batch reader for OpenClaw topic transcripts.",
        epilog="topic_id is required — numeric (e.g. 7301) or topic name (e.g. telemost).",
    )
    parser.add_argument(
        "topic_id",
        help="Numeric Telegram topic ID or topic name (e.g. 'telemost', 'OpenClaw_infra'). REQUIRED.",
    )
    parser.add_argument("--batch", type=int)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--total", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--mark-done", type=int)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument(
        "--max-text", type=int, default=0,
        help="truncate message text in batch output; 0 means no truncation",
    )
    parser.add_argument("--agents-base", type=Path, default=DEFAULT_AGENTS_BASE)
    parser.add_argument("--progress-dir", type=Path, default=DEFAULT_PROGRESS_DIR)
    args = parser.parse_args()

    # Resolve topic name -> numeric id before any further processing.
    args.topic_id = resolve_topic_id(args.topic_id, args.agents_base)

    pfile = progress_file(args.progress_dir, args.topic_id)

    if args.reset:
        if pfile.exists():
            pfile.unlink()
            print(f"Removed {pfile}")
        else:
            print(f"No v2 progress file found: {pfile}")
        return 0

    if args.mark_done is not None:
        progress = load_progress(pfile, args.topic_id)
        if args.mark_done > progress.get("last_completed_batch", -1):
            progress["last_completed_batch"] = args.mark_done
            progress["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            save_progress(pfile, progress)
            print(f"Marked batch {args.mark_done} as done (topic:{args.topic_id}, v2)")
        else:
            print(f"Batch {args.mark_done} was already marked done (topic:{args.topic_id}, v2)")
        return 0

    messages, raw_count, duplicate_count, paths = load_messages(args.topic_id, args.agents_base)
    deduped_count = len(messages)
    total_batches = (deduped_count + args.batch_size - 1) // args.batch_size

    progress = load_progress(pfile, args.topic_id)
    if progress.get("total_batches") != total_batches:
        progress["total_batches"] = total_batches
        # Do not write on --status/--total; keep these read-only.

    if args.total:
        print(
            f"topic:{args.topic_id} raw_msgs:{raw_count} deduped_msgs:{deduped_count} "
            f"duplicates:{duplicate_count} batch_size:{args.batch_size} total_batches:{total_batches}"
        )
        return 0

    if args.status:
        last = int(progress.get("last_completed_batch", -1))
        done = max(0, last + 1)
        pct = round(done / total_batches * 100) if total_batches else 0
        print(f"Archive progress v2  [topic:{args.topic_id}]")
        print(f"  Batches done  : {done}/{total_batches}  ({pct}%)")
        print(f"  Raw messages  : {raw_count}")
        print(f"  Deduped msgs   : {deduped_count}")
        print(f"  Duplicates     : {duplicate_count}")
        print(f"  Next batch    : {last + 1}" if done < total_batches else "  Status        : COMPLETE")
        print(f"  Progress file : {pfile}")
        if progress.get("updated"):
            print(f"  Last updated  : {progress['updated']}")
        return 0

    batch_n = args.batch if args.batch is not None else int(progress.get("last_completed_batch", -1)) + 1
    if batch_n >= total_batches:
        print(f"COMPLETE — all {total_batches} batches processed (topic:{args.topic_id}, v2)")
        return 0

    start = batch_n * args.batch_size
    end = min(start + args.batch_size, deduped_count)
    batch = messages[start:end]

    print_stats(args.topic_id, paths, raw_count, deduped_count, duplicate_count, args.batch_size, total_batches)
    print(f"BATCH {batch_n}/{total_batches - 1}  [topic:{args.topic_id}]")
    print(f"  Messages : {start}–{end - 1}  ({len(batch)} total, deduped index)")
    print(f"  From     : {ts_to_str(batch[0].ts_ms) if batch else '?'}")
    print(f"  To       : {ts_to_str(batch[-1].ts_ms) if batch else '?'}")
    print(f"  Progress : {max(0, int(progress.get('last_completed_batch', -1)) + 1)}/{total_batches} done before this batch")
    print("=" * 60)

    for msg in batch:
        print()
        print(f"[{msg.role.upper()} {ts_to_str(msg.ts_ms)}]")
        print(f"dedupe_key: {msg.dedupe_key}")
        print(f"source: {os.path.basename(msg.path)} seq:{msg.seq}")
        print(message_preview(msg.text, args.max_text))

    print()
    print("=" * 60)
    print(f"END BATCH {batch_n}/{total_batches - 1}  [topic:{args.topic_id}]")
    print(f"To mark done after archive write: python3 {Path(__file__).as_posix()} {args.topic_id} --mark-done {batch_n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
