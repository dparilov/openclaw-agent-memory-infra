#!/usr/bin/env python3
"""
refresh-memory.py — v1 refresh-memory command (single-topic, local input).

Thin wrapper that runs, in sequence:
  1. archive-context.py  — ingest local input into raw chunks
  2. compile-working-memory.py — compile chunks into working/*.md drafts

Default mode is dry-run. Use --write to actually write files.

Does NOT:
  - call LLM APIs
  - use vector DB / embeddings / memory-core
  - run OpenClaw doctor/fix/repair
  - auto-commit or auto-push
  - implement multi-topic orchestration

Usage (dry-run, default):
    python3 scripts/refresh-memory.py \\
        --target /path/to/project \\
        --topic 7301:coder \\
        --input /path/to/context.md \\
        --source-type markdown_export

Usage (write mode):
    python3 scripts/refresh-memory.py \\
        --target /path/to/project \\
        --topic 7301:coder \\
        --input /path/to/context.md \\
        --source-type markdown_export \\
        --write

Usage (Telegram mode, write):
    python3 scripts/refresh-memory.py \\
        --target /path/to/project \\
        --topic 7301:coder \\
        --read-topic \\
        --chat-id -1003596522926 \\
        --limit 200 \\
        --write

Usage (Telegram mode, message-ID range):
    python3 scripts/refresh-memory.py \\
        --target /path/to/project \\
        --topic 7301:coder \\
        --read-topic \\
        --chat-id -1003596522926 \\
        --since-id 15000 --until-id 16000 \\
        --write

Usage (Telegram mode, date range):
    python3 scripts/refresh-memory.py \\
        --target /path/to/project \\
        --topic 7301:coder \\
        --read-topic \\
        --chat-id -1003596522926 \\
        --since 2026-05-01 --until 2026-05-15 \\
        --write

Usage (Telegram mode, full read):
    python3 scripts/refresh-memory.py \\
        --target /path/to/project \\
        --topic 7301:coder \\
        --read-topic \\
        --chat-id -1003596522926 \\
        --full --confirm-large-read \\
        --write

Exit codes:
    0  — both steps succeeded (or dry-run succeeded)
    1  — validation error, archive step failed, or compile step failed
"""
from __future__ import annotations

import argparse
import importlib.util
import math
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_ROLES = frozenset({"coder", "reviewer", "infra", "unknown"})
ALLOWED_SOURCE_TYPES = frozenset({"session_jsonl", "markdown_export", "operator_note"})
WORKING_FILES = ("agent-brief.md", "current-state.md", "known-issues.md")

_SCRIPTS_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Script loading
# ---------------------------------------------------------------------------

def _load_script(name: str):
    """Load a hyphen-named script from scripts/ via importlib."""
    path = _SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _clear_existing_chunks(raw_dir: Path) -> int:
    """
    Delete chunk-*.md files in raw_dir (write mode only).
    Returns the number of files deleted.
    Does not remove the directory or any non-chunk files.
    """
    if not raw_dir.exists():
        return 0
    count = 0
    for chunk in sorted(raw_dir.glob("chunk-*.md")):
        chunk.unlink()
        count += 1
    return count


