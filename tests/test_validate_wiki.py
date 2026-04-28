#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,json,shutil,sys,tempfile,unittest
from io import StringIO
from pathlib import Path

SCRIPTS=Path(__file__).parent.parent/"scripts"/"context_access"

def _load(name,fname):
    spec=importlib.util.spec_from_file_location(name,SCRIPTS/fname)
    mod=importlib.util.module_from_spec(spec); sys.path.insert(0,str(SCRIPTS)); spec.loader.exec_module(mod); return mod

bw=_load("build_wiki","build-wiki.py"); vw=_load("validate_wiki","validate-wiki.py")

SAMPLE="""\
# Memory: topic-99
<!-- last-batch: 1 | last-write: 2026-04-28T10:00Z | batches: 0-1 -->
## [2026-04-27] Batch 0 — session test-b0
- A regular fact
- \u26a0\ufe0f CONFLICT: conflict fact here
## [2026-04-28] Batch 1
- Another regular fact
"""

def _build(mem):
    old=sys.argv[:]; sys.argv=["build-wiki.py","--memory-dir",str(mem)]
    try: bw.main()
    except SystemExit: pass
    finally: sys.argv=old

def _validate(mem,extra=None):
    old=sys.argv[:]; sys.argv=["validate-wiki.py","--memory-dir",str(mem)]+(extra or [])
    captured=[]; orig_emit=vw._emit; orig_wr=vw.write_report
    def fake_emit(f,_): captured.extend(f)
    vw._emit=fake_emit; vw.write_report=lambda *a,**k: None
    try: code=vw.main()
    except SystemExit as e: code=int(e.code) if e.code else 0
    finally: sys.argv=old; vw._emit=orig_emit; vw.write_report=orig_wr
    return code,captured

def _codes(f): return [x.code for x in f]

def _valid(tmp):
    m=Path(tmp)/"memory"; m.mkdir(); (m/"topic-99.md").write_text(SAMPLE,encoding="utf-8"); _build(m); return m

# ── original 13 tests ────────────────────────────────────────────────────

class TestFreshBuild(unittest.TestCase):
    def test_passes(self):
        with tempfile.TemporaryDirectory() as t:
            m=_valid(t); code,f=_validate(m)
            self.assertEqual([x for x in f if x.level=="error"],[]); self.assertEqual(code,0)

class TestMissingMeta(unittest.TestCase):
    def test_exit1(self):
        with tempfile.TemporaryDirectory() as t:
            m=_valid(t); (m/"wiki"/"WIKI_META.json").unlink(); code,f=_validate(m)
            self.assertEqual(code,1); self.assertIn("meta_missing",_codes(f))

class TestMissingSourceFile(unittest.TestCase):
    def test_error(self):
        with tempfile.TemporaryDirectory() as t:
            m=_valid(t); (m/"topic-99.md").unlink(); code,f=_validate(m)
            self.assertEqual(code,1); self.assertIn("source_file_missing",_codes(f))

class TestSha256Mismatch(unittest.TestCase):
    def test_warning(self):
        with tempfile.TemporaryDirectory() as t:
            m=_valid(t); (m/"topic-99.md").write_text(SAMPLE+"\n- Extra\n",encoding="utf-8")
            _,f=_validate(m); self.assertIn("source_sha256_mismatch",_codes(f))

class TestMtimeNewer(unittest.TestCase):
    def test_warning(self):
        with tempfile.TemporaryDirectory() as t:
            m=_valid(t); mp=m/"wiki"/"WIKI_META.json"; meta=json.loads(mp.read_text())
            meta["built_at"]="2020-01-01T00:00:00Z"
            mp.write_text(json.dumps(meta,indent=2),encoding="utf-8")
            _,f=_validate(m); self.assertIn("source_mtime_newer",_codes(f))

class TestLineOutOfRange(unittest.TestCase):
    def test_error(self):
        with tempfile.TemporaryDirectory() as t:
            m=_valid(t); mp=m/"wiki"/"WIKI_META.json"; meta=json.loads(mp.read_text())
            if meta["facts"]: meta["facts"][0]["line_number"]=99999
            mp.write_text(json.dumps(meta,indent=2),encoding="utf-8")
            code,f=_validate(m); self.assertIn("line_number_out_of_range",_codes(f)); self.assertEqual(code,1)

class TestFactCountMismatch(unittest.TestCase):
    def test_error(self):
        with tempfile.TemporaryDirectory() as t:
            m=_valid(t); mp=m/"wiki"/"WIKI_META.json"; meta=json.loads(mp.read_text())
            for sf in meta["source_files"]: sf["fact_count"]=999
            mp.write_text(json.dumps(meta,indent=2),encoding="utf-8")
            code,f=_validate(m); self.assertIn("fact_count_mismatch",_codes(f)); self.assertEqual(code,1)

class TestConflictMismatch(unittest.TestCase):
    def test_error(self):
        with tempfile.TemporaryDirectory() as t:
            m=_valid(t); mp=m/"wiki"/"WIKI_META.json"; meta=json.loads(mp.read_text())
            meta["conflict_facts"]=999
            mp.write_text(json.dumps(meta,indent=2),encoding="utf-8")
            code,f=_validate(m); self.assertIn("conflict_facts_mismatch",_codes(f)); self.assertEqual(code,1)

class TestMissingTopicPage(unittest.TestCase):
    def test_error(self):
        with tempfile.TemporaryDirectory() as t:
            m=_valid(t); (m/"wiki"/"topic-99.md").unlink(); code,f=_validate(m)
            self.assertIn("topic_page_missing",_codes(f)); self.assertEqual(code,1)

