#!/usr/bin/env python3
"""
manage-candidates.py — L1 Candidate Knowledge manager.

Manages the intermediate candidate layer between raw fact extraction (L1) and
working memory (L2). Each candidate is a YAML entry with a status lifecycle.

Candidate statuses:
  candidate        → freshly extracted, not yet reviewed
  auto-promoted    → meets auto-promotion criteria, written to L2
  needs-approval   → high-risk type, requires human approval before promotion
  approved         → manually approved, written to L2
  rejected         → explicitly discarded
  obsolete         → superseded by a newer candidate on the same topic
  duplicate        → semantically equivalent to an existing L2 fact

Usage:
  python3 manage-candidates.py <topic_id|topic_name> --add <facts-file>
  python3 manage-candidates.py <topic_id|topic_name> --list
  python3 manage-candidates.py <topic_id|topic_name> --promote-auto
  python3 manage-candidates.py <topic_id|topic_name> --approve <candidate-id>
  python3 manage-candidates.py <topic_id|topic_name> --reject <candidate-id>
  python3 manage-candidates.py <topic_id|topic_name> --show <candidate-id>
  python3 manage-candidates.py <topic_id|topic_name> --status

Environment variables:
  OPENCLAW_AGENTS   path to ~/.openclaw/agents/
  OPENCLAW_MEMORY   path to .agent/memory/ (default: .agent/memory relative to cwd)
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    # Minimal YAML fallback — enough for our simple schema
    yaml = None  # type: ignore

DEFAULT_AGENTS_BASE = Path.home() / ".openclaw" / "agents"


# ---------------------------------------------------------------------------
# High-risk fact types that require human approval before L2 promotion
# ---------------------------------------------------------------------------

HIGH_RISK_TYPES = {
    "architecture_decision",
    "process_rule",
    "constraint",
}

AUTO_PROMOTE_TYPES = {
    "fact",
    "person",
    "project_state",
    "preference",
    "resolved_issue",
}


# ---------------------------------------------------------------------------
# Candidate schema helpers
# ---------------------------------------------------------------------------

def candidate_id() -> str:
    return "CAND-" + str(uuid.uuid4())[:8].upper()


def candidates_file(memory_dir: Path, topic_id: str) -> Path:
    cdir = memory_dir / "candidates"
    cdir.mkdir(parents=True, exist_ok=True)
    return cdir / f"topic-{topic_id}-candidates.yaml"


def load_candidates(path: Path) -> list[dict]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if yaml:
        return yaml.safe_load(text) or []
    # Minimal fallback: return raw text wrapped (not parsed)
    return []


def save_candidates(path: Path, candidates: list[dict]) -> None:
    if yaml:
        path.write_text(yaml.dump(candidates, allow_unicode=True, sort_keys=False), encoding="utf-8")
    else:
        # Fallback: write as plain structured text
        lines = []
        for c in candidates:
            lines.append("---")
            for k, v in c.items():
                lines.append(f"{k}: {v!r}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_type(fact: str) -> str:
    """Heuristic type classification from fact text."""
    fact_lower = fact.lower()
    if any(w in fact_lower for w in ("decided", "decision", "chose", "architecture", "design")):
        return "architecture_decision"
    if any(w in fact_lower for w in ("must", "never", "always", "required", "cannot", "constraint")):
        return "constraint"
    if any(w in fact_lower for w in ("rule", "policy", "process", "procedure")):
        return "process_rule"
    if any(w in fact_lower for w in ("prefers", "preference", "likes", "wants")):
        return "preference"
    if any(w in fact_lower for w in ("fixed", "resolved", "solved", "closed", "shipped", "released")):
        return "resolved_issue"
    if any(w in fact_lower for w in ("is ", "are ", "was ", "were ", "has ", "have ")):
        return "fact"
    return "fact"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_add(topic_id: str, facts_source: str, memory_dir: Path, session_id: str) -> None:
    """Read facts from file or stdin, create candidate entries."""
    if facts_source == "-":
        lines = sys.stdin.read().splitlines()
    else:
        lines = Path(facts_source).read_text(encoding="utf-8", errors="replace").splitlines()

    facts = [l.strip() for l in lines if l.strip() and l.strip().startswith("- ")]
    if not facts:
        print("ERROR: no bullet facts found (lines must start with '- ')", file=sys.stderr)
        sys.exit(1)

    cf = candidates_file(memory_dir, topic_id)
    existing = load_candidates(cf)

    added = 0
    for fact in facts:
        fact_type = classify_type(fact)
        c = {
            "id": candidate_id(),
            "created_at": now_iso(),
            "created_by": session_id,
            "topic_id": topic_id,
            "type": fact_type,
            "claim": fact,
            "status": "needs-approval" if fact_type in HIGH_RISK_TYPES else "candidate",
        }
        existing.append(c)
        added += 1
        print(f"  {c['id']} [{fact_type}] {fact[:80]}")

    save_candidates(cf, existing)
    print(f"\nAdded {added} candidates to {cf}")


def cmd_list(topic_id: str, memory_dir: Path) -> None:
    """List all candidates with status."""
    cf = candidates_file(memory_dir, topic_id)
    candidates = load_candidates(cf)
    if not candidates:
        print(f"No candidates for topic {topic_id}")
        return

    by_status: dict[str, list] = {}
    for c in candidates:
        s = c.get("status", "?")
        by_status.setdefault(s, []).append(c)

    print(f"CANDIDATES  [topic:{topic_id}]  total:{len(candidates)}")
    print("=" * 60)
    for status, items in sorted(by_status.items()):
        print(f"\n[{status.upper()}]  ({len(items)})")
        for c in items:
            claim = str(c.get("claim", ""))[:72]
            print(f"  {c['id']}  [{c.get('type','?')}]  {claim}")


def cmd_status(topic_id: str, memory_dir: Path) -> None:
    """Summary stats."""
    cf = candidates_file(memory_dir, topic_id)
    candidates = load_candidates(cf)
    counts: dict[str, int] = {}
    for c in candidates:
        s = c.get("status", "?")
        counts[s] = counts.get(s, 0) + 1
    print(f"CANDIDATE STATUS  [topic:{topic_id}]")
    print(f"  Total: {len(candidates)}")
    for s, n in sorted(counts.items()):
        print(f"  {s:<20}: {n}")
    print(f"  File: {cf}")


def cmd_promote_auto(topic_id: str, memory_dir: Path, agents_base: Path) -> None:
    """Auto-promote candidates that meet criteria → write to L2 memory."""
    cf = candidates_file(memory_dir, topic_id)
    candidates = load_candidates(cf)

    to_promote = [
        c for c in candidates
        if c.get("status") == "candidate" and c.get("type") in AUTO_PROMOTE_TYPES
    ]
    if not to_promote:
        print(f"No auto-promotable candidates (status=candidate, type in {AUTO_PROMOTE_TYPES})")
        return

    # Write facts to L2 via archive-batch-v2
    ab = _import_archive_batch()
    session_id = f"promote-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    facts = [str(c["claim"]) for c in to_promote]
    memory_file = memory_dir / f"topic-{topic_id}.md"

    # Call write_batch_to_memory directly
    existing_content = memory_file.read_text(encoding="utf-8") if memory_file.exists() else ""
    existing_bullets = ab.extract_existing_bullets(existing_content)
    written = ab.write_batch_to_memory(
        memory_file=memory_file,
        topic_id=topic_id,
        batch_n=-1,  # promotion batch
        session_id=session_id,
        facts=facts,
        existing_bullets=existing_bullets,
    )

    # Update statuses
    promoted_ids = {c["id"] for c in to_promote}
    for c in candidates:
        if c["id"] in promoted_ids:
            c["status"] = "auto-promoted"
            c["promoted_at"] = now_iso()
            c["promoted_by"] = session_id

    save_candidates(cf, candidates)
    print(f"Auto-promoted {len(to_promote)} candidates → {written} facts written to {memory_file}")


def cmd_approve(topic_id: str, cand_id: str, memory_dir: Path, agents_base: Path) -> None:
    """Manually approve a candidate → write to L2."""
    cf = candidates_file(memory_dir, topic_id)
    candidates = load_candidates(cf)

    target = next((c for c in candidates if c.get("id") == cand_id), None)
    if not target:
        print(f"ERROR: candidate {cand_id} not found", file=sys.stderr)
        sys.exit(1)

    ab = _import_archive_batch()
    session_id = f"approve-{cand_id}"
    memory_file = memory_dir / f"topic-{topic_id}.md"
    existing_content = memory_file.read_text(encoding="utf-8") if memory_file.exists() else ""
    existing_bullets = ab.extract_existing_bullets(existing_content)
    ab.write_batch_to_memory(
        memory_file=memory_file,
        topic_id=topic_id,
        batch_n=-1,
        session_id=session_id,
        facts=[str(target["claim"])],
        existing_bullets=existing_bullets,
    )

    target["status"] = "approved"
    target["approved_at"] = now_iso()
    save_candidates(cf, candidates)
    print(f"Approved {cand_id} → written to {memory_file}")


def cmd_reject(topic_id: str, cand_id: str, memory_dir: Path) -> None:
    """Mark a candidate as rejected."""
    cf = candidates_file(memory_dir, topic_id)
    candidates = load_candidates(cf)
    target = next((c for c in candidates if c.get("id") == cand_id), None)
    if not target:
        print(f"ERROR: candidate {cand_id} not found", file=sys.stderr)
        sys.exit(1)
    target["status"] = "rejected"
    target["rejected_at"] = now_iso()
    save_candidates(cf, candidates)
    print(f"Rejected {cand_id}: {str(target.get('claim',''))[:80]}")


def cmd_show(topic_id: str, cand_id: str, memory_dir: Path) -> None:
    cf = candidates_file(memory_dir, topic_id)
    candidates = load_candidates(cf)
    target = next((c for c in candidates if c.get("id") == cand_id), None)
    if not target:
        print(f"ERROR: candidate {cand_id} not found", file=sys.stderr)
        sys.exit(1)
    if yaml:
        print(yaml.dump(target, allow_unicode=True, sort_keys=False))
    else:
        for k, v in target.items():
            print(f"{k}: {v}")


# ---------------------------------------------------------------------------
# Import archive-batch-v2 helpers
# ---------------------------------------------------------------------------

def _import_archive_batch():
    script = Path(__file__).parent / "archive-batch-v2.py"
    spec = importlib.util.spec_from_file_location("archive_batch_v2", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="L1 Candidate Knowledge manager — intermediate layer between extraction and L2 memory."
    )
    parser.add_argument("topic", help="Topic ID (numeric) or topic name")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--add", metavar="FACTS_FILE",
                       help="Add candidates from facts file (or '-' for stdin)")
    group.add_argument("--list", action="store_true", help="List all candidates")
    group.add_argument("--status", action="store_true", help="Show summary stats")
    group.add_argument("--promote-auto", action="store_true",
                       help="Auto-promote eligible candidates to L2 memory")
    group.add_argument("--approve", metavar="CANDIDATE_ID",
                       help="Manually approve candidate → write to L2")
    group.add_argument("--reject", metavar="CANDIDATE_ID", help="Reject a candidate")
    group.add_argument("--show", metavar="CANDIDATE_ID", help="Show full candidate details")

    parser.add_argument("--session-id", default=None, help="Session ID for traceability")
    parser.add_argument("--memory-dir", type=Path,
                        default=Path(".agent/memory"),
                        help="Memory directory (default: .agent/memory)")
    parser.add_argument("--agents-base", type=Path, default=DEFAULT_AGENTS_BASE)
    args = parser.parse_args()

    # Resolve topic name
    ab = _import_archive_batch()
    topic_id = ab.resolve_topic_id(args.topic, args.agents_base)

    session_id = args.session_id or f"mgr-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    memory_dir = args.memory_dir

    if args.add:
        cmd_add(topic_id, args.add, memory_dir, session_id)
    elif args.list:
        cmd_list(topic_id, memory_dir)
    elif args.status:
        cmd_status(topic_id, memory_dir)
    elif args.promote_auto:
        cmd_promote_auto(topic_id, memory_dir, args.agents_base)
    elif args.approve:
        cmd_approve(topic_id, args.approve, memory_dir, args.agents_base)
    elif args.reject:
        cmd_reject(topic_id, args.reject, memory_dir)
    elif args.show:
        cmd_show(topic_id, args.show, memory_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
