#!/usr/bin/env python3
"""
compile-working-memory.py — v1 working memory compile command.

Reads raw archive chunks and AGENT_CONTEXT.md, then either:
  dry-run (default): prints plan, context packet preview, extraction prompt
  write mode:        writes draft working/*.md files for agent-assisted extraction

Scripts do not call LLM APIs directly.
Extraction is agent-assisted: use the generated context packet + prompt
to populate working/*.md with an agent (OpenClaw or Claude CLI).

Usage (dry-run, default):
    python3 scripts/compile-working-memory.py \\
        --target /path/to/project \\
        --topics 7301:coder,13350:reviewer \\
        --dry-run

Usage (write mode):
    python3 scripts/compile-working-memory.py \\
        --target /path/to/project \\
        --topics 7301:coder,13350:reviewer \\
        --write
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WORKING_FILES = ("agent-brief.md", "current-state.md", "known-issues.md")
ALLOWED_ROLES = ("coder", "reviewer", "infra", "unknown")
# Directories inside .agent/memory/ that the compile step must never touch
FORBIDDEN_MEMORY_DIRS = ("index", "candidates", "wiki")
# Maximum characters in the bounded context packet
MAX_CONTEXT_CHARS = 32_000
# Maximum characters read from any single ancillary file
MAX_FILE_READ = 16_000

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class TopicSpec(NamedTuple):
    topic_id: str
    role: str


class ChunkInfo(NamedTuple):
    path: Path
    topic_id: str
    role: str
    char_count: int
    has_redactions: bool


class CompileInputs(NamedTuple):
    agent_context: str       # content of AGENT_CONTEXT.md, or ""
    topics: list             # list[TopicSpec]
    chunks: list             # list[ChunkInfo]
    notes: str               # content of --notes file, or ""
    existing_working: dict   # filename -> content for existing working/*.md


# ---------------------------------------------------------------------------
# Topic spec parsing
# ---------------------------------------------------------------------------


def parse_topics(topics_str: str) -> list:
    """Parse '7301:coder,13350:reviewer' into list[TopicSpec]."""
    specs = []
    for item in topics_str.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(
                f"invalid topic spec (expected <id>:<role>): {item!r}"
            )
        topic_id, role = item.split(":", 1)
        topic_id = topic_id.strip()
        role = role.strip()
        if not topic_id:
            raise ValueError(f"empty topic id in: {item!r}")
        if role not in ALLOWED_ROLES:
            raise ValueError(
                f"invalid role {role!r} in {item!r}; allowed: {ALLOWED_ROLES}"
            )
        specs.append(TopicSpec(topic_id=topic_id, role=role))
    if not specs:
        raise ValueError("no topic specs parsed from --topics")
    return specs


# ---------------------------------------------------------------------------
# Input collection
# ---------------------------------------------------------------------------


def scan_chunks(target: Path, topic_id: str, role: str) -> list:
    """Return sorted ChunkInfo list for one topic."""
    raw_dir = target / ".agent" / "memory" / "raw" / f"topic-{topic_id}"
    if not raw_dir.is_dir():
        return []
    chunks = []
    for path in sorted(raw_dir.glob("chunk-*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        chunks.append(ChunkInfo(
            path=path,
            topic_id=topic_id,
            role=role,
            char_count=len(text),
            has_redactions="[REDACTED:" in text,
        ))
    return chunks


def safe_read(path: Path, max_chars: int = MAX_FILE_READ) -> str:
    """Read a file safely, truncating to max_chars."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[truncated at {max_chars} chars]"
        return text
    except OSError:
        return ""


def collect_inputs(
    target: Path, topics: list, notes_path: "Path | None"
) -> CompileInputs:
    """Collect all allowed inputs from disk."""
    agent_context_path = target / ".agent" / "AGENT_CONTEXT.md"
    agent_context = (
        safe_read(agent_context_path) if agent_context_path.is_file() else ""
    )

    all_chunks: list = []
    for spec in topics:
        all_chunks.extend(scan_chunks(target, spec.topic_id, spec.role))

    notes = ""
    if notes_path is not None:
        notes = safe_read(notes_path)

    existing_working: dict = {}
    working_dir = target / ".agent" / "memory" / "working"
    if working_dir.is_dir():
        for fname in WORKING_FILES:
            fpath = working_dir / fname
            if fpath.is_file():
                existing_working[fname] = safe_read(fpath)

    return CompileInputs(
        agent_context=agent_context,
        topics=topics,
        chunks=all_chunks,
        notes=notes,
        existing_working=existing_working,
    )


