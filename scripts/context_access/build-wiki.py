#!/usr/bin/env python3
"""
build-wiki.py — L3 Shared Knowledge Vault builder.

Reads all memory/topic-<id>.md files and generates a cross-referenced,
searchable wiki in memory/wiki/. Neutral — no agent-specific logic.

Usage:
  python3 build-wiki.py --memory-dir .agent/memory
  python3 build-wiki.py --memory-dir .agent/memory --clean
  python3 build-wiki.py --memory-dir .agent/memory --topic 7301

Output:
  memory/wiki/index.md          — master index with all topics + stats
  memory/wiki/topic-<id>.md     — per-topic wiki page (clean facts only)
  memory/wiki/by-type/          — facts grouped by type (decisions, constraints, etc.)
  memory/wiki/WIKI_META.json    — build metadata (last-built, topic count, fact count)

Environment variables:
  OPENCLAW_AGENTS   path to ~/.openclaw/agents/ (for topic name resolution)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_AGENTS_BASE = Path.home() / ".openclaw" / "agents"


# ---------------------------------------------------------------------------
# Fact extraction from memory file
# ---------------------------------------------------------------------------

def extract_facts(content: str) -> list[dict]:
    """Extract clean facts from topic-<id>.md content.

    Returns list of {text, batch_n, is_conflict} dicts.
    Skips ⚠️ CONFLICT annotation lines (keeps the main fact).
    """
    facts = []
    current_batch = -1
    batch_re = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\] Batch (\d+)")
    compact_re = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\] Batch -1")  # promotion batches

    for line in content.splitlines():
        bm = batch_re.match(line)
        if bm:
            current_batch = int(bm.group(2))
            continue
        if compact_re.match(line):
            current_batch = -1
            continue

        stripped = line.strip()
        if stripped.startswith("- ⚠️"):
            continue  # skip conflict annotations
        if stripped.startswith("- "):
            facts.append({
                "text": stripped,
                "batch_n": current_batch,
                "is_conflict": False,
            })

    return facts


def classify_fact(text: str) -> str:
    """Classify fact into wiki section."""
    t = text.lower()
    if any(w in t for w in ("decided", "decision", "chose", "architecture", "design pattern")):
        return "decisions"
    if any(w in t for w in ("must", "never", "always", "required", "cannot", "constraint")):
        return "constraints"
    if any(w in t for w in ("rule", "policy", "process", "procedure", "workflow")):
        return "process"
    if any(w in t for w in ("shipped", "released", "fixed", "resolved", "deployed")):
        return "resolved"
    if any(w in t for w in ("prefers", "preference", "likes", "wants", "style")):
        return "preferences"
    if any(w in t for w in ("blocker", "blocked", "pending", "waiting", "issue", "bug")):
        return "blockers"
    return "general"


def parse_memory_header(content: str) -> dict:
    """Extract metadata from <!-- last-batch: N | last-write: TS | ... --> header."""
    m = re.search(r"<!--\s*(.+?)\s*-->", content)
    if not m:
        return {}
    meta = {}
    for part in m.group(1).split("|"):
        kv = part.strip().split(":", 1)
        if len(kv) == 2:
            meta[kv[0].strip()] = kv[1].strip()
    return meta


def topic_name_from_file(path: Path) -> str:
    """Extract topic name from first heading in file."""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


# ---------------------------------------------------------------------------
# Wiki page builders
# ---------------------------------------------------------------------------

def build_topic_page(topic_id: str, memory_file: Path, wiki_dir: Path) -> dict:
    """Build wiki/topic-<id>.md from memory file. Returns stats."""
    content = memory_file.read_text(encoding="utf-8", errors="replace")
    header = parse_memory_header(content)
    facts = extract_facts(content)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    last_write = header.get("last-write", "unknown")
    title = topic_name_from_file(memory_file)

    # Group facts by type
    by_type: dict[str, list[str]] = {}
    for f in facts:
        t = classify_fact(f["text"])
        by_type.setdefault(t, []).append(f["text"])

    lines = [
        f"# {title}",
        f"",
        f"> Topic ID: `{topic_id}` | Last memory write: `{last_write}` | Facts: {len(facts)}",
        f"> Wiki built: `{now_str}`",
        f"",
    ]

    # ordered sections
    section_order = ["decisions", "constraints", "process", "preferences", "resolved", "blockers", "general"]
    section_titles = {
        "decisions": "## Decisions & Architecture",
        "constraints": "## Constraints",
        "process": "## Process & Rules",
        "preferences": "## Preferences",
        "resolved": "## Resolved Issues",
        "blockers": "## Blockers",
        "general": "## General Facts",
    }

    for section in section_order:
        if section in by_type:
            lines.append(section_titles[section])
            lines.append("")
            for fact in by_type[section]:
                lines.append(fact)
            lines.append("")

    wiki_file = wiki_dir / f"topic-{topic_id}.md"
    wiki_file.write_text("\n".join(lines), encoding="utf-8")

    return {
        "topic_id": topic_id,
        "title": title,
        "fact_count": len(facts),
        "last_write": last_write,
        "wiki_file": str(wiki_file),
        "by_type": {k: len(v) for k, v in by_type.items()},
    }


def build_by_type_pages(all_facts_by_type: dict[str, list[dict]], wiki_dir: Path) -> None:
    """Build wiki/by-type/<type>.md pages aggregating facts across all topics."""
    type_dir = wiki_dir / "by-type"
    type_dir.mkdir(exist_ok=True)

    section_titles = {
        "decisions": "Architecture Decisions",
        "constraints": "Constraints",
        "process": "Process & Rules",
        "preferences": "Preferences",
        "resolved": "Resolved Issues",
        "blockers": "Blockers",
        "general": "General Facts",
    }

    for fact_type, entries in all_facts_by_type.items():
        title = section_titles.get(fact_type, fact_type.title())
        lines = [
            f"# {title}",
            f"",
            f"> {len(entries)} facts across {len({e['topic_id'] for e in entries})} topics",
            f"",
        ]

        # Group by topic
        by_topic: dict[str, list[str]] = {}
        for e in entries:
            by_topic.setdefault(e["topic_id"], []).append(e["text"])

        for tid, tfacts in sorted(by_topic.items()):
            lines.append(f"## Topic {tid}")
            lines.append("")
            for f in tfacts:
                lines.append(f)
            lines.append("")

        (type_dir / f"{fact_type}.md").write_text("\n".join(lines), encoding="utf-8")


def build_index(topic_stats: list[dict], wiki_dir: Path) -> None:
    """Build wiki/index.md — master index."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    total_facts = sum(s["fact_count"] for s in topic_stats)

    lines = [
        "# Knowledge Vault — Index",
        "",
        f"> Built: `{now_str}` | Topics: {len(topic_stats)} | Total facts: {total_facts}",
        "",
        "## Topics",
        "",
        "| Topic ID | Title | Facts | Last Write | Wiki Page |",
        "|----------|-------|-------|------------|-----------|",
    ]

    for s in sorted(topic_stats, key=lambda x: x["topic_id"]):
        wiki_link = f"[view](topic-{s['topic_id']}.md)"
        lines.append(
            f"| `{s['topic_id']}` | {s['title']} | {s['fact_count']} | `{s['last_write']}` | {wiki_link} |"
        )

    lines += [
        "",
        "## By Type",
        "",
    ]

    type_dir = wiki_dir / "by-type"
    if type_dir.exists():
        for tf in sorted(type_dir.glob("*.md")):
            lines.append(f"- [{tf.stem.replace('-', ' ').title()}](by-type/{tf.name})")
    lines.append("")

    (wiki_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="L3 Knowledge Vault builder — generates cross-referenced wiki from memory files."
    )
    parser.add_argument("--memory-dir", type=Path, default=Path(".agent/memory"),
                        help="Memory directory (default: .agent/memory)")
    parser.add_argument("--topic", default=None,
                        help="Build wiki for single topic only (numeric ID or name)")
    parser.add_argument("--clean", action="store_true",
                        help="Remove wiki/ directory before rebuilding")
    parser.add_argument("--agents-base", type=Path, default=DEFAULT_AGENTS_BASE)
    args = parser.parse_args()

    memory_dir = args.memory_dir
    if not memory_dir.exists():
        raise SystemExit(f"ERROR: memory directory not found: {memory_dir}")

    wiki_dir = memory_dir / "wiki"

    if args.clean and wiki_dir.exists():
        import shutil
        shutil.rmtree(wiki_dir)
        print(f"Cleaned {wiki_dir}")

    wiki_dir.mkdir(parents=True, exist_ok=True)

    # Find memory files
    if args.topic:
        # Resolve topic name if needed
        ab_script = Path(__file__).parent / "archive-batch-v2.py"
        if ab_script.exists():
            spec = importlib.util.spec_from_file_location("archive_batch_v2", ab_script)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            topic_id = mod.resolve_topic_id(args.topic, args.agents_base)
        else:
            topic_id = args.topic
        memory_files = [memory_dir / f"topic-{topic_id}.md"]
        memory_files = [f for f in memory_files if f.exists()]
    else:
        memory_files = sorted(memory_dir.glob("topic-*.md"))

    if not memory_files:
        print("No memory files found. Run archive-batch-v2.py --write first.")
        return 0

    print(f"Building wiki from {len(memory_files)} memory file(s)...")

    topic_stats = []
    all_facts_by_type: dict[str, list[dict]] = {}

    for mf in memory_files:
        # Extract topic ID from filename
        m = re.match(r"topic-(\d+)\.md", mf.name)
        if not m:
            continue
        tid = m.group(1)

        try:
            stats = build_topic_page(tid, mf, wiki_dir)
            topic_stats.append(stats)

            # Collect for by-type pages
            content = mf.read_text(encoding="utf-8", errors="replace")
            facts = extract_facts(content)
            for f in facts:
                ft = classify_fact(f["text"])
                all_facts_by_type.setdefault(ft, []).append({
                    "topic_id": tid,
                    "text": f["text"],
                })

            print(f"  topic-{tid}: {stats['fact_count']} facts → {stats['wiki_file']}")
        except Exception as e:
            print(f"  ERROR topic-{tid}: {e}", file=sys.stderr)

    build_by_type_pages(all_facts_by_type, wiki_dir)
    build_index(topic_stats, wiki_dir)

    # Write WIKI_META.json
    meta = {
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "topic_count": len(topic_stats),
        "total_facts": sum(s["fact_count"] for s in topic_stats),
        "topics": topic_stats,
    }
    (wiki_dir / "WIKI_META.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nWiki built:")
    print(f"  Topics:      {len(topic_stats)}")
    print(f"  Total facts: {sum(s['fact_count'] for s in topic_stats)}")
    print(f"  Index:       {wiki_dir / 'index.md'}")
    print(f"  By-type:     {wiki_dir / 'by-type/'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
