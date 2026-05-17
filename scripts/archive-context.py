#!/usr/bin/env python3
"""
archive-context.py — v1 minimal local-input archive command.

Reads an explicit local input file and writes Markdown archive chunks to
.agent/memory/raw/topic-<topic>/ according to docs/V1_CONTEXT_ARCHIVE_CONTRACT.md.

Usage (dry-run, default):
    python3 scripts/archive-context.py \
        --target /path/to/project \
        --topic 7301 \
        --role coder \
        --input /path/to/context.md \
        --source-type markdown_export \
        --chunk-size 200

Usage (write mode):
    python3 scripts/archive-context.py \
        --target /path/to/project \
        --topic 7301 \
        --role coder \
        --input /path/to/context.md \
        --source-type markdown_export \
        --chunk-size 200 \
        --write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_SOURCE_TYPES = ("session_jsonl", "markdown_export", "operator_note", "telegram_topic")
ALLOWED_ROLES = ("coder", "reviewer", "infra", "unknown")
DEFAULT_CHUNK_SIZE = 200

# ---------------------------------------------------------------------------
# Sensitive data patterns
# Values are NEVER stored — only category + replacement placeholder.
# Pattern order matters: more specific patterns first.
# ---------------------------------------------------------------------------

REDACT_PATTERNS: list[tuple[re.Pattern, str]] = [
    # PEM private/certificate key blocks (multi-line safe with DOTALL)
    (re.compile(r"-----BEGIN [A-Z ]+KEY-----[\s\S]*?-----END [A-Z ]+KEY-----"), "pem_key"),
    # Telegram bot token: digits:base62_35+
    (re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{35,}\b"), "telegram_bot_token"),
    # Bearer token header
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-._~+/]+=*\b"), "bearer_token"),
    # Explicit password assignment: password=VALUE or password: VALUE
    (re.compile(r"(?i)(password|passwd|pwd)\s*[=:]\s*\S+"), "password"),
    # API key assignment
    (re.compile(r"(?i)(api[_-]?key|apikey|api[_-]?secret)\s*[=:]\s*\S+"), "api_key"),
    # Token assignment
    (re.compile(r"(?i)(token|auth[_-]?token|access[_-]?token|secret[_-]?key)\s*[=:]\s*\S+"), "token"),
    # OAuth client secret
    (re.compile(r"(?i)client[_-]?secret\s*[=:]\s*\S+"), "oauth_secret"),
    # AWS-style key
    (re.compile(r"(?i)(aws[_-]?secret|aws[_-]?access[_-]?key)\s*[=:]\s*\S+"), "aws_credential"),
]

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class RedactionResult(NamedTuple):
    text: str
    counts: dict  # category -> count
    status: str   # clean | redacted


class Chunk(NamedTuple):
    index: int          # 1-based
    lines: list[str]
    message_count: int
    ts_start: str
    ts_end: str


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

def redact_text(text: str) -> RedactionResult:
    """Apply all redaction patterns; return sanitised text + summary."""
    counts: dict[str, int] = {}
    result = text

    for pattern, category in REDACT_PATTERNS:
        def _replace(m: re.Match, cat: str = category) -> str:
            counts[cat] = counts.get(cat, 0) + 1
            return f"[REDACTED:{cat}]"
        result = pattern.sub(_replace, result)

    status = "redacted" if counts else "clean"
    return RedactionResult(text=result, counts=counts, status=status)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_lines(lines: list[str], chunk_size: int) -> list[Chunk]:
    """Split plain lines into fixed-size chunks."""
    chunks: list[Chunk] = []
    for i in range(0, max(len(lines), 1), chunk_size):
        batch = lines[i:i + chunk_size]
        if not batch:
            continue
        chunks.append(Chunk(
            index=len(chunks) + 1,
            lines=batch,
            message_count=len(batch),
            ts_start="",
            ts_end="",
        ))
    return chunks


def chunk_jsonl(lines: list[str], chunk_size: int) -> list[Chunk]:
    """Split JSONL lines into chunks; extract timestamps if available."""
    chunks: list[Chunk] = []
    batch: list[str] = []
    ts_start = ""
    ts_end = ""

    for line in lines:
        line = line.rstrip()
        if not line:
            continue
        batch.append(line)
        # Try to extract timestamp from JSON
        try:
            obj = json.loads(line)
            ts = (
                obj.get("timestamp") or obj.get("ts") or
                obj.get("date") or obj.get("created_at") or ""
            )
            if ts:
                ts_str = str(ts)
                if not ts_start:
                    ts_start = ts_str
                ts_end = ts_str
        except (json.JSONDecodeError, AttributeError):
            pass

        if len(batch) >= chunk_size:
            chunks.append(Chunk(
                index=len(chunks) + 1,
                lines=batch,
                message_count=len(batch),
                ts_start=ts_start,
                ts_end=ts_end,
            ))
            batch = []
            ts_start = ""
            ts_end = ""

    if batch:
        chunks.append(Chunk(
            index=len(chunks) + 1,
            lines=batch,
            message_count=len(batch),
            ts_start=ts_start,
            ts_end=ts_end,
        ))

    return chunks or [Chunk(index=1, lines=[], message_count=0, ts_start="", ts_end="")]


def split_into_chunks(content: str, source_type: str, chunk_size: int) -> list[Chunk]:
    lines = content.splitlines()
    if source_type == "session_jsonl":
        return chunk_jsonl(lines, chunk_size)
    return chunk_lines(lines, chunk_size)


# ---------------------------------------------------------------------------
# Front-matter rendering
# ---------------------------------------------------------------------------

def render_frontmatter(
    *,
    source_type: str,
    chat_id: str,
    topic_id: str,
    topic_role: str,
    chunk: Chunk,
    redaction_status: str,
    created_at: str,
) -> str:
    mc = chunk.message_count if chunk.message_count else ""
    ts_start = chunk.ts_start or ""
    ts_end = chunk.ts_end or ""
    return (
        "---\n"
        f"source_type: {source_type}\n"
        f"chat_id: \"{chat_id}\"\n"
        f"topic_id: \"{topic_id}\"\n"
        f"topic_role: {topic_role}\n"
        "range:\n"
        f"  message_count: {mc}\n"
        f"  ts_start: \"{ts_start}\"\n"
        f"  ts_end: \"{ts_end}\"\n"
        f"created_at: \"{created_at}\"\n"
        f"redaction_status: {redaction_status}\n"
        "---\n"
    )


# ---------------------------------------------------------------------------
# Chunk file name
# ---------------------------------------------------------------------------

def chunk_filename(index: int) -> str:
    return f"chunk-{index:04d}.md"


# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------

def resolve_out_dir(target: Path, topic: str, out_override: str | None) -> Path:
    if out_override:
        return Path(out_override)
    return target / ".agent" / "memory" / "raw" / f"topic-{topic}"


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def _redaction_summary(counts: dict) -> str:
    if not counts:
        return "  none"
    return "\n".join(f"  {cat}: {n}" for cat, n in sorted(counts.items()))


def format_dry_run_report(
    *,
    input_path: Path,
    out_dir: Path,
    chunks: list[Chunk],
    redaction_results: list[RedactionResult],
    source_type: str,
    topic: str,
    role: str,
    chat_id: str,
    created_at: str,
) -> str:
    total_redactions: dict[str, int] = {}
    needs_review = False
    for rr in redaction_results:
        for cat, n in rr.counts.items():
            total_redactions[cat] = total_redactions.get(cat, 0) + n

    lines = [
        "=== archive-context dry-run ===",
        f"input:       {input_path}",
        f"source-type: {source_type}",
        f"topic:       {topic}",
        f"role:        {role}",
        f"out dir:     {out_dir}  (dry-run — not created)",
        f"chunks:      {len(chunks)}",
        "",
        "Redaction summary:",
        _redaction_summary(total_redactions),
        "",
        "--- First chunk metadata preview ---",
    ]
    if chunks:
        c = chunks[0]
        rr = redaction_results[0]
        fm = render_frontmatter(
            source_type=source_type,
            chat_id=chat_id,
            topic_id=topic,
            topic_role=role,
            chunk=c,
            redaction_status=rr.status,
            created_at=created_at,
        )
        lines.append(fm.rstrip())
        if rr.counts:
            lines.append("[chunk body omitted — redactions present]")
        else:
            preview_lines = rr.text.splitlines()[:5]
            lines.append("\n".join(preview_lines))
            if len(rr.text.splitlines()) > 5:
                lines.append(f"... ({len(rr.text.splitlines()) - 5} more lines)")
    lines.append("")
    lines.append("(pass --write to write chunks to disk)")
    return "\n".join(lines)


def format_write_report(
    *,
    out_dir: Path,
    written: list[Path],
    redaction_results: list[RedactionResult],
) -> str:
    total_redactions: dict[str, int] = {}
    for rr in redaction_results:
        for cat, n in rr.counts.items():
            total_redactions[cat] = total_redactions.get(cat, 0) + n

    lines = [
        "=== archive-context write ===",
        f"output dir:  {out_dir}",
        f"files written: {len(written)}",
    ]
    for p in written:
        lines.append(f"  {p}")
    lines += [
        "",
        "Redaction summary:",
        _redaction_summary(total_redactions),
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="archive-context",
        description="Archive explicit local context into Markdown chunks (v1).",
    )
    p.add_argument("--target", required=True,
                   help="Path to target project repo root")
    p.add_argument("--topic", required=True,
                   help="Topic ID (e.g. 7301)")
    p.add_argument("--role", required=True, choices=ALLOWED_ROLES,
                   help="Topic role")
    p.add_argument("--input", required=True, dest="input_path",
                   help="Path to input file")
    p.add_argument("--source-type", required=True, choices=ALLOWED_SOURCE_TYPES,
                   dest="source_type",
                   help="Input source type")
    p.add_argument("--chat-id", default="", dest="chat_id",
                   help="Telegram chat ID (optional)")
    p.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE,
                   dest="chunk_size",
                   help=f"Lines/messages per chunk (default: {DEFAULT_CHUNK_SIZE})")
    p.add_argument("--out", default=None,
                   help="Override output directory")
    p.add_argument("--write", action="store_true",
                   help="Write chunks to disk (default is dry-run)")
    return p


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Fix 2: validate chunk size
    if args.chunk_size <= 0:
        print(
            f"ERROR: --chunk-size must be a positive integer, got: {args.chunk_size}",
            file=sys.stderr,
        )
        return 1

    target = Path(args.target)
    input_path = Path(args.input_path)

    # Validate
    if not target.is_dir():
        print(f"ERROR: --target does not exist or is not a directory: {target}", file=sys.stderr)
        return 1
    if not input_path.is_file():
        print(f"ERROR: --input does not exist or is not a file: {input_path}", file=sys.stderr)
        return 1

    content = input_path.read_text(encoding="utf-8", errors="replace")
    chunks = split_into_chunks(content, args.source_type, args.chunk_size)
    out_dir = resolve_out_dir(target, args.topic, args.out)

    # Fix 3: --out must resolve inside --target
    if args.out:
        try:
            out_dir.resolve().relative_to(target.resolve())
        except ValueError:
            print(
                f"ERROR: --out must resolve inside --target\n"
                f"  target: {target.resolve()}\n"
                f"  out:    {Path(args.out).resolve()}",
                file=sys.stderr,
            )
            return 1

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Redact each chunk body
    redaction_results: list[RedactionResult] = []
    for chunk in chunks:
        body = "\n".join(chunk.lines)
        redaction_results.append(redact_text(body))

    if not args.write:
        # Dry-run
        print(format_dry_run_report(
            input_path=input_path,
            out_dir=out_dir,
            chunks=chunks,
            redaction_results=redaction_results,
            source_type=args.source_type,
            topic=args.topic,
            role=args.role,
            chat_id=args.chat_id,
            created_at=created_at,
        ))
        return 0

    # Fix 1: prevent accidental overwrite
    existing_chunks = sorted(out_dir.glob("chunk-*.md")) if out_dir.exists() else []
    if existing_chunks:
        sample = ", ".join(p.name for p in existing_chunks[:3])
        suffix = " ..." if len(existing_chunks) > 3 else ""
        print(
            f"ERROR: output directory already contains chunk files: {out_dir}\n"
            f"  found: {len(existing_chunks)} file(s): {sample}{suffix}",
            file=sys.stderr,
        )
        return 1

    # Write mode
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for chunk, rr in zip(chunks, redaction_results):
        fm = render_frontmatter(
            source_type=args.source_type,
            chat_id=args.chat_id,
            topic_id=args.topic,
            topic_role=args.role,
            chunk=chunk,
            redaction_status=rr.status,
            created_at=created_at,
        )
        chunk_path = out_dir / chunk_filename(chunk.index)
        chunk_path.write_text(fm + "\n" + rr.text, encoding="utf-8")
        written.append(chunk_path)

    print(format_write_report(
        out_dir=out_dir,
        written=written,
        redaction_results=redaction_results,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