# ---------------------------------------------------------------------------
# Bounded context packet
# ---------------------------------------------------------------------------


def build_context_packet(
    chunks: list, max_chars: int = MAX_CONTEXT_CHARS
) -> str:
    """Concatenate chunk content up to max_chars with per-chunk headers."""
    parts: list = []
    total = 0
    for i, info in enumerate(chunks):
        header = (
            f"\n\n--- {info.path.name}"
            f" (topic-{info.topic_id}, {info.role}) ---\n"
        )
        try:
            body = info.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            body = "[unreadable]"
        entry = header + body
        if total + len(entry) > max_chars:
            remaining = max_chars - total
            if remaining > len(header) + 40:
                entry = header + body[: remaining - len(header)]
                entry += "\n[truncated]"
                parts.append(entry)
            omitted = len(chunks) - i
            parts.append(
                f"\n\n[context limit reached — {omitted} chunk(s) omitted]"
            )
            break
        parts.append(entry)
        total += len(entry)
    return "".join(parts) if parts else "[no chunks available]"


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

_EXTRACTION_PROMPT_TMPL = """\
You are a memory extraction agent. Using the context packet below, fill in the
three working memory draft files for this project. Follow these rules:

1. Each fact must be traceable to a source chunk or AGENT_CONTEXT.md.
2. Label facts: confirmed | inferred | stale | needs_review.
3. Do not include raw secrets. Mention [REDACTED:*] at category level only.
4. Keep each file short and dense. No padding, no prose.
5. Replace all <!-- TODO --> placeholders with real content.

Files to produce:
- agent-brief.md: project identity, repo, active topics/roles, objective,
  do-not-do rules, startup load order, next useful actions.
- current-state.md: last updated, active branch, recent completed work,
  in-progress work, blockers, relevant PRs/commits.
- known-issues.md: per-issue — description, severity, status, source, next action.

Source topics: {topics}
AGENT_CONTEXT present: {has_agent_context}
Operator notes present: {has_notes}
Redacted chunks: {redacted_count} (handle with care — do not reconstruct secrets)
"""


def build_extraction_prompt(
    topics: list,
    has_agent_context: bool,
    has_notes: bool,
    redacted_count: int,
) -> str:
    topics_str = ", ".join(f"{s.topic_id}:{s.role}" for s in topics)
    return _EXTRACTION_PROMPT_TMPL.format(
        topics=topics_str,
        has_agent_context="yes" if has_agent_context else "no",
        has_notes="yes" if has_notes else "no",
        redacted_count=redacted_count,
    )


# ---------------------------------------------------------------------------
# Draft templates
# ---------------------------------------------------------------------------

_AGENT_BRIEF_TMPL = """\
---
draft: true
compiled_at: "{compiled_at}"
topics: [{topics}]
sources: {source_count} chunk(s)
---

<!-- AGENT: fill in the sections below using the context packet at the bottom -->

# Agent Brief

## Project identity
<!-- TODO: project name, purpose, primary stakeholders -->

## Repository
<!-- TODO: repo path, repo URL -->

## Active topics and roles
<!-- TODO: from AGENT_CONTEXT.md -->

## Current objective
<!-- TODO -->

## Do-not-do rules
<!-- TODO: what this agent must never do -->

## Memory load order
1. `.agent/AGENT_CONTEXT.md`
2. `working/agent-brief.md`
3. `working/current-state.md`
4. `working/known-issues.md`

## Next useful actions
<!-- TODO: what a new agent should do first -->
"""

_CURRENT_STATE_TMPL = """\
---
draft: true
compiled_at: "{compiled_at}"
topics: [{topics}]
---

<!-- AGENT: fill in the sections below using the context packet in agent-brief.md -->

# Current State

## Last updated
{compiled_at}

## Active branch / repo status
<!-- TODO: [stale] unless freshly verified -->

## Recent completed work
<!-- TODO: list with source references, e.g. (raw/topic-7301/chunk-0003.md) -->

## In-progress work
<!-- TODO -->

## Current blockers
<!-- TODO -->

## Relevant PRs / commits
<!-- TODO -->
"""