class TestMissingByTypePage(unittest.TestCase):
    def test_error(self):
        with tempfile.TemporaryDirectory() as t:
            m=_valid(t)
            if (m/"wiki"/"by-type").exists(): shutil.rmtree(m/"wiki"/"by-type")
            code,f=_validate(m); self.assertIn("by_type_page_missing",_codes(f)); self.assertEqual(code,1)

class TestJsonOutput(unittest.TestCase):
    def test_valid_json(self):
        with tempfile.TemporaryDirectory() as t:
            m=_valid(t); old=sys.stdout; sys.stdout=cap=StringIO()
            old_argv=sys.argv[:]; sys.argv=["validate-wiki.py","--memory-dir",str(m),"--json"]
            try: vw.main()
            except SystemExit: pass
            finally: sys.stdout=old; sys.argv=old_argv
            self.assertIsInstance(json.loads(cap.getvalue()),list)

class TestStrictMode(unittest.TestCase):
    def test_warnings_cause_exit1(self):
        with tempfile.TemporaryDirectory() as t:
            m=_valid(t); mp=m/"wiki"/"WIKI_META.json"; meta=json.loads(mp.read_text())
            meta["built_at"]="2020-01-01T00:00:00Z"
            mp.write_text(json.dumps(meta,indent=2),encoding="utf-8")
            c1,_=_validate(m,["--strict"]); self.assertEqual(c1,1)

class TestGhostTopicNoMismatch(unittest.TestCase):
    def test_no_mismatch(self):
        with tempfile.TemporaryDirectory() as t:
            m=_valid(t); mp=m/"wiki"/"WIKI_META.json"; meta=json.loads(mp.read_text())
            meta["per_topic_last_batch"]["ghost"]=None
            meta["source_files"].append({"path":"memory/topic-ghost.md","topic_id":"ghost",
                "fact_count":0,"last_batch":None,"sha256":"","mtime":""})
            (m/"wiki"/"topic-ghost.md").write_text("# ghost\n",encoding="utf-8")
            (m/"topic-ghost.md").write_text("# ghost\n",encoding="utf-8")
            mp.write_text(json.dumps(meta,indent=2),encoding="utf-8"); _,f=_validate(m)
            self.assertEqual([x.code for x in f if x.code=="per_topic_last_batch_mismatch"],[])

# ── new hardening tests (PR #15 review) ──────────────────────────────────

class TestSha256RequiredKey(unittest.TestCase):
    """E-req 1a: sha256 must be present in source_files[]."""
    def test_missing_sha256_is_error(self):
        with tempfile.TemporaryDirectory() as t:
            m=_valid(t); mp=m/"wiki"/"WIKI_META.json"; meta=json.loads(mp.read_text())
            if meta["source_files"]: del meta["source_files"][0]["sha256"]
            mp.write_text(json.dumps(meta,indent=2),encoding="utf-8")
            code,f=_validate(m)
            self.assertIn("source_files_entry_missing_keys",_codes(f)); self.assertEqual(code,1)

class TestMtimeRequiredKey(unittest.TestCase):
    """E-req 1b: mtime must be present in source_files[]."""
    def test_missing_mtime_is_error(self):
        with tempfile.TemporaryDirectory() as t:
            m=_valid(t); mp=m/"wiki"/"WIKI_META.json"; meta=json.loads(mp.read_text())
            if meta["source_files"]: del meta["source_files"][0]["mtime"]
            mp.write_text(json.dumps(meta,indent=2),encoding="utf-8")
            code,f=_validate(m)
            self.assertIn("source_files_entry_missing_keys",_codes(f)); self.assertEqual(code,1)

class TestMalformedSourceFiles(unittest.TestCase):
    """E-req 2: validator must not crash on non-dict source_files entries."""
    def test_bad_entry_no_crash(self):
        with tempfile.TemporaryDirectory() as t:
            m=_valid(t); mp=m/"wiki"/"WIKI_META.json"; meta=json.loads(mp.read_text())
            meta["source_files"]=["bad-entry"]
            mp.write_text(json.dumps(meta,indent=2),encoding="utf-8")
            code,f=_validate(m)
            self.assertIn("source_files_entry_not_dict",_codes(f)); self.assertEqual(code,1)

class TestStoredMtimeMismatch(unittest.TestCase):
    """E-req 4a: stored mtime differs from actual file mtime → warning."""
    def test_warning(self):
        with tempfile.TemporaryDirectory() as t:
            m=_valid(t); mp=m/"wiki"/"WIKI_META.json"; meta=json.loads(mp.read_text())
            for sf in meta["source_files"]: sf["mtime"]="2020-01-01T00:00:00Z"
            mp.write_text(json.dumps(meta,indent=2),encoding="utf-8")
            _,f=_validate(m); self.assertIn("source_mtime_mismatch",_codes(f))

class TestStoredMtimeInvalidFormat(unittest.TestCase):
    """E-req 4b: stored mtime with invalid format → warning."""
    def test_warning(self):
        with tempfile.TemporaryDirectory() as t:
            m=_valid(t); mp=m/"wiki"/"WIKI_META.json"; meta=json.loads(mp.read_text())
            for sf in meta["source_files"]: sf["mtime"]="not-a-date"
            mp.write_text(json.dumps(meta,indent=2),encoding="utf-8")
            _,f=_validate(m); self.assertIn("source_mtime_invalid_format",_codes(f))

if __name__=="__main__": unittest.main()