def _load_read_topic():
    """Load read-topic.py from scripts/context_access/ via importlib."""
    ctx_dir = str(_SCRIPTS_DIR / "context_access")
    if ctx_dir not in sys.path:
        sys.path.insert(0, ctx_dir)
    path = _SCRIPTS_DIR / "context_access" / "read-topic.py"
    spec = importlib.util.spec_from_file_location("read_topic", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Topic parsing
# ---------------------------------------------------------------------------

def parse_topic(topic_str: str) -> Tuple[str, str]:
    """
    Parse '<topic-id>:<role>' → (topic_id, role).
    Raises ValueError on invalid format or unknown role.
    """
    parts = topic_str.split(":", 1)
    if len(parts) != 2:
        raise ValueError(
            f"invalid topic format {topic_str!r}: expected <id>:<role>"
        )
    topic_id, role = parts[0].strip(), parts[1].strip()
    if not topic_id:
        raise ValueError(f"empty topic id in {topic_str!r}")
    if role not in ALLOWED_ROLES:
        raise ValueError(
            f"unknown role {role!r}; allowed: {', '.join(sorted(ALLOWED_ROLES))}"
        )
    return topic_id, role


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate(
    target: Path,
    input_path: Path,
    topic_str: str,
    source_type: str,
) -> Optional[str]:
    """Return error string if validation fails, else None."""
    if not target.exists() or not target.is_dir():
        return f"ERROR: --target not found or not a directory: {target}"
    if not (target / ".agent" / "AGENT_CONTEXT.md").exists():
        return f"ERROR: .agent/AGENT_CONTEXT.md not found in {target}"
    if not input_path.exists() or not input_path.is_file():
        return f"ERROR: --input not found or not a file: {input_path}"
    try:
        parse_topic(topic_str)
    except ValueError as e:
        return f"ERROR: --topic: {e}"
    if source_type not in ALLOWED_SOURCE_TYPES:
        return (
            f"ERROR: invalid --source-type {source_type!r}; "
            f"allowed: {', '.join(sorted(ALLOWED_SOURCE_TYPES))}"
        )
    return None


# ---------------------------------------------------------------------------
# Input counting
# ---------------------------------------------------------------------------

def _count_input(
    input_path: Path,
    source_type: str,
    chunk_size: int,
) -> Tuple[int, Optional[int], int]:
    """
    Count input statistics before archiving.
    Returns (lines_read, logical_records_or_None, planned_chunks).
    logical_records is None when not determinable (printed as 'unknown').
    planned_chunks estimated from non-empty lines / chunk_size.
    """
    try:
        text = input_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0, None, 0
    all_lines = text.splitlines()
    lines_read = len(all_lines)
    non_empty = [ln for ln in all_lines if ln.strip()]
    logical_records: Optional[int] = len(non_empty) if source_type == "session_jsonl" else None
    planned = math.ceil(len(non_empty) / chunk_size) if non_empty else 0
    return lines_read, logical_records, max(1, planned) if non_empty else 0


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _build_report(
    mode: str,
    target: Path,
    topic_id: str,
    role: str,
    input_path: Path,
    source_type: str,
    archive_status: str,
    compile_status: str,
    warnings: List[str],
    *,
    lines_read: int = 0,
    logical_records: Optional[int] = None,
    planned_chunks: int = 0,
    notes_path: Optional[Path] = None,
    raw_chunk_paths: Optional[List[Path]] = None,
    existing_chunks: int = 0,
    chunks_replaced: str = "NO",
) -> str:
    raw_dir = f".agent/memory/raw/topic-{topic_id}/"
    warn_lines = "\n".join(f"- {w}" for w in warnings) if warnings else "- none"
    working_lines = "\n".join(
        f"- .agent/memory/working/{f}" for f in WORKING_FILES
    )

    # --- Input processed ---
    logical_str = str(logical_records) if logical_records is not None else "unknown"
    chunks_written = len(raw_chunk_paths) if raw_chunk_paths else 0
    chunk_line = (
        f"- raw chunks written: {chunks_written}"
        if mode == "write"
        else f"- raw chunks planned: {planned_chunks}"
    )
    input_section = (
        "Input processed:\n"
        f"- input file: {input_path}\n"
        f"- source type: {source_type}\n"
        f"- lines read: {lines_read}\n"
        f"- logical records/messages: {logical_str}\n"
        f"{chunk_line}"
    )

    # --- Files read ---
    files_read: List[str] = [
        f"- {input_path}",
        f"- {target / '.agent' / 'AGENT_CONTEXT.md'}",
    ]
    if notes_path:
        files_read.append(f"- {notes_path}")
    if raw_chunk_paths:
        for p in raw_chunk_paths:
            files_read.append(f"- {p}  (compile input)")
    files_read_section = "Files read:\n" + "\n".join(files_read)

    # --- Files written ---
    if mode == "write" and raw_chunk_paths:
        written: List[str] = [f"- {p}" for p in raw_chunk_paths]
        written += [f"- .agent/memory/working/{f}" for f in WORKING_FILES]
        files_written_section = "Files written:\n" + "\n".join(written)
    else:
        files_written_section = "Files written:\n- none"

    # --- Files not touched ---
    not_touched_section = (
        "Files not touched:\n"
        "- .agent/memory/index/\n"
        "- .agent/memory/candidates/\n"
        "- .agent/memory/wiki/\n"
        "- git staging / commits"
    )

    return (
        "REFRESH MEMORY REPORT\n\n"
        f"Mode: {mode}\n"
        f"Target: {target}\n"
        f"Topic: {topic_id}\n"
        f"Role: {role}\n\n"
        f"{input_section}\n\n"
        f"Existing raw chunks: {existing_chunks}\n"
        f"Raw chunks replaced: {chunks_replaced}\n\n"
        f"Archive step: {archive_status}\n"
        f"Compile step: {compile_status}\n\n"
        f"Raw output:\n- {raw_dir}\n\n"
        f"Working files:\n{working_lines}\n\n"
        f"{files_read_section}\n\n"
        f"{files_written_section}\n\n"
        f"{not_touched_section}\n\n"
        f"Warnings:\n{warn_lines}\n\n"
        "Notes:\n"
        "- No Telegram read performed.\n"
        "- No LLM API calls performed.\n"
        "- No vector DB / embeddings / memory-core used.\n"
    )


# ---------------------------------------------------------------------------
# Telegram report
# ---------------------------------------------------------------------------

def _build_telegram_report(
    mode: str,
    target: Path,
    topic_id: str,
    role: str,
    chat_id: str,
    archive_status: str,
    compile_status: str,
    warnings: List[str],
    *,
    read_mode: str = "limit",
    limit: Optional[int] = None,
    since_id: Optional[int] = None,
    until_id: Optional[int] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    max_scan: Optional[int] = None,
    messages_fetched: Optional[int] = None,
    messages_archived: Optional[int] = None,
    planned: bool = False,
    notes_path: Optional[Path] = None,
    raw_chunk_paths: Optional[List[Path]] = None,
    existing_chunks: int = 0,
    chunks_replaced: str = "NO",
) -> str:
    raw_dir = f".agent/memory/raw/topic-{topic_id}/"
    warn_lines = "\n".join(f"- {w}" for w in warnings) if warnings else "- none"
    working_lines = "\n".join(f"- .agent/memory/working/{f}" for f in WORKING_FILES)

    fetched_str = str(messages_fetched) if messages_fetched is not None else "unknown"
    archived_str = str(messages_archived) if messages_archived is not None else "unknown"
    export_str = "planned (dry-run)" if planned else "deleted"

    tg_lines = [
        "Telegram read:",
        f"- mode: {read_mode}",
        f"- chat id: {chat_id}",
        f"- topic id: {topic_id}",
    ]
    if limit is not None:
        tg_lines.append(f"- limit: {limit}")
    if since_id is not None:
        tg_lines.append(f"- since-id: {since_id}")
    if until_id is not None:
        tg_lines.append(f"- until-id: {until_id}")
    if since is not None:
        tg_lines.append(f"- since: {since}")
    if until is not None:
        tg_lines.append(f"- until: {until}")
    tg_lines.append(f"- max-scan: {max_scan if max_scan is not None else 10000}")
    tg_lines.append(f"- messages fetched: {fetched_str}")
    tg_lines.append(f"- messages archived: {archived_str}")
    tg_lines.append(f"- temporary export: {export_str}")
    telegram_section = "\n".join(tg_lines)

    chunks_written = len(raw_chunk_paths) if raw_chunk_paths else 0
    if planned:
        chunk_line = "- raw chunks planned: (dry-run)"
    elif mode == "write":
        chunk_line = f"- raw chunks written: {chunks_written}"
    else:
        chunk_line = "- raw chunks planned: unknown"

    input_section = (
        "Input processed:\n"
        "- source type: telegram_topic\n"
        f"- logical records/messages: {fetched_str}\n"
        f"{chunk_line}"
    )

    files_read: List[str] = [
        f"- {target / '.agent' / 'AGENT_CONTEXT.md'}",
    ]
    if notes_path:
        files_read.append(f"- {notes_path}")
    if raw_chunk_paths:
        for p in raw_chunk_paths:
            files_read.append(f"- {p}  (compile input)")
    files_read_section = "Files read:\n" + "\n".join(files_read)

    if mode == "write" and raw_chunk_paths:
        written: List[str] = [f"- {p}" for p in raw_chunk_paths]
        written += [f"- .agent/memory/working/{f}" for f in WORKING_FILES]
        files_written_section = "Files written:\n" + "\n".join(written)
    else:
        files_written_section = "Files written:\n- none"

    not_touched_section = (
        "Files not touched:\n"
        "- .agent/memory/index/\n"
        "- .agent/memory/candidates/\n"
        "- .agent/memory/wiki/\n"
        "- git staging / commits"
    )

    if planned:
        tg_note = f"- Telegram read: planned (dry-run, mode={read_mode})."
    else:
        tg_note = f"- Telegram read performed via read-topic.py (mode={read_mode})."

    return (
        "REFRESH MEMORY REPORT\n\n"
        f"Mode: {mode}\n"
        f"Target: {target}\n"
        f"Topic: {topic_id}\n"
        f"Role: {role}\n\n"
        f"{telegram_section}\n\n"
        f"{input_section}\n\n"
        f"Existing raw chunks: {existing_chunks}\n"
        f"Raw chunks replaced: {chunks_replaced}\n\n"
        f"Archive step: {archive_status}\n"
        f"Compile step: {compile_status}\n\n"
        f"Raw output:\n- {raw_dir}\n\n"
        f"Working files:\n{working_lines}\n\n"
        f"{files_read_section}\n\n"
        f"{files_written_section}\n\n"
        f"{not_touched_section}\n\n"
        f"Warnings:\n{warn_lines}\n\n"
        "Notes:\n"
        f"{tg_note}\n"
        "- No LLM API calls performed.\n"
        "- No vector DB / embeddings / memory-core used.\n"
    )


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def refresh(
    target: Path,
    topic_id: str,
    role: str,
    input_path: Path,
    source_type: str,
    write: bool = False,
    notes_path: Optional[Path] = None,
    chunk_size: int = 200,
    # Injectable for testing — pass mock modules instead of loading from disk
    _archive_mod=None,
    _compile_mod=None,
) -> Tuple[int, str]:
    """
    Run archive step then compile step.
    Returns (exit_code, report_text).
    """
    mode = "write" if write else "dry-run"
    warnings: List[str] = []

    # Count input before running archive
    lines_read, logical_records, planned_chunks = _count_input(
        input_path, source_type, chunk_size
    )

    # Inspect / clear existing raw chunks
    raw_dir_path = target / ".agent" / "memory" / "raw" / f"topic-{topic_id}"
    if write:
        existing_chunks = _clear_existing_chunks(raw_dir_path)
        chunks_replaced = "YES" if existing_chunks > 0 else "NO"
    else:
        existing_chunks = (
            len(list(raw_dir_path.glob("chunk-*.md")))
            if raw_dir_path.exists() else 0
        )
        chunks_replaced = "planned" if existing_chunks > 0 else "NO"

    # Load scripts lazily (allow injection in tests)
    if _archive_mod is None:
        try:
            _archive_mod = _load_script("archive-context")
        except Exception as e:
            return 1, f"ERROR: could not load archive-context.py: {e}"

    if _compile_mod is None:
        try:
            _compile_mod = _load_script("compile-working-memory")
        except Exception as e:
            return 1, f"ERROR: could not load compile-working-memory.py: {e}"

    # -----------------------------------------------------------------------
    # Archive step
    # -----------------------------------------------------------------------
    archive_argv: List[str] = [
        "--target", str(target),
        "--topic", topic_id,
        "--role", role,
        "--input", str(input_path),
        "--source-type", source_type,
        "--chunk-size", str(chunk_size),
    ]
    if write:
        archive_argv.append("--write")
    # dry-run is archive-context default; no flag needed

    archive_code = _run_step(_archive_mod, archive_argv, warnings, "archive")
    archive_status = "PASS" if archive_code == 0 else "FAIL"

    # Enumerate written chunks (write mode only, after successful archive)
    raw_chunk_paths: Optional[List[Path]] = None
    if archive_code == 0 and write:
        raw_dir_path = target / ".agent" / "memory" / "raw" / f"topic-{topic_id}"
        if raw_dir_path.exists():
            raw_chunk_paths = sorted(raw_dir_path.glob("chunk-*.md"))

    if archive_code != 0:
        return 1, _build_report(
            mode, target, topic_id, role, input_path, source_type,
            archive_status, "SKIP", warnings,
            lines_read=lines_read,
            logical_records=logical_records,
            planned_chunks=planned_chunks,
            notes_path=notes_path,
            existing_chunks=existing_chunks,
            chunks_replaced=chunks_replaced,
        )

    # -----------------------------------------------------------------------
    # Compile step
    # -----------------------------------------------------------------------
    compile_argv: List[str] = [
        "--target", str(target),
        "--topics", f"{topic_id}:{role}",
    ]
    if notes_path:
        compile_argv += ["--notes", str(notes_path)]
    if write:
        compile_argv.append("--write")
    else:
        compile_argv.append("--dry-run")

    compile_code = _run_step(_compile_mod, compile_argv, warnings, "compile")
    compile_status = "PASS" if compile_code == 0 else "FAIL"

    exit_code = 0 if compile_code == 0 else 1
    return exit_code, _build_report(
        mode, target, topic_id, role, input_path, source_type,
        archive_status, compile_status, warnings,
        lines_read=lines_read,
        logical_records=logical_records,
        planned_chunks=planned_chunks,
        notes_path=notes_path,
        raw_chunk_paths=raw_chunk_paths,
        existing_chunks=existing_chunks,
        chunks_replaced=chunks_replaced,
    )


# ---------------------------------------------------------------------------
# Telegram message count parser
# ---------------------------------------------------------------------------

def _parse_message_count(transcript_text: str) -> Optional[int]:
    """
    Parse message count from read-topic.py transcript output.

    Tries explicit metadata patterns first:
      raw format:   '=== Топик ... (N сообщений) ==='
      batch format: '## Source: telegram:...:... | messages: N'

    Falls back to counting non-empty, non-header lines when neither
    pattern is found.
    Returns None if count cannot be determined.
    """
    import re as _re

    # Pattern 1: raw format header
    m = _re.search(r"\((\d+) \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0439\)", transcript_text)
    if m:
        return int(m.group(1))

    # Pattern 2: batch format header
    m = _re.search(r"messages:\s*(\d+)", transcript_text)
    if m:
        return int(m.group(1))

    # Fallback: count non-empty, non-header lines
    lines = transcript_text.splitlines()
    count = sum(
        1 for ln in lines
        if ln.strip() and not ln.startswith("===") and not ln.startswith("##")
    )
    return count if count > 0 else None


def _detect_read_mode(
    limit: Optional[int],
    since_id: Optional[int],
    until_id: Optional[int],
    since: Optional[str],
    until: Optional[str],
    full: bool,
) -> str:
    """Determine the read mode from the supplied flags."""
    if full:
        return "full"
    if since is not None and until is not None:
        return "date-range"
    if since is not None:
        return "since-date"
    if since_id is not None and until_id is not None:
        return "message-id-range"
    if since_id is not None:
        return "since-id"
    return "limit"


def refresh_telegram(
    target: Path,
    topic_id: str,
    role: str,
    chat_id: str,
    write: bool = False,
    notes_path: Optional[Path] = None,
    chunk_size: int = 200,
    *,
    limit: Optional[int] = None,
    since_id: Optional[int] = None,
    until_id: Optional[int] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    full: bool = False,
    max_scan: Optional[int] = None,
    # Injectable for testing
    _read_topic_mod=None,
    _archive_mod=None,
    _compile_mod=None,
) -> Tuple[int, str]:
    """
    Telegram read path: read-topic.py -> archive-context.py -> compile-working-memory.py.
    Dry-run: no Telegram network call; reports as 'planned'.
    """
    import os as _os
    import tempfile

    mode = "write" if write else "dry-run"
    warnings: List[str] = []
    read_mode = _detect_read_mode(limit, since_id, until_id, since, until, full)

    # Common kwargs for _build_telegram_report
    _report_kw = dict(
        read_mode=read_mode, limit=limit, since_id=since_id,
        until_id=until_id, since=since, until=until,
        max_scan=max_scan,
    )

    # Dry-run: skip Telegram call entirely
    if not write:
        tg_raw_dir = target / ".agent" / "memory" / "raw" / f"topic-{topic_id}"
        dry_existing = (
            len(list(tg_raw_dir.glob("chunk-*.md")))
            if tg_raw_dir.exists() else 0
        )
        dry_replaced = "planned" if dry_existing > 0 else "NO"
        return 0, _build_telegram_report(
            mode=mode, target=target, topic_id=topic_id, role=role,
            chat_id=chat_id,
            archive_status="SKIP", compile_status="SKIP",
            warnings=warnings, planned=True, notes_path=notes_path,
            existing_chunks=dry_existing, chunks_replaced=dry_replaced,
            **_report_kw,
        )

    # --- Write mode: create temp file for transcript ---
    tmp_fd, tmp_path_str = tempfile.mkstemp(suffix=".md", prefix="refresh-tg-")
    _os.close(tmp_fd)
    tmp_path = Path(tmp_path_str)
    messages_fetched: Optional[int] = None

    try:
        # Load read-topic module
        if _read_topic_mod is None:
            try:
                _read_topic_mod = _load_read_topic()
            except Exception as e:
                tmp_path.unlink(missing_ok=True)
                return 1, (
                    f"REFRESH MEMORY REPORT\n\nMode: {mode}\n"
                    f"ERROR: could not load read-topic.py: {e}\n"
                )

        # Call read-topic with --out to write transcript to temp file
        read_argv: List[str] = [
            str(topic_id),
            "--chat-id", chat_id,
            "--out", str(tmp_path),
        ]
        if limit is not None:
            read_argv += ["--limit", str(limit)]
        if since_id is not None:
            read_argv += ["--since-id", str(since_id)]
        if until_id is not None:
            read_argv += ["--until-id", str(until_id)]
        if since is not None:
            read_argv += ["--since", since]
        if until is not None:
            read_argv += ["--until", until]
        if max_scan is not None:
            read_argv += ["--max-scan", str(max_scan)]
        if full:
            read_argv += ["--full", "--confirm-large-read"]
        read_code = _run_step(_read_topic_mod, read_argv, warnings, "read-topic")
        if read_code != 0:
            tmp_path.unlink(missing_ok=True)
            # Read failed: existing chunks were NOT touched
            tg_raw_dir = target / ".agent" / "memory" / "raw" / f"topic-{topic_id}"
            surviving = (
                len(list(tg_raw_dir.glob("chunk-*.md")))
                if tg_raw_dir.exists() else 0
            )
            return 1, _build_telegram_report(
                mode=mode, target=target, topic_id=topic_id, role=role,
                chat_id=chat_id,
                archive_status="FAIL", compile_status="SKIP",
                warnings=warnings, notes_path=notes_path,
                existing_chunks=surviving, chunks_replaced="NO",
                **_report_kw,
            )

        # Read succeeded: safe to clear existing raw chunks now
        tg_raw_dir = target / ".agent" / "memory" / "raw" / f"topic-{topic_id}"
        existing_chunks = _clear_existing_chunks(tg_raw_dir)
        chunks_replaced = "YES" if existing_chunks > 0 else "NO"

        # Estimate messages_fetched from non-empty, non-header lines
        try:
            lines = tmp_path.read_text(encoding="utf-8", errors="replace").splitlines()
            messages_fetched = sum(
                1 for ln in lines
                if ln.strip() and not ln.startswith("===") and not ln.startswith("##")
            )
        except Exception:
            messages_fetched = None

        # Load archive module
        if _archive_mod is None:
            try:
                _archive_mod = _load_script("archive-context")
            except Exception as e:
                tmp_path.unlink(missing_ok=True)
                return 1, (
                    f"REFRESH MEMORY REPORT\n\nMode: {mode}\n"
                    f"ERROR: could not load archive-context.py: {e}\n"
                )

        archive_argv: List[str] = [
            "--target", str(target),
            "--topic", topic_id,
            "--role", role,
            "--input", str(tmp_path),
            "--source-type", "telegram_topic",
            "--chunk-size", str(chunk_size),
            "--write",
        ]
        archive_code = _run_step(_archive_mod, archive_argv, warnings, "archive")
        archive_status = "PASS" if archive_code == 0 else "FAIL"

        raw_chunk_paths: Optional[List[Path]] = None
        if archive_code == 0:
            raw_dir_path = target / ".agent" / "memory" / "raw" / f"topic-{topic_id}"
            if raw_dir_path.exists():
                raw_chunk_paths = sorted(raw_dir_path.glob("chunk-*.md"))
        # messages_archived = messages processed (same as fetched), not chunk count
        messages_archived = messages_fetched

        # Clean up temp file
        tmp_path.unlink(missing_ok=True)

        if archive_code != 0:
            return 1, _build_telegram_report(
                mode=mode, target=target, topic_id=topic_id, role=role,
                chat_id=chat_id,
                archive_status=archive_status, compile_status="SKIP",
                warnings=warnings, messages_fetched=messages_fetched,
                messages_archived=messages_archived, notes_path=notes_path,
                existing_chunks=existing_chunks, chunks_replaced=chunks_replaced,
                **_report_kw,
            )

        # Load compile module
        if _compile_mod is None:
            try:
                _compile_mod = _load_script("compile-working-memory")
            except Exception as e:
                return 1, (
                    f"REFRESH MEMORY REPORT\n\nMode: {mode}\n"
                    f"ERROR: could not load compile-working-memory.py: {e}\n"
                )

        compile_argv: List[str] = [
            "--target", str(target),
            "--topics", f"{topic_id}:{role}",
        ]
        if notes_path:
            compile_argv += ["--notes", str(notes_path)]
        compile_argv.append("--write")

        compile_code = _run_step(_compile_mod, compile_argv, warnings, "compile")
        compile_status = "PASS" if compile_code == 0 else "FAIL"

        exit_code = 0 if compile_code == 0 else 1
        return exit_code, _build_telegram_report(
            mode=mode, target=target, topic_id=topic_id, role=role,
            chat_id=chat_id,
            archive_status=archive_status, compile_status=compile_status,
            warnings=warnings, messages_fetched=messages_fetched,
            messages_archived=messages_archived, raw_chunk_paths=raw_chunk_paths,
            notes_path=notes_path,
            existing_chunks=existing_chunks, chunks_replaced=chunks_replaced,
            **_report_kw,
        )

    except Exception as exc:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        warnings.append(f"unexpected exception: {exc}")
        return 1, _build_telegram_report(
            mode=mode, target=target, topic_id=topic_id, role=role,
            chat_id=chat_id,
            archive_status="FAIL", compile_status="SKIP",
            warnings=warnings, notes_path=notes_path,
            **_report_kw,
        )


def _run_step(mod, argv: List[str], warnings: List[str], label: str) -> int:
    """Invoke mod.main(argv), return integer exit code."""
    try:
        code = mod.main(argv)
        return code if isinstance(code, int) else 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    except Exception as e:
        warnings.append(f"{label} step exception: {e}")
        return 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="refresh-memory",
        description=(
            "Thin wrapper: archive-context.py → compile-working-memory.py "
            "for one local input and one topic. Default: dry-run."
        ),
    )
    p.add_argument(
        "--target", required=True,
        help="Path to target project directory.",
    )
    p.add_argument(
        "--topic", required=True,
        help="Topic spec: <id>:<role>. Role: coder|reviewer|infra|unknown.",
    )
    p.add_argument(
        "--input", required=False, default=None, dest="input_path",
        help="Path to local input file (local mode).",
    )
    p.add_argument(
        "--source-type", required=False, default=None, dest="source_type",
        choices=sorted(ALLOWED_SOURCE_TYPES),
        help="Input source type (local mode).",
    )
    p.add_argument(
        "--read-topic", action="store_true", default=False, dest="read_topic",
        help="Telegram mode: read from topic instead of local --input file.",
    )
    p.add_argument(
        "--chat-id", default=None, dest="chat_id",
        help="Telegram chat ID (required with --read-topic).",
    )
    p.add_argument(
        "--limit", type=int, default=None,
        help="Max messages to fetch (Telegram mode; must be positive).",
    )
    p.add_argument(
        "--since-id", type=int, default=None, dest="since_id",
        help="Only fetch messages after this message ID (must be positive).",
    )
    p.add_argument(
        "--until-id", type=int, default=None, dest="until_id",
        help="Only fetch messages up to this message ID (requires --since-id; must be positive).",
    )
    p.add_argument(
        "--since", default=None,
        help="Only fetch messages after this date (YYYY-MM-DD).",
    )
    p.add_argument(
        "--until", default=None,
        help="Only fetch messages before this date (YYYY-MM-DD; requires --since).",
    )
    p.add_argument(
        "--full", action="store_true", default=False,
        help="Read entire topic history (requires --confirm-large-read).",
    )
    p.add_argument(
        "--confirm-large-read", action="store_true", default=False, dest="confirm_large_read",
        help="Acknowledge that --full may fetch many messages.",
    )
    p.add_argument(
        "--max-scan", type=int, default=None, dest="max_scan",
        help="Max messages to scan from Telegram history (safety cap, default: 10000). Must be positive.",
    )
    p.add_argument(
        "--notes", default=None,
        help="Optional path to operator notes file.",
    )
    p.add_argument(
        "--chunk-size", type=int, default=200, dest="chunk_size",
        help="Lines per raw chunk (passed to archive-context). Default: 200.",
    )
    p.add_argument(
        "--write", action="store_true", default=False,
        help="Write files. Default is dry-run.",
    )
    p.add_argument(
        "--dry-run", action="store_true", default=False, dest="dry_run",
        help="Explicit dry-run (default behaviour).",
    )
    return p


