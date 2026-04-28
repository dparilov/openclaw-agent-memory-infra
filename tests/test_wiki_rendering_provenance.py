#!/usr/bin/env python3
"""
tests/test_wiki_rendering_provenance.py — D2: provenance rendering in wiki pages.

Tests cover:
  1.  format_provenance() includes source_file, topic_id, batch, date, session, line
  2.  format_provenance() handles batch_n=None
  3.  format_provenance() marks conflict facts
  4.  topic page includes provenance tail under each fact
  5.  topic page includes conflict fact visibly (⚠️ section)
  6.  by-type page includes provenance under each fact
  7.  by-type page includes topic/source/batch for mixed-topic facts
  8.  non-numeric topic file is rendered (wiki/topic-openclaw-infra.md)
  9.  dry-run writes nothing
  10. WIKI_META schema v2 still present after D2 build
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / "scripts" / "context_access"


def _load_build_wiki():
    spec = importlib.util.spec_from_file_location("build_wiki", SCRIPTS / "build-wiki.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


bw = _load_build_wiki()

SAMPLE_CONTENT = """\
# Memory: topic-test

<!-- last-batch: 2 | last-write: 2026-04-28T10:00Z | batches: 0-2 -->

## [2026-04-27] Batch 0 — session infra-init-b0
- First regular fact
- Second regular fact

## [2026-04-28] Batch 2 — session hotfix-b2
- Third fact in batch 2
- ⚠️ CONFLICT: This fact conflicts with batch 0
"""

NON_NUMERIC_CONTENT = """\
# Memory: openclaw-infra

<!-- last-batch: 0 | last-write: 2026-04-28T10:00Z | batches: 0-0 -->

## [2026-04-28] Batch 0 — session setup-b0
- Non-numeric context fact
"""


# ---------------------------------------------------------------------------
# 1-3: format_provenance()
# ---------------------------------------------------------------------------

class TestFormatProvenance(unittest.TestCase):

    def _make_fact(self, **overrides):
        base = dict(
            id="wiki-fact-7301-b0-l5",
            text="Some fact",
            topic_id="7301",
            source_file="memory/topic-7301.md",
            line_number=5,
            batch_n=0,
            batch_date="2026-04-27",
            session_id="infra-init-b0",
            is_conflict=False,
            fact_type="general",
        )
        base.update(overrides)
        return base

    def test_includes_source_file(self):
        f = self._make_fact()
        p = bw.format_provenance(f)
        self.assertIn("memory/topic-7301.md", p)

    def test_includes_topic_id(self):
        f = self._make_fact()
        p = bw.format_provenance(f)
        self.assertIn("7301", p)

    def test_includes_batch_number(self):
        f = self._make_fact(batch_n=4)
        p = bw.format_provenance(f)
        self.assertIn("Batch 4", p)

    def test_includes_batch_date(self):
        f = self._make_fact(batch_date="2026-04-27")
        p = bw.format_provenance(f)
        self.assertIn("2026-04-27", p)

    def test_includes_session_id(self):
        f = self._make_fact(session_id="my-session-x")
        p = bw.format_provenance(f)
        self.assertIn("my-session-x", p)

    def test_includes_line_number(self):
        f = self._make_fact(line_number=42)
        p = bw.format_provenance(f)
        self.assertIn("line 42", p)

    def test_batch_none_renders_unknown(self):
        f = self._make_fact(batch_n=None, batch_date=None, session_id=None)
        p = bw.format_provenance(f)
        self.assertIn("Batch unknown", p)
        self.assertNotIn("Batch 0", p)

    def test_conflict_fact_marked(self):
        f = self._make_fact(is_conflict=True)
        p = bw.format_provenance(f)
        self.assertIn("conflict", p.lower())

    def test_non_conflict_not_marked(self):
        f = self._make_fact(is_conflict=False)
        p = bw.format_provenance(f)
        self.assertNotIn("conflict", p.lower())

    def test_output_is_italic_markdown(self):
        f = self._make_fact()
        p = bw.format_provenance(f)
        self.assertIn("_Source:", p)
        self.assertTrue(p.strip().endswith("_"))


# ---------------------------------------------------------------------------
# Helper: run build and return wiki files
# ---------------------------------------------------------------------------

def _run_build(mem_dir: Path, extra_args: list[str] | None = None) -> None:
    old_argv = sys.argv[:]
    sys.argv = ["build-wiki.py", "--memory-dir", str(mem_dir)] + (extra_args or [])
    try:
        bw.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv


# ---------------------------------------------------------------------------
# 4-5: topic page provenance
# ---------------------------------------------------------------------------

class TestTopicPageProvenance(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mem_dir = Path(self.tmp) / "memory"
        self.mem_dir.mkdir()
        (self.mem_dir / "topic-7301.md").write_text(SAMPLE_CONTENT, encoding="utf-8")
        _run_build(self.mem_dir)
        self.topic_page = (self.mem_dir / "wiki" / "topic-7301.md").read_text()

    def test_topic_page_has_provenance_under_facts(self):
        self.assertIn("_Source:", self.topic_page)

    def test_topic_page_has_source_file(self):
        self.assertIn("memory/topic-7301.md", self.topic_page)

    def test_topic_page_has_batch_number(self):
        self.assertIn("Batch 0", self.topic_page)

    def test_topic_page_has_session_id(self):
        self.assertIn("infra-init-b0", self.topic_page)

    def test_topic_page_has_conflict_section(self):
        self.assertIn("Conflict", self.topic_page)

    def test_topic_page_conflict_visibly_marked(self):
        self.assertIn("⚠️", self.topic_page)

    def test_topic_page_conflict_fact_text_visible(self):
        self.assertIn("CONFLICT", self.topic_page)


# ---------------------------------------------------------------------------
# 6-7: by-type page provenance
# ---------------------------------------------------------------------------

class TestByTypePageProvenance(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mem_dir = Path(self.tmp) / "memory"
        self.mem_dir.mkdir()
        # Two topics so we can test mixed-topic provenance
        (self.mem_dir / "topic-7301.md").write_text(SAMPLE_CONTENT, encoding="utf-8")
        (self.mem_dir / "topic-9999.md").write_text("""\
