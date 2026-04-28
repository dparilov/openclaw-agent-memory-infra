#!/usr/bin/env python3
"""
validate-wiki.py — Pre-live integrity checker for L3 Knowledge Vault.

Usage:
  python3 validate-wiki.py --memory-dir .agent/memory
  python3 validate-wiki.py --memory-dir .agent/memory --json
  python3 validate-wiki.py --memory-dir .agent/memory --strict
  python3 validate-wiki.py --memory-dir .agent/memory --write-report PATH

Exit codes:
  0  no errors (warnings only, or none)
  1  errors present (or warnings with --strict)
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

ERROR = "error"
WARN  = "warning"
OK    = "ok"

class Finding:
    def __init__(self, level, code, message):
        self.level = level; self.code = code; self.message = message
    def as_dict(self): return {"level": self.level, "code": self.code, "message": self.message}
    def __repr__(self):
        sym = {"error": "✗", "warning": "⚠", "ok": "✓"}.get(self.level, "?")
        return f"  [{sym}] {self.message}"

def _sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""): h.update(chunk)
    return h.hexdigest()

def _parse_iso(ts):
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try: return datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc)
        except ValueError: pass
    return None

def check_meta_exists(wiki_dir, findings):
    p = wiki_dir / "WIKI_META.json"
    if not p.exists():
        findings.append(Finding(ERROR, "meta_missing", f"WIKI_META.json not found: {p}")); return None
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        findings.append(Finding(ERROR, "meta_invalid_json", f"WIKI_META.json not valid JSON: {e}")); return None

def check_schema_version(meta, findings):
    ver = meta.get("wiki_schema_version")
    if ver is None: findings.append(Finding(ERROR, "schema_version_missing", "WIKI_META missing 'wiki_schema_version'"))
    elif not isinstance(ver, int) or ver < 2: findings.append(Finding(ERROR, "schema_version_low", f"wiki_schema_version={ver!r}, expected int >= 2"))

def check_source_files_structure(meta, findings):
    sf = meta.get("source_files")
    if sf is None: findings.append(Finding(ERROR, "source_files_missing", "WIKI_META missing 'source_files'")); return
    if not isinstance(sf, list): findings.append(Finding(ERROR, "source_files_not_list", "'source_files' is not a list")); return
    req = {"path", "topic_id", "fact_count", "last_batch"}
    for i, e in enumerate(sf):
        if not isinstance(e, dict): findings.append(Finding(ERROR, "source_files_entry_not_dict", f"source_files[{i}] not an object")); continue
        miss = req - e.keys()
        if miss: findings.append(Finding(ERROR, "source_files_entry_missing_keys", f"source_files[{i}] missing: {sorted(miss)}"))

def check_facts_structure(meta, findings):
    facts = meta.get("facts")
    if facts is None: findings.append(Finding(ERROR, "facts_missing", "WIKI_META missing 'facts'")); return []
    if not isinstance(facts, list): findings.append(Finding(ERROR, "facts_not_list", "'facts' not a list")); return []
    req = {"id","text","topic_id","source_file","line_number","batch_n","batch_date","session_id","is_conflict","fact_type"}
    bad = []
    for i, f in enumerate(facts):
        if not isinstance(f, dict): findings.append(Finding(ERROR, "fact_not_dict", f"facts[{i}] not a dict")); bad.append(i); continue
        miss = req - f.keys()
        if miss: findings.append(Finding(ERROR, "fact_missing_fields", f"facts[{i}] id={f.get('id','?')!r} missing: {sorted(miss)}"))
    return [f for i, f in enumerate(facts) if i not in bad]

def check_source_files_exist(meta, memory_dir, findings):
    resolved = {}
    for e in meta.get("source_files", []):
        sp = e.get("path", "")
        c = memory_dir.parent / sp
        if not c.exists():
            c2 = Path(sp)
            if c2.exists(): c = c2
            else: findings.append(Finding(ERROR, "source_file_missing", f"source file not found: {sp!r}")); continue
        resolved[sp] = c
    return resolved

def check_line_numbers(facts, resolved, findings):
    lc = {}
    for sp, rp in resolved.items():
        try: lc[sp] = sum(1 for _ in rp.open(encoding="utf-8", errors="replace"))
        except: lc[sp] = 0
    for f in facts:
        sp = f.get("source_file", ""); ln = f.get("line_number")
        if sp not in lc: continue
        if not isinstance(ln, int) or ln < 1:
            findings.append(Finding(ERROR, "line_number_invalid", f"fact {f.get('id','?')!r}: line_number={ln!r} invalid"))
        elif ln > lc[sp]:
            findings.append(Finding(ERROR, "line_number_out_of_range", f"fact {f.get('id','?')!r}: line_number={ln} > file lines={lc[sp]}"))

def check_fact_text_at_line(facts, resolved, findings):
    fl = {}
    for sp, rp in resolved.items():
        try: fl[sp] = rp.read_text(encoding="utf-8", errors="replace").splitlines()
        except: fl[sp] = []
    for f in facts:
        sp = f.get("source_file", ""); ln = f.get("line_number"); text = f.get("text", "")
        if sp not in fl or not isinstance(ln, int): continue
        lines = fl[sp]; window = range(max(0, ln-3), min(len(lines), ln+2))
        if not any(text in lines[i] for i in window):
            findings.append(Finding(WARN, "fact_text_not_near_line", f"fact {f.get('id','?')!r}: text not near line {ln} in {sp!r}"))

def check_fact_count_consistency(meta, facts, findings):
    actual = {}
    for f in facts: sp = f.get("source_file",""); actual[sp] = actual.get(sp, 0)+1
    for e in meta.get("source_files", []):
        sp = e.get("path",""); d = e.get("fact_count", 0); r = actual.get(sp, 0)
        if d != r: findings.append(Finding(ERROR, "fact_count_mismatch", f"source_files path={sp!r}: fact_count={d} but {r} found"))

def check_conflict_facts_count(meta, facts, findings):
    d = meta.get("conflict_facts")
    if d is None: findings.append(Finding(WARN, "conflict_facts_missing", "WIKI_META missing 'conflict_facts'")); return
    actual = sum(1 for f in facts if f.get("is_conflict"))
    if d != actual: findings.append(Finding(ERROR, "conflict_facts_mismatch", f"conflict_facts={d} but {actual} found"))

def check_per_topic_last_batch(meta, facts, findings):
    pt = meta.get("per_topic_last_batch")
    if pt is None: findings.append(Finding(WARN, "per_topic_last_batch_missing", "WIKI_META missing 'per_topic_last_batch'")); return
    actual = {}
    for f in facts:
        tid = f.get("topic_id",""); bn = f.get("batch_n")
        if bn is None: actual.setdefault(tid, None)
        else:
            prev = actual.get(tid); actual[tid] = max(prev, bn) if prev is not None else bn
    for tid, db in pt.items():
        if tid not in actual: continue  # ghost topic — no facts in index, skip
        real = actual.get(tid)
        if db != real: findings.append(Finding(ERROR, "per_topic_last_batch_mismatch", f"per_topic_last_batch[{tid!r}]={db!r} but computed={real!r}"))

def check_topic_pages_exist(meta, wiki_dir, findings):
    for e in meta.get("source_files", []):
        tid = e.get("topic_id",""); p = wiki_dir / f"topic-{tid}.md"
        if not p.exists(): findings.append(Finding(ERROR, "topic_page_missing", f"wiki page missing for topic {tid!r}: {p}"))

def check_by_type_pages_exist(meta, wiki_dir, findings):
    facts = meta.get("facts", [])
    used = {f.get("fact_type","") for f in facts if f.get("fact_type")}
    td = wiki_dir / "by-type"
    for ft in sorted(used):
        p = td / f"{ft}.md"
        if not p.exists(): findings.append(Finding(ERROR, "by_type_page_missing", f"by-type page missing: {p}"))

def check_sha256_freshness(meta, resolved, findings):
    for e in meta.get("source_files", []):
        sp = e.get("path",""); rs = e.get("sha256")
        if rs is None: continue
        rp = resolved.get(sp)
        if rp is None: continue
        if _sha256(rp) != rs: findings.append(Finding(WARN, "source_sha256_mismatch", f"source {sp!r}: sha256 changed (wiki stale)"))

def check_mtime_freshness(meta, resolved, findings):
    ba_str = meta.get("built_at","")
    ba = _parse_iso(ba_str) if ba_str else None
    if ba is None: return
    for e in meta.get("source_files", []):
        sp = e.get("path",""); rp = resolved.get(sp)
        if rp is None: continue
        try: mtime = datetime.fromtimestamp(rp.stat().st_mtime, tz=timezone.utc)
        except: continue
        if mtime > ba: findings.append(Finding(WARN, "source_mtime_newer", f"source {sp!r}: mtime newer than built_at {ba_str}"))

def write_report(report_path, findings, memory_dir):
    errors = [f for f in findings if f.level==ERROR]; warnings = [f for f in findings if f.level==WARN]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = ["# Wiki Audit Report","",f"> Generated: `{now}` | memory-dir: `{memory_dir}`",
             f"> Errors: {len(errors)} | Warnings: {len(warnings)}",""]
    if errors:
        lines += ["## Errors",""]
        for f in errors: lines.append(f"- **[{f.code}]** {f.message}")
        lines.append("")
    if warnings:
        lines += ["## Warnings",""]
        for f in warnings: lines.append(f"- **[{f.code}]** {f.message}")
        lines.append("")
    if not errors and not warnings: lines += ["## Result","","All checks passed.",""]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: {report_path}")

def _emit(findings, args):
    if args.json:
        print(json.dumps([f.as_dict() for f in findings], ensure_ascii=False, indent=2))
    else:
        errors = [f for f in findings if f.level==ERROR]; warnings = [f for f in findings if f.level==WARN]
        if not errors and not warnings: print("Wiki validation passed: no errors or warnings.")
        else:
            for f in findings: print(repr(f))
            print(); print(f"Result: {len(errors)} error(s), {len(warnings)} warning(s)")

def main():
    parser = argparse.ArgumentParser(
        description="Pre-live wiki integrity checker for L3 Knowledge Vault.",
        epilog="""\nChecks performed (errors unless noted):
  meta_exists            WIKI_META.json present and valid JSON
  schema_version         wiki_schema_version >= 2
  source_files_structure source_files[] is list of objects with required keys
  facts_structure        facts[] present with all 10 required provenance fields
  source_files_exist     every source_files[].path exists on disk
  line_numbers           every fact line_number is within source file range
  fact_text_near_line    fact text appears near referenced line  [warning]
  fact_count             source_files[].fact_count matches actual facts
  conflict_facts         conflict_facts count matches is_conflict=True facts
  per_topic_last_batch   per_topic_last_batch consistent with facts
  topic_pages            wiki/topic-<id>.md exists for every topic
  by_type_pages          wiki/by-type/<type>.md exists for every fact_type
  sha256_freshness       source sha256 unchanged since build  [warning]
  mtime_freshness        source mtime not newer than built_at  [warning]

