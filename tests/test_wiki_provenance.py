#!/usr/bin/env python3
"""
tests/test_wiki_provenance.py — D1: WikiFact parser + WIKI_META provenance index.

Tests cover:
  - parse_facts() captures batch_date and session_id
  - Nested bullets are NOT promoted to facts
  - Conflict facts (- ⚠️ ...) stored as is_conflict=True
  - Top-level regular facts are is_conflict=False
  - Fact outside any batch heading: batch_n=None
  - WIKI_META.json contains required schema v2 fields
  - Fact IDs are deterministic
  - build_git_sha is str or None
  - dry-run writes nothing
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Load build-wiki module from source
# ---------------------------------------------------------------------------

SCRIPTS = Path(__file__).parent.parent / "scripts" / "context_access"


def _load_build_wiki():
    spec = importlib.util.spec_from_file_location(
        "build_wiki", SCRIPTS / "build-wiki.py"
    )
    mod = importlib.util.module_from_spec(spec)
    # Ensure io_utils is resolvable
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


bw = _load_build_wiki()
parse_facts = bw.parse_facts
extract_facts = bw.extract_facts
WikiFact = bw.WikiFact


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CONTENT = """\
# Memory: topic-test

<!-- last-batch: 3 | last-write: 2026-04-28T10:00Z | batches: 0–3 -->

## [2026-04-27] Batch 0 — session infra-init-b0
- First fact in batch 0
- Second fact in batch 0
  - nested bullet (should NOT be a fact)

## [2026-04-28] Batch 1
- Fact in batch 1, no session
  - also nested, skip

## [2026-04-28] Batch 2 — session hotfix-b2
- Regular fact in batch 2
- ⚠️ CONFLICT: This fact conflicts with batch 0

## [2026-04-28] Batch -1
- Promotion fact (batch -1, no batch_n)
"""

NO_BATCH_CONTENT = """\
# Memory: topic-orphan

