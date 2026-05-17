#!/usr/bin/env python3
"""
refresh-memory.py — v1 refresh-memory command (single-topic, local input).

Thin wrapper that runs, in sequence:
  1. archive-context.py  — ingest local input into raw chunks
  2. compile-working-memory.py — compile chunks into working/*.md drafts

Default mode is dry-run. Use --write to actually write files.

Does NOT:
  - read Telegram / Pyrogram
  - call LLM APIs
  - use vector DB / embeddings / memory-core
  - run OpenClaw doctor/fix/repair
  - auto-commit or auto-push
  - implement multi-topic orchestration
  - implement --read-topic

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

Exit codes:
    0  — both steps succeeded (or dry-run succeeded)
    1  — validation error, archive step failed, or compile step failed
"""
from __future__ import annotations

import argparse
import importlib.util
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
) -> str:
    raw_dir = f".agent/memory/raw/topic-{topic_id}/"
    warn_lines = "\n".join(f"- {w}" for w in warnings) if warnings else "- none"
    working_lines = "\n".join(
        f"- .agent/memory/working/{f}" for f in WORKING_FILES
    )
    return (
        "REFRESH MEMORY REPORT\n\n"
        f"Mode: {mode}\n"
        f"Target: {target}\n"
        f"Topic: {topic_id}\n"
        f"Role: {role}\n"
        f"Input: {input_path}\n"
        f"Source type: {source_type}\n\n"
        f"Archive step: {archive_status}\n"
        f"Compile step: {compile_status}\n\n"
        f"Raw output:\n- {raw_dir}\n\n"
        f"Working files:\n{working_lines}\n\n"
        f"Warnings:\n{warn_lines}\n\n"
        "Notes:\n"
        "- No Telegram read performed.\n"
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

    if archive_code != 0:
        return 1, _build_report(
            mode, target, topic_id, role, input_path, source_type,
            archive_status, "SKIP", warnings,
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
        "--input", required=True, dest="input_path",
        help="Path to local input file.",
    )
    p.add_argument(
        "--source-type", required=True, dest="source_type",
        choices=sorted(ALLOWED_SOURCE_TYPES),
        help="Input source type.",
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


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    target = Path(args.target)
    input_path = Path(args.input_path)
    notes_path = Path(args.notes) if args.notes else None

    # --dry-run overrides --write
    write = args.write and not args.dry_run

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