See docs/PRE_LIVE_CHECKLIST.md for full pre-live workflow.""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--memory-dir", type=Path, default=Path(".agent/memory"))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--write-report", type=Path, default=None, metavar="PATH")
    args = parser.parse_args()
    memory_dir = args.memory_dir
    if not memory_dir.exists():
        print(f"ERROR: memory directory not found: {memory_dir}", file=sys.stderr); return 1
    wiki_dir = memory_dir / "wiki"; findings = []
    meta = check_meta_exists(wiki_dir, findings)
    if meta is None:
        _emit(findings, args)
        if args.write_report: write_report(args.write_report, findings, memory_dir)
        return 1
    check_schema_version(meta, findings)
    check_source_files_structure(meta, findings)
    facts = check_facts_structure(meta, findings)
    resolved = check_source_files_exist(meta, memory_dir, findings)
    check_line_numbers(facts, resolved, findings)
    check_fact_text_at_line(facts, resolved, findings)
    check_fact_count_consistency(meta, facts, findings)
    check_conflict_facts_count(meta, facts, findings)
    check_per_topic_last_batch(meta, facts, findings)
    check_topic_pages_exist(meta, wiki_dir, findings)
    check_by_type_pages_exist(meta, wiki_dir, findings)
    check_sha256_freshness(meta, resolved, findings)
    check_mtime_freshness(meta, resolved, findings)
    if args.write_report: write_report(args.write_report, findings, memory_dir)
    _emit(findings, args)
    errors = [f for f in findings if f.level==ERROR]; warnings = [f for f in findings if f.level==WARN]
    if errors: return 1
    if args.strict and warnings: return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
