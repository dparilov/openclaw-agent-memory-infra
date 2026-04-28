#!/usr/bin/env python3
"""tests/test_validate_wiki.py — E3: validate-wiki.py integrity checks (14 tests)."""
from __future__ import annotations
import importlib.util, json, shutil, sys, tempfile, unittest
from io import StringIO
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / "scripts" / "context_access"

def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / fname)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS)); spec.loader.exec_module(mod); return mod

bw = _load("build_wiki", "build-wiki.py")
vw = _load("validate_wiki", "validate-wiki.py")

SAMPLE = """\
# Memory: topic-99

<!-- last-batch: 1 | last-write: 2026-04-28T10:00Z | batches: 0-1 -->

## [2026-04-27] Batch 0 — session test-b0
- A regular fact
- ⚠️ CONFLICT: conflict fact here

## [2026-04-28] Batch 1
- Another regular fact
"""

def _build(mem_dir, extra=None):
    old = sys.argv[:]
    sys.argv = ["build-wiki.py","--memory-dir",str(mem_dir)] + (extra or [])
    try: bw.main()
    except SystemExit: pass
    finally: sys.argv = old

def _validate(mem_dir, extra=None):
    old = sys.argv[:]; sys.argv = ["validate-wiki.py","--memory-dir",str(mem_dir)] + (extra or [])
    captured = []; orig_emit = vw._emit; orig_wr = vw.write_report
    def fake_emit(f,_): captured.extend(f)
    vw._emit = fake_emit; vw.write_report = lambda *a,**k: None
    try: code = vw.main()
    except SystemExit as e: code = int(e.code) if e.code is not None else 0
    finally: sys.argv = old; vw._emit = orig_emit; vw.write_report = orig_wr
    return code, captured

def _codes(findings): return [f.code for f in findings]

def _setup(tmp):
    mem_dir = Path(tmp)/"memory"; mem_dir.mkdir()
    (mem_dir/"topic-99.md").write_text(SAMPLE, encoding="utf-8")
    _build(mem_dir); return mem_dir

class TestFreshBuildValid(unittest.TestCase):
    def test_fresh_build_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem_dir = _setup(tmp); code, findings = _validate(mem_dir)
            self.assertEqual([f for f in findings if f.level=="error"], [])
            self.assertEqual(code, 0)