def _parse_date(s: str) -> str:
    """Validate YYYY-MM-DD format and return the string. Raises ValueError."""
    from datetime import datetime as _dt
    _dt.strptime(s, "%Y-%m-%d")
    return s


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    target = Path(args.target)
    notes_path = Path(args.notes) if args.notes else None

    # --dry-run overrides --write
    write = args.write and not args.dry_run

    # --chunk-size must be positive
    if args.chunk_size <= 0:
        print(f"ERROR: --chunk-size must be a positive integer, got {args.chunk_size}")
        return 1

    # Mode detection
    has_local = args.input_path is not None
    has_telegram = args.read_topic

    if has_local and has_telegram:
        print("ERROR: --input and --read-topic are mutually exclusive")
        return 1

    if not has_local and not has_telegram:
        print(
            "ERROR: specify either --input + --source-type (local mode) "
            "or --read-topic + --chat-id + --limit (Telegram mode)"
        )
        return 1

    # --- Telegram mode ---
    if has_telegram:
        if not args.chat_id:
            print("ERROR: --read-topic requires --chat-id")
            return 1

        # --topics unsupported
        if hasattr(args, "topics") and args.topics:
            print("ERROR: --topics is not supported; use --topic for single-topic mode")
            return 1

        # Selector validation: at least one required
        has_limit = args.limit is not None
        has_since_id = args.since_id is not None
        has_until_id = args.until_id is not None
        has_since = args.since is not None
        has_until = args.until is not None
        has_full = args.full

        if not (has_limit or has_since_id or has_since or has_full):
            print(
                "ERROR: --read-topic requires at least one read selector: "
                "--limit, --since-id, --since, or --full"
            )
            return 1

        # --full validation
        if has_full:
            if not args.confirm_large_read:
                print("ERROR: --full requires --confirm-large-read")
                return 1
            if has_limit or has_since_id or has_until_id or has_since or has_until:
                print("ERROR: --full cannot be combined with --limit, --since-id, --until-id, --since, or --until")
                return 1

        # Reject ambiguous combos: --limit + --since-id, --limit + --since
        if has_limit and has_since_id:
            print("ERROR: --limit and --since-id are ambiguous; use one selector mode")
            return 1
        if has_limit and has_since:
            print("ERROR: --limit and --since are ambiguous; use one selector mode")
            return 1

        # --limit must be positive
        if has_limit and args.limit <= 0:
            print(f"ERROR: --limit must be a positive integer, got {args.limit}")
            return 1

        # --since-id / --until-id must be positive
        if has_since_id and args.since_id <= 0:
            print(f"ERROR: --since-id must be a positive integer, got {args.since_id}")
            return 1
        if has_until_id and args.until_id <= 0:
            print(f"ERROR: --until-id must be a positive integer, got {args.until_id}")
            return 1

        # --max-scan must be positive
        if args.max_scan is not None and args.max_scan <= 0:
            print(f"ERROR: --max-scan must be a positive integer, got {args.max_scan}")
            return 1

        # --until-id requires --since-id
        if has_until_id and not has_since_id:
            print("ERROR: --until-id requires --since-id")
            return 1

        # --until requires --since
        if has_until and not has_since:
            print("ERROR: --until requires --since")
            return 1

        # Validate date formats
        if has_since:
            try:
                _parse_date(args.since)
            except ValueError:
                print(f"ERROR: --since must be YYYY-MM-DD, got {args.since!r}")
                return 1
        if has_until:
            try:
                _parse_date(args.until)
            except ValueError:
                print(f"ERROR: --until must be YYYY-MM-DD, got {args.until!r}")
                return 1

        if not target.exists() or not target.is_dir():
            print(f"ERROR: --target not found or not a directory: {target}")
            return 1
        if not (target / ".agent" / "AGENT_CONTEXT.md").exists():
            print(f"ERROR: .agent/AGENT_CONTEXT.md not found in {target}")
            return 1

        try:
            topic_id, role = parse_topic(args.topic)
        except ValueError as e:
            print(f"ERROR: --topic: {e}")
            return 1

        exit_code, report = refresh_telegram(
            target=target,
            topic_id=topic_id,
            role=role,
            chat_id=args.chat_id,
            write=write,
            notes_path=notes_path,
            chunk_size=args.chunk_size,
            limit=args.limit,
            since_id=args.since_id,
            until_id=args.until_id,
            since=args.since,
            until=args.until,
            full=args.full,
            max_scan=args.max_scan,
        )
        print(report)
        return exit_code

    # --- Local mode ---
    input_path = Path(args.input_path)
    if not args.source_type:
        print("ERROR: --input requires --source-type")
        return 1

    err = _validate(target, input_path, args.topic, args.source_type)
    if err:
        print(err)
        return 1

    topic_id, role = parse_topic(args.topic)

    exit_code, report = refresh(
        target=target,
        topic_id=topic_id,
        role=role,
        input_path=input_path,
        source_type=args.source_type,
        write=write,
        notes_path=notes_path,
        chunk_size=args.chunk_size,
    )
    print(report)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