_KNOWN_ISSUES_TMPL = """\
---
draft: true
compiled_at: "{compiled_at}"
topics: [{topics}]
---

<!-- AGENT: fill in the sections below using the context packet in agent-brief.md -->
<!-- Format per issue:
## <issue title>
- severity: high | medium | low
- status: open | resolved | mitigated
- source: <chunk path or AGENT_CONTEXT>
- next action: <what to do>
- do-not-do: <if relevant>
-->

# Known Issues

## No issues extracted yet
- severity: low
- status: open
- source: draft template
- next action: extract from context packet in agent-brief.md
"""

_CONTEXT_PACKET_SECTION = """
---

<!-- CONTEXT PACKET — do not edit below this line                              -->
<!-- Bounded context from raw chunks for agent-assisted extraction.            -->
<!-- compile-working-memory.py does not call LLM APIs.                        -->
<!-- Use the extraction prompt and raw context below to populate working/*.md. -->

## Extraction prompt

{extraction_prompt}

## Raw context

{context_packet}
"""

_DRAFT_TEMPLATES = {
    "agent-brief.md": _AGENT_BRIEF_TMPL,
    "current-state.md": _CURRENT_STATE_TMPL,
    "known-issues.md": _KNOWN_ISSUES_TMPL,
}


def build_draft(
    filename: str,
    compiled_at: str,
    topics: list,
    source_count: int,
    extraction_prompt: str,
    context_packet: str,
) -> str:
    """Build draft content for a working memory file."""
    topics_str = ", ".join(f"{s.topic_id}:{s.role}" for s in topics)
    tmpl = _DRAFT_TEMPLATES[filename]
    header = tmpl.format(
        compiled_at=compiled_at,
        topics=topics_str,
        source_count=source_count,
    )
    # Embed context packet only in agent-brief.md to avoid duplication
    if filename == "agent-brief.md":
        footer = _CONTEXT_PACKET_SECTION.format(
            extraction_prompt=extraction_prompt,
            context_packet=context_packet,
        )
        return header + footer
    return header


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------


def collect_warnings(inputs: CompileInputs) -> list:
    warnings = []
    if not inputs.agent_context:
        warnings.append(
            "AGENT_CONTEXT.md not found — agent-brief.md will be incomplete"
        )
    if not inputs.chunks:
        warnings.append(
            "no raw chunks found for any topic — output will be empty templates"
        )
    redacted = [c for c in inputs.chunks if c.has_redactions]
    if redacted:
        warnings.append(
            f"{len(redacted)} chunk(s) contain redacted content — "
            "review before using for detailed extraction"
        )
    for fname in WORKING_FILES:
        if fname in inputs.existing_working:
            warnings.append(f"existing {fname} will be overwritten in write mode")
    return warnings


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def format_dry_run_report(
    *,
    target: Path,
    inputs: CompileInputs,
    warnings: list,
    context_packet: str,
    extraction_prompt: str,
    compiled_at: str,
) -> str:
    topics_str = ", ".join(f"{s.topic_id}:{s.role}" for s in inputs.topics)
    chunk_by_topic: dict = {}
    redacted_by_topic: dict = {}
    for c in inputs.chunks:
        chunk_by_topic[c.topic_id] = chunk_by_topic.get(c.topic_id, 0) + 1
        if c.has_redactions:
            redacted_by_topic[c.topic_id] = redacted_by_topic.get(c.topic_id, 0) + 1

    lines = [
        "=== compile-working-memory dry-run ===",
        f"target:      {target}",
        f"topics:      {topics_str}",
        f"compiled_at: {compiled_at}",
        "",
        "Chunk summary:",
    ]
    for spec in inputs.topics:
        n = chunk_by_topic.get(spec.topic_id, 0)
        r = redacted_by_topic.get(spec.topic_id, 0)
        redact_note = f", {r} redacted" if r else ""
        lines.append(
            f"  topic-{spec.topic_id} ({spec.role}): {n} chunk(s){redact_note}"
        )

    working_dir = target / ".agent" / "memory" / "working"
    lines += [
        "",
        f"AGENT_CONTEXT.md: {'found' if inputs.agent_context else 'NOT FOUND'}",
        f"operator notes:   {'found' if inputs.notes else 'not provided'}",
        f"existing working: {list(inputs.existing_working.keys()) or 'none'}",
        "",
        "Planned output files (not written — dry-run):",
    ]
    for fname in WORKING_FILES:
        lines.append(f"  {working_dir / fname}")

    if warnings:
        lines += ["", "Warnings:"]
        for w in warnings:
            lines.append(f"  \u26a0 {w}")

    preview = context_packet[:500] + ("..." if len(context_packet) > 500 else "")
    lines += [
        "",
        "Context packet preview (first 500 chars):",
        preview,
        "",
        "Extraction prompt:",
        extraction_prompt.strip(),
        "",
        "(pass --write to write draft working/*.md to disk)",
    ]
    return "\n".join(lines)