class TestMissingMeta(unittest.TestCase):
    def test_missing_meta_exit1(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem_dir = _setup(tmp); (mem_dir/"wiki"/"WIKI_META.json").unlink()
            code, findings = _validate(mem_dir)
            self.assertEqual(code, 1); self.assertIn("meta_missing", _codes(findings))

class TestMissingSourceFile(unittest.TestCase):
    def test_missing_source_file_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem_dir = _setup(tmp); (mem_dir/"topic-99.md").unlink()
            code, findings = _validate(mem_dir)
            self.assertEqual(code, 1); self.assertIn("source_file_missing", _codes(findings))

class TestSha256Mismatch(unittest.TestCase):
    def test_sha256_mismatch_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem_dir = _setup(tmp)
            (mem_dir/"topic-99.md").write_text(SAMPLE+"\n- Extra fact\n", encoding="utf-8")
            _, findings = _validate(mem_dir)
            self.assertIn("source_sha256_mismatch", _codes(findings))

class TestMtimeNewer(unittest.TestCase):
    def test_mtime_newer_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem_dir = _setup(tmp); mp = mem_dir/"wiki"/"WIKI_META.json"
            meta = json.loads(mp.read_text()); meta["built_at"] = "2020-01-01T00:00:00Z"
            mp.write_text(json.dumps(meta,indent=2), encoding="utf-8")
            _, findings = _validate(mem_dir)
            self.assertIn("source_mtime_newer", _codes(findings))

class TestLineNumberOutOfRange(unittest.TestCase):
    def test_line_out_of_range_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem_dir = _setup(tmp); mp = mem_dir/"wiki"/"WIKI_META.json"
            meta = json.loads(mp.read_text())
            if meta["facts"]: meta["facts"][0]["line_number"] = 99999
            mp.write_text(json.dumps(meta,indent=2), encoding="utf-8")
            code, findings = _validate(mem_dir)
            self.assertIn("line_number_out_of_range", _codes(findings)); self.assertEqual(code,1)

class TestFactCountMismatch(unittest.TestCase):
    def test_fact_count_mismatch_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem_dir = _setup(tmp); mp = mem_dir/"wiki"/"WIKI_META.json"
            meta = json.loads(mp.read_text())
            for sf in meta["source_files"]: sf["fact_count"] = 999
            mp.write_text(json.dumps(meta,indent=2), encoding="utf-8")
            code, findings = _validate(mem_dir)
            self.assertIn("fact_count_mismatch", _codes(findings)); self.assertEqual(code,1)

class TestConflictFactsMismatch(unittest.TestCase):
    def test_conflict_facts_mismatch_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem_dir = _setup(tmp); mp = mem_dir/"wiki"/"WIKI_META.json"
            meta = json.loads(mp.read_text()); meta["conflict_facts"] = 999
            mp.write_text(json.dumps(meta,indent=2), encoding="utf-8")
            code, findings = _validate(mem_dir)
            self.assertIn("conflict_facts_mismatch", _codes(findings)); self.assertEqual(code,1)

class TestMissingTopicPage(unittest.TestCase):
    def test_missing_topic_page_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem_dir = _setup(tmp); (mem_dir/"wiki"/"topic-99.md").unlink()
            code, findings = _validate(mem_dir)
            self.assertIn("topic_page_missing", _codes(findings)); self.assertEqual(code,1)

class TestMissingByTypePage(unittest.TestCase):
    def test_missing_by_type_page_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem_dir = _setup(tmp); td = mem_dir/"wiki"/"by-type"
            if td.exists(): shutil.rmtree(td)
            code, findings = _validate(mem_dir)
            self.assertIn("by_type_page_missing", _codes(findings)); self.assertEqual(code,1)

class TestJsonOutput(unittest.TestCase):
    def test_json_output_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem_dir = _setup(tmp); old_out = sys.stdout; sys.stdout = cap = StringIO()
            old_argv = sys.argv[:]; sys.argv = ["validate-wiki.py","--memory-dir",str(mem_dir),"--json"]
            try: vw.main()
            except SystemExit: pass
            finally: sys.stdout = old_out; sys.argv = old_argv
            self.assertIsInstance(json.loads(cap.getvalue()), list)

class TestStrictMode(unittest.TestCase):
    def test_strict_warnings_cause_exit1(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem_dir = _setup(tmp); mp = mem_dir/"wiki"/"WIKI_META.json"
            meta = json.loads(mp.read_text()); meta["built_at"] = "2020-01-01T00:00:00Z"
            mp.write_text(json.dumps(meta,indent=2), encoding="utf-8")
            code_n, fn = _validate(mem_dir)
            if all(f.level=="warning" for f in fn): self.assertEqual(code_n, 0)
            code_s, _ = _validate(mem_dir, ["--strict"])
            self.assertEqual(code_s, 1)

class TestTopicWithNoFacts(unittest.TestCase):
    def test_topic_with_no_facts_no_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem_dir = _setup(tmp); mp = mem_dir/"wiki"/"WIKI_META.json"
            meta = json.loads(mp.read_text())
            meta["per_topic_last_batch"]["ghost-topic"] = None
            meta["source_files"].append({"path":"memory/topic-ghost-topic.md","topic_id":"ghost-topic","fact_count":0,"last_batch":None})
            (mem_dir/"wiki"/"topic-ghost-topic.md").write_text("# ghost\n", encoding="utf-8")
            (mem_dir/"topic-ghost-topic.md").write_text("# ghost\n", encoding="utf-8")
            mp.write_text(json.dumps(meta,indent=2), encoding="utf-8")
            _, findings = _validate(mem_dir)
            self.assertEqual([f.code for f in findings if f.code=="per_topic_last_batch_mismatch"], [])