- Orphan fact before any heading
"""


# ---------------------------------------------------------------------------
# Test: parse_facts basic extraction
# ---------------------------------------------------------------------------

class TestParseFacts(unittest.TestCase):

    def setUp(self):
        self.facts = parse_facts(SAMPLE_CONTENT, source_file="memory/topic-test.md", topic_id="test")

    def test_returns_list_of_wiki_facts(self):
        self.assertIsInstance(self.facts, list)
        self.assertTrue(len(self.facts) > 0)

    def test_nested_bullets_not_facts(self):
        texts = [f["text"] for f in self.facts]
        self.assertFalse(any("nested bullet" in t for t in texts))
        self.assertFalse(any("also nested" in t for t in texts))

    def test_batch_date_captured(self):
        b0_facts = [f for f in self.facts if f["batch_n"] == 0]
        self.assertTrue(len(b0_facts) >= 1)
        for f in b0_facts:
            self.assertEqual(f["batch_date"], "2026-04-27")

    def test_session_id_captured(self):
        b0_facts = [f for f in self.facts if f["batch_n"] == 0]
        for f in b0_facts:
            self.assertEqual(f["session_id"], "infra-init-b0")

    def test_batch_without_session_has_none_session(self):
        b1_facts = [f for f in self.facts if f["batch_n"] == 1]
        self.assertTrue(len(b1_facts) >= 1)
        for f in b1_facts:
            self.assertIsNone(f["session_id"])

    def test_batch_date_for_batch1(self):
        b1_facts = [f for f in self.facts if f["batch_n"] == 1]
        for f in b1_facts:
            self.assertEqual(f["batch_date"], "2026-04-28")

    def test_conflict_fact_is_conflict_true(self):
        conflicts = [f for f in self.facts if f["is_conflict"]]
        self.assertEqual(len(conflicts), 1)
        self.assertIn("CONFLICT", conflicts[0]["text"])

    def test_regular_fact_is_conflict_false(self):
        regular = [f for f in self.facts if not f["is_conflict"]]
        self.assertTrue(len(regular) >= 3)

    def test_source_file_stored(self):
        for f in self.facts:
            self.assertEqual(f["source_file"], "memory/topic-test.md")

    def test_topic_id_stored(self):
        for f in self.facts:
            self.assertEqual(f["topic_id"], "test")

    def test_line_number_positive(self):
        for f in self.facts:
            self.assertGreater(f["line_number"], 0)

    def test_batch_minus1_gives_none_batch_n(self):
        promotion = [f for f in self.facts if "Promotion fact" in f["text"]]
        self.assertEqual(len(promotion), 1)
        self.assertIsNone(promotion[0]["batch_n"])

    def test_text_stripped_of_dash_prefix(self):
        # text should NOT start with "- "
        for f in self.facts:
            self.assertFalse(f["text"].startswith("- "), f"text starts with '- ': {f['text']!r}")


# ---------------------------------------------------------------------------
# Test: fact_id determinism
# ---------------------------------------------------------------------------

class TestFactIdDeterminism(unittest.TestCase):

    def test_id_format(self):
        facts = parse_facts(SAMPLE_CONTENT, source_file="x.md", topic_id="7301")
        for f in facts:
            self.assertTrue(
                f["id"].startswith("wiki-fact-7301-"),
                f"Bad id: {f['id']!r}"
            )

    def test_id_contains_line_number(self):
        facts = parse_facts(SAMPLE_CONTENT, source_file="x.md", topic_id="7301")
        for f in facts:
            self.assertIn(f"-l{f['line_number']}", f["id"])

    def test_id_contains_batch_label(self):
        facts = parse_facts(SAMPLE_CONTENT, source_file="x.md", topic_id="7301")
        b0 = [f for f in facts if f["batch_n"] == 0]
        for f in b0:
            self.assertIn("-b0-", f["id"])

    def test_id_unknown_for_no_batch(self):
        facts = parse_facts(NO_BATCH_CONTENT, source_file="x.md", topic_id="orphan")
        self.assertTrue(len(facts) >= 1)
        for f in facts:
            self.assertIn("-bunknown-", f["id"])

    def test_ids_are_unique_within_file(self):
        facts = parse_facts(SAMPLE_CONTENT, source_file="x.md", topic_id="7301")
        ids = [f["id"] for f in facts]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate fact IDs found")


# ---------------------------------------------------------------------------
# Test: orphan facts (outside batch)
# ---------------------------------------------------------------------------

class TestOrphanFacts(unittest.TestCase):

    def test_fact_outside_batch_has_none_batch_n(self):
        facts = parse_facts(NO_BATCH_CONTENT, topic_id="orphan")
        self.assertEqual(len(facts), 1)
        self.assertIsNone(facts[0]["batch_n"])
        self.assertIsNone(facts[0]["batch_date"])
        self.assertIsNone(facts[0]["session_id"])


# ---------------------------------------------------------------------------
# Test: backward-compatible extract_facts()
# ---------------------------------------------------------------------------

class TestExtractFactsCompat(unittest.TestCase):

    def test_returns_list_of_dicts(self):
        facts = extract_facts(SAMPLE_CONTENT)
        self.assertIsInstance(facts, list)
        for f in facts:
            self.assertIn("text", f)
            self.assertIn("batch_n", f)
            self.assertIn("is_conflict", f)

    def test_text_has_dash_prefix(self):
        facts = extract_facts(SAMPLE_CONTENT)
        for f in facts:
            self.assertTrue(f["text"].startswith("- "), f"Expected '- ' prefix: {f['text']!r}")

    def test_nested_bullets_excluded(self):
        facts = extract_facts(SAMPLE_CONTENT)
        texts = [f["text"] for f in facts]
        self.assertFalse(any("nested" in t for t in texts))


# ---------------------------------------------------------------------------
# Test: WIKI_META.json schema v2
# ---------------------------------------------------------------------------

class TestWikiMetaSchema(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mem_dir = Path(self.tmp) / "memory"
        self.mem_dir.mkdir()
        (self.mem_dir / "topic-9999.md").write_text(SAMPLE_CONTENT, encoding="utf-8")

    def _run_build(self):
        """Run main() and return parsed WIKI_META.json."""
        import sys as _sys
        old_argv = _sys.argv[:]
        _sys.argv = ["build-wiki.py", "--memory-dir", str(self.mem_dir)]
        try:
            bw.main()
        except SystemExit:
            pass
        finally:
            _sys.argv = old_argv
        meta_path = self.mem_dir / "wiki" / "WIKI_META.json"
        return json.loads(meta_path.read_text())

    def test_schema_version_is_2(self):
        meta = self._run_build()
        self.assertEqual(meta["wiki_schema_version"], 2)

    def test_built_at_present(self):
        meta = self._run_build()
        self.assertIn("built_at", meta)
        self.assertRegex(meta["built_at"], r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

    def test_build_git_sha_present(self):
        meta = self._run_build()
        self.assertIn("build_git_sha", meta)
        # value is str or None
        self.assertTrue(
            meta["build_git_sha"] is None or isinstance(meta["build_git_sha"], str),
            f"Expected str or None, got: {meta['build_git_sha']!r}"
        )

    def test_source_files_is_list_of_objects(self):
        meta = self._run_build()
        self.assertIn("source_files", meta)
        self.assertIsInstance(meta["source_files"], list)
        self.assertTrue(len(meta["source_files"]) >= 1)
        entry = meta["source_files"][0]
        self.assertIn("path", entry)
        self.assertIn("topic_id", entry)
        self.assertIn("fact_count", entry)
        self.assertIn("last_batch", entry)

    def test_per_topic_last_batch_present(self):
        meta = self._run_build()
        self.assertIn("per_topic_last_batch", meta)
        self.assertIn("9999", meta["per_topic_last_batch"])

    def test_conflict_facts_count(self):
        meta = self._run_build()
        self.assertIn("conflict_facts", meta)
        self.assertIsInstance(meta["conflict_facts"], int)
        self.assertEqual(meta["conflict_facts"], 1)

    def test_facts_index_present(self):
        meta = self._run_build()
        self.assertIn("facts", meta)
        self.assertIsInstance(meta["facts"], list)
        self.assertTrue(len(meta["facts"]) >= 1)

    def test_facts_have_required_fields(self):
        meta = self._run_build()
        required = {"id", "text", "topic_id", "source_file", "line_number",
                    "batch_n", "batch_date", "session_id", "is_conflict", "fact_type"}
        for f in meta["facts"]:
            missing = required - set(f.keys())
            self.assertFalse(missing, f"Fact missing fields: {missing}")

    def test_facts_ids_are_unique(self):
        meta = self._run_build()
        ids = [f["id"] for f in meta["facts"]]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate fact IDs in WIKI_META.json")


# ---------------------------------------------------------------------------
# Test: dry-run writes nothing
# ---------------------------------------------------------------------------

class TestDryRunWritesNothing(unittest.TestCase):

    def test_dry_run_no_wiki_dir(self):
        tmp = tempfile.mkdtemp()
        mem_dir = Path(tmp) / "memory"
        mem_dir.mkdir()
        (mem_dir / "topic-1.md").write_text(SAMPLE_CONTENT, encoding="utf-8")

        import sys as _sys
        old_argv = _sys.argv[:]
        _sys.argv = ["build-wiki.py", "--memory-dir", str(mem_dir), "--dry-run"]
        try:
            bw.main()
        except SystemExit:
            pass
        finally:
            _sys.argv = old_argv

        wiki_dir = mem_dir / "wiki"
        self.assertFalse(wiki_dir.exists(), "wiki/ should not be created in dry-run mode")


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Test: extract_facts conflict filtering
# ---------------------------------------------------------------------------

class TestExtractFactsConflictFiltering(unittest.TestCase):

    def test_extract_facts_skips_conflicts_by_default(self):
        facts = extract_facts(SAMPLE_CONTENT)
        conflict_texts = [f["text"] for f in facts if "CONFLICT" in f["text"]]
        self.assertEqual(conflict_texts, [],
                         "extract_facts() must skip conflict facts by default")

    def test_extract_facts_can_include_conflicts(self):
        facts = extract_facts(SAMPLE_CONTENT, include_conflicts=True)
        conflict_texts = [f["text"] for f in facts if "CONFLICT" in f["text"]]
        self.assertTrue(len(conflict_texts) >= 1,
                        "include_conflicts=True must return conflict facts")


# ---------------------------------------------------------------------------
# Test: source paths are portable (not absolute)
# ---------------------------------------------------------------------------

class TestSourcePathsPortable(unittest.TestCase):

    def setUp(self):
        import tempfile as _tf
        self.tmp = _tf.mkdtemp()
        self.mem_dir = Path(self.tmp) / "memory"
        self.mem_dir.mkdir()
        (self.mem_dir / "topic-8888.md").write_text(SAMPLE_CONTENT, encoding="utf-8")

    def _run_build_and_meta(self):
        import sys as _sys
        old_argv = _sys.argv[:]
        _sys.argv = ["build-wiki.py", "--memory-dir", str(self.mem_dir)]
        try:
            bw.main()
        except SystemExit:
            pass
        finally:
            _sys.argv = old_argv
        meta_path = self.mem_dir / "wiki" / "WIKI_META.json"
        return json.loads(meta_path.read_text())

    def test_source_files_path_not_absolute(self):
        meta = self._run_build_and_meta()
        for sf in meta["source_files"]:
            self.assertFalse(
                Path(sf["path"]).is_absolute(),
                f"source_files[].path is absolute: {sf['path']!r}"
            )

    def test_fact_source_file_not_absolute(self):
        meta = self._run_build_and_meta()
        for f in meta["facts"]:
            self.assertFalse(
                Path(f["source_file"]).is_absolute(),
                f"fact source_file is absolute: {f['source_file']!r}"
            )
