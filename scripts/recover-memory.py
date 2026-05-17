#!/usr/bin/env python3
"""
recover-memory.py — v1 recover-memory command.

Reads the compiled Markdown memory pack and prints a concise startup context
for a coding/reviewer/infra agent.

Does NOT:
  - read Telegram / Pyrogram
  - read raw chunks, index files, or candidates
  - build or read wiki
  - call LLM APIs
  - use vector DB / embeddings / memory-core
  - run OpenClaw doctor/fix/repair
  - touch target project repos

Usage:
    python3 scripts/recover-memory.py --target /path/to/project
    python3 scripts/recover-memory.py --target /path/to/project --topic 7301 --role coder
    python3 scripts/recover-memory.py --target /path/to/project --format text

Exit codes:
    0  — AGENT_CONTEXT.md found (working files may be missing/stale)
    1  — target missing/unreadable or AGENT_CONTEXT.md missing/unreadable
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STALE_DAYS = 7
MAX_FILE_READ = 8_000   # max chars read from any single file
MAX_SECTION_CHARS = 600  # max chars per extracted section in output

REQUIRED_WORKING_FILES = (
    "agent-brief.md",
    "current-state.md",
    "known-issues.md",
)
OPTIONAL_WORKING_FILES = (
    "decisions.md",
    "open-questions.md",
)

# Heading groups for extraction (normalised, lowercase)
_CONTEXT_HEADINGS = frozenset({
    "project", "current objective", "objective", "overview", "summary",
    "agent brief", "brief", "current state", "state",
})
_DONOT_HEADINGS = frozenset({
    "do not do", "do not", "non-goals", "non goals", "forbidden",
    "constraints", "hard constraints", "out of scope",
})
_BLOCKERS_HEADINGS = frozenset({
    "blockers", "current blockers", "known issues", "issues", "problems",
    "blocking", "blocked",
})
_NEXT_HEADINGS = frozenset({
    "next", "next steps", "next useful actions", "next actions",
    "action items", "todo", "to do", "recommendations",
})

# ---------------------------------------------------------------------------
# Staleness helpers
# ---------------------------------------------------------------------------

_LAST_UPDATED_RE = re.compile(
    r"_?[Ll]ast\s+updated:\s*(\d{4}-\d{2}-\d{2})"
)


def _parse_last_updated(text: str) -> Optional[datetime]:
    """Return the first Last-updated date found in the first 2000 chars, or None."""
    m = _LAST_UPDATED_RE.search(text[:2000])
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _is_stale(text: str) -> bool:
    dt = _parse_last_updated(text)
    if dt is None:
        return False  # no date → cannot determine staleness
    return (datetime.now(timezone.utc) - dt) > timedelta(days=STALE_DAYS)


# ---------------------------------------------------------------------------
# File status
# ---------------------------------------------------------------------------

def _file_status(path: Path, optional: bool = False) -> Tuple[str, str]:
    """
    Returns (status_label, content).
    status_label: "OK", "[MISSING]", "optional [MISSING]", "[STALE]"
    """
    if not path.exists():
        return ("optional [MISSING]" if optional else "[MISSING]"), ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_READ]
    except OSError:
        return ("optional [MISSING]" if optional else "[MISSING]"), ""
    if _is_stale(text):
        return "[STALE]", text
    return "OK", text


# ---------------------------------------------------------------------------
# Section extraction (heading-based heuristics, stdlib only)
# ---------------------------------------------------------------------------

def _extract_sections(
    text: str,
    heading_set: frozenset,
    max_chars: int = MAX_SECTION_CHARS,
) -> str:
    """
    Extract content under Markdown headings whose normalised name is in heading_set.
    Returns extracted text, truncated to max_chars.
    """
    lines = text.splitlines()
    in_section = False
    collected: List[str] = []
    total = 0

    for line in lines:
        m = re.match(r"^#{1,4}\s+(.+)$", line)
        if m:
            name = m.group(1).strip().lower().rstrip(":")
            if name in heading_set:
                in_section = True
                continue
            else:
                in_section = False
        if in_section:
            if total + len(line) + 1 >= max_chars:
                budget = max_chars - total
                collected.append(line[:budget] + "…")
                break
            collected.append(line)
            total += len(line) + 1

    return "\n".join(collected).strip()


def _first_n_chars(text: str, n: int = 400) -> str:
    """Fallback: return first n characters, breaking on a newline boundary."""
    stripped = text.strip()
    if len(stripped) <= n:
        return stripped
    return stripped[:n].rsplit("\n", 1)[0] + "\n…"


# ---------------------------------------------------------------------------
# Output builders
# ---------------------------------------------------------------------------

# FileStatus = (rel_path, status_label, content)
FileStatus = Tuple[str, str, str]


def _readable_texts(file_statuses: List[FileStatus]) -> dict:
    """Return {rel_path: content} for files that have content (OK or STALE)."""
    return {
        rel: content
        for rel, status, content in file_statuses
        if content and status in ("OK", "[STALE]")
    }


def _gather_section(all_texts: dict, heading_set: frozenset, context_fallback: bool = False) -> str:
    parts: List[str] = []
    for rel, content in all_texts.items():
        extracted = _extract_sections(content, heading_set)
        if extracted:
            parts.append(extracted)
        elif context_fallback and rel.endswith("agent-brief.md"):
            parts.append(_first_n_chars(content))
    return "\n\n".join(parts)


def _build_markdown(
    file_statuses: List[FileStatus],
    topic: Optional[str],
    role: Optional[str],
) -> str:
    lines: List[str] = ["# Recovered Project Memory", ""]

    if topic or role:
        filters = []
        if topic:
            filters.append(f"topic={topic}")
        if role:
            filters.append(f"role={role}")
        lines += [f"_Filters: {', '.join(filters)}_", ""]

    lines += ["## Loaded files", ""]
    for rel, status, _ in file_statuses:
        lines.append(f"- {rel} — {status}")
    lines.append("")

    all_texts = _readable_texts(file_statuses)

    def _section_md(heading: str, heading_set: frozenset, fallback: bool = False) -> None:
        lines.append(f"## {heading}")
        lines.append("")
        content = _gather_section(all_texts, heading_set, context_fallback=fallback)
        lines.append(content if content else "_(none extracted)_")
        lines.append("")

    _section_md("Startup context", _CONTEXT_HEADINGS, fallback=True)
    _section_md("Do not do", _DONOT_HEADINGS)
    _section_md("Current blockers", _BLOCKERS_HEADINGS)
    _section_md("Next useful actions", _NEXT_HEADINGS)

    lines += [
        "## Notes",
        "",
        "- No Telegram read performed.",
        "- No raw chunks read.",
        "- No vector DB / embeddings / memory-core used.",
        "",
    ]

    return "\n".join(lines)


def _build_text(
    file_statuses: List[FileStatus],
    topic: Optional[str],
    role: Optional[str],
) -> str:
    parts: List[str] = ["=== Recovered Project Memory ===", ""]

    if topic or role:
        filters = []
        if topic:
            filters.append(f"topic={topic}")
        if role:
            filters.append(f"role={role}")
        parts += [f"Filters: {', '.join(filters)}", ""]

    parts.append("Loaded files:")
    for rel, status, _ in file_statuses:
        parts.append(f"  {rel} — {status}")
    parts.append("")

    all_texts = _readable_texts(file_statuses)

    def _section_txt(title: str, heading_set: frozenset, fallback: bool = False) -> None:
        parts.append(f"{title}:")
        content = _gather_section(all_texts, heading_set, context_fallback=fallback)
        parts.append(content if content else "  (none extracted)")
        parts.append("")

    _section_txt("Startup context", _CONTEXT_HEADINGS, fallback=True)
    _section_txt("Do not do", _DONOT_HEADINGS)
    _section_txt("Current blockers", _BLOCKERS_HEADINGS)
    _section_txt("Next useful actions", _NEXT_HEADINGS)

    parts += [
        "Notes:",
        "  No Telegram read performed.",
        "  No raw chunks read.",
        "  No vector DB / embeddings / memory-core used.",
    ]

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def recover(
    target: Path,
    topic: Optional[str] = None,
    role: Optional[str] = None,
    fmt: str = "markdown",
) -> Tuple[int, str]:
    """
    Read memory pack under target and return (exit_code, output_text).
    exit_code 0 → success (AGENT_CONTEXT found); 1 → fatal error.
    """
    # Validate target
    if not target.exists() or not target.is_dir():
        return 1, f"ERROR: target not found or not a directory: {target}"

    # Require AGENT_CONTEXT.md
    context_path = target / ".agent" / "AGENT_CONTEXT.md"
    try:
        context_text = context_path.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_READ]
        context_status = "OK"
    except (OSError, FileNotFoundError):
        return 1, f"ERROR: .agent/AGENT_CONTEXT.md not found or unreadable in {target}"

    # Collect file statuses
    working_dir = target / ".agent" / "memory" / "working"
    file_statuses: List[FileStatus] = []

    file_statuses.append((".agent/AGENT_CONTEXT.md", context_status, context_text))

    for fname in REQUIRED_WORKING_FILES:
        rel = f".agent/memory/working/{fname}"
        status, content = _file_status(working_dir / fname, optional=False)
        file_statuses.append((rel, status, content))

    for fname in OPTIONAL_WORKING_FILES:
        rel = f".agent/memory/working/{fname}"
        status, content = _file_status(working_dir / fname, optional=True)
        file_statuses.append((rel, status, content))

    if fmt == "text":
        output = _build_text(file_statuses, topic, role)
    else:
        output = _build_markdown(file_statuses, topic, role)

    return 0, output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="recover-memory",
        description=(
            "Read compiled Markdown memory pack and print a concise "
            "startup context for a coding/reviewer/infra agent."
        ),
    )
    p.add_argument(
        "--target", required=True,
        help="Path to the target project directory.",
    )
    p.add_argument(
        "--topic", default=None,
        help="Optional topic ID filter (metadata only, not used for file selection).",
    )
    p.add_argument(
        "--role", default=None, choices=["coder", "reviewer", "infra"],
        help="Optional role filter (metadata only).",
    )
    p.add_argument(
        "--format", dest="fmt", default="markdown", choices=["markdown", "text"],
        help="Output format. Default: markdown.",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    target = Path(args.target)
    exit_code, output = recover(target, topic=args.topic, role=args.role, fmt=args.fmt)
    print(output)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