# Memory: topic-9999

## [2026-04-28] Batch 0 — session other-b0
- Another general fact
""", encoding="utf-8")
        _run_build(self.mem_dir)
        self.by_type_dir = self.mem_dir / "wiki" / "by-type"

    def test_by_type_dir_created(self):
        self.assertTrue(self.by_type_dir.exists())

    def test_general_page_has_provenance(self):
        general = (self.by_type_dir / "general.md")
        self.assertTrue(general.exists(), "general.md not found")
        content = general.read_text()
        self.assertIn("_Source:", content)

    def test_by_type_page_has_source_file(self):
        general = (self.by_type_dir / "general.md").read_text()
        self.assertIn("memory/", general)

    def test_by_type_page_has_batch(self):
        general = (self.by_type_dir / "general.md").read_text()
        self.assertIn("Batch", general)

    def test_by_type_mixed_topics_both_provenance(self):
        general = (self.by_type_dir / "general.md").read_text()
        # Both topic IDs must appear in provenance
        self.assertIn("7301", general)
        self.assertIn("9999", general)


# ---------------------------------------------------------------------------
# 8: non-numeric topic file
# ---------------------------------------------------------------------------

class TestNonNumericTopicFile(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mem_dir = Path(self.tmp) / "memory"
        self.mem_dir.mkdir()
        (self.mem_dir / "topic-openclaw-infra.md").write_text(
            NON_NUMERIC_CONTENT, encoding="utf-8"
        )
        _run_build(self.mem_dir)

    def test_non_numeric_wiki_page_created(self):
        wiki_page = self.mem_dir / "wiki" / "topic-openclaw-infra.md"
        self.assertTrue(wiki_page.exists(), "wiki/topic-openclaw-infra.md not created")

    def test_non_numeric_page_has_content(self):
        wiki_page = (self.mem_dir / "wiki" / "topic-openclaw-infra.md").read_text()
        self.assertIn("Non-numeric context fact", wiki_page)

    def test_non_numeric_page_has_provenance(self):
        wiki_page = (self.mem_dir / "wiki" / "topic-openclaw-infra.md").read_text()
        self.assertIn("_Source:", wiki_page)

    def test_non_numeric_in_meta_source_files(self):
        meta = json.loads((self.mem_dir / "wiki" / "WIKI_META.json").read_text())
        topic_ids = [sf["topic_id"] for sf in meta["source_files"]]
        self.assertIn("openclaw-infra", topic_ids)


# ---------------------------------------------------------------------------
# 9: dry-run
# ---------------------------------------------------------------------------

class TestDryRunD2(unittest.TestCase):

    def test_dry_run_writes_nothing(self):
        tmp = tempfile.mkdtemp()
        mem_dir = Path(tmp) / "memory"
        mem_dir.mkdir()
        (mem_dir / "topic-1.md").write_text(SAMPLE_CONTENT, encoding="utf-8")
        _run_build(mem_dir, ["--dry-run"])
        self.assertFalse((mem_dir / "wiki").exists(),
                         "wiki/ must not be created in --dry-run mode")


# ---------------------------------------------------------------------------
# 10: WIKI_META schema v2 still intact
# ---------------------------------------------------------------------------

class TestWikiMetaV2Intact(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.mem_dir = Path(tmp) / "memory"
        self.mem_dir.mkdir()
        (self.mem_dir / "topic-42.md").write_text(SAMPLE_CONTENT, encoding="utf-8")
        _run_build(self.mem_dir)
        self.meta = json.loads((self.mem_dir / "wiki" / "WIKI_META.json").read_text())

    def test_schema_version_2(self):
        self.assertEqual(self.meta["wiki_schema_version"], 2)

    def test_source_files_objects(self):
        self.assertIsInstance(self.meta["source_files"], list)
        self.assertTrue(len(self.meta["source_files"]) >= 1)
        self.assertIn("path", self.meta["source_files"][0])

    def test_facts_index_present(self):
        self.assertIn("facts", self.meta)
        self.assertIsInstance(self.meta["facts"], list)

    def test_per_topic_last_batch(self):
        self.assertIn("per_topic_last_batch", self.meta)

    def test_conflict_facts_count(self):
        self.assertIn("conflict_facts", self.meta)
        self.assertIsInstance(self.meta["conflict_facts"], int)

    def test_build_git_sha_present(self):
        self.assertIn("build_git_sha", self.meta)
        val = self.meta["build_git_sha"]
        self.assertTrue(val is None or isinstance(val, str))


if __name__ == "__main__":
    unittest.main()