def format_write_report(
    *,
    working_dir: Path,
    written: list,
    warnings: list,
) -> str:
    lines = [
        "=== compile-working-memory write ===",
        f"output dir:    {working_dir}",
        f"files written: {len(written)}",
    ]
    for p in written:
        lines.append(f"  {p}")
    if warnings:
        lines += ["", "Warnings:"]
        for w in warnings:
            lines.append(f"  \u26a0 {w}")
    lines += [
        "",
        "Next step: review the draft files, then run your agent with the",
        "context packet + extraction prompt in agent-brief.md to populate",
        "working/*.md.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="compile-working-memory",
        description="Compile raw archive chunks into working memory draft files (v1).",
    )
    p.add_argument("--target", required=True,
                   help="Path to target project repo root")
    p.add_argument("--topics", required=True,
                   help="Comma-separated topic:role pairs, e.g. 7301:coder,13350:reviewer")
    p.add_argument("--notes", default=None, dest="notes_path",
                   help="Optional operator notes file")
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="Show plan and context packet; do not write files")
    p.add_argument("--write", action="store_true",
                   help="Write draft working/*.md files to disk")
    return p


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: "list[str] | None" = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Dry-run is the default when --write is absent
    if not args.write:
        args.dry_run = True

    target = Path(args.target)
    if not target.is_dir():
        print(
            f"ERROR: --target does not exist or is not a directory: {target}",
            file=sys.stderr,
        )
        return 1

    notes_path: "Path | None" = None
    if args.notes_path:
        notes_path = Path(args.notes_path)
        if not notes_path.is_file():
            print(
                f"ERROR: --notes file does not exist: {notes_path}",
                file=sys.stderr,
            )
            return 1

    try:
        topics = parse_topics(args.topics)
    except ValueError as e:
        print(f"ERROR: --topics: {e}", file=sys.stderr)
        return 1

    compiled_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inputs = collect_inputs(target, topics, notes_path)
    warnings = collect_warnings(inputs)
    redacted_count = sum(1 for c in inputs.chunks if c.has_redactions)
    context_packet = build_context_packet(inputs.chunks)
    extraction_prompt = build_extraction_prompt(
        topics=inputs.topics,
        has_agent_context=bool(inputs.agent_context),
        has_notes=bool(inputs.notes),
        redacted_count=redacted_count,
    )

    if not args.write:
        print(format_dry_run_report(
            target=target,
            inputs=inputs,
            warnings=warnings,
            context_packet=context_packet,
            extraction_prompt=extraction_prompt,
            compiled_at=compiled_at,
        ))
        return 0

    # Write mode — only .agent/memory/working/*.md
    working_dir = target / ".agent" / "memory" / "working"
    working_dir.mkdir(parents=True, exist_ok=True)
    written: list = []
    for fname in WORKING_FILES:
        draft = build_draft(
            filename=fname,
            compiled_at=compiled_at,
            topics=inputs.topics,
            source_count=len(inputs.chunks),
            extraction_prompt=extraction_prompt,
            context_packet=context_packet,
        )
        out_path = working_dir / fname
        out_path.write_text(draft, encoding="utf-8")
        written.append(out_path)

    print(format_write_report(
        working_dir=working_dir,
        written=written,
        warnings=warnings,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
