#!/usr/bin/env python3
"""
tests/test_dry_run.py — verify that --dry-run modes in archive-batch-v2,
build-wiki, and manage-candidates never mutate memory, audit, progress, or
wiki directories.

All tests are dependency-free (stdlib + the scripts themselves).
"""
from __future__ import annotations

import importlib.util
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).parent.parent / "scripts" / "context_access"


def _load(name: str, filename: str):
    """Import a script as a module without executing its __main__ block.

    Registers the module in sys.modules BEFORE exec_module so that
    @dataclass and other module-level decorators can find the module via
    sys.modules[cls.__module__] (Python 3.12+ dataclasses requirement).
    """
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # must be registered before exec_module
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_MEMORY = """\
<!-- last-batch: 0 | last-write: 2026-01-01 | batches: 0-0 -->
# Topic 9999

## [2026-01-01] Batch 0 — session dry-test
- This is a test decision: prefer dry-run paths
- constraint: never mutate on dry-run
"""


# ---------------------------------------------------------------------------
# build-wiki --dry-run
# ---------------------------------------------------------------------------

class TestBuildWikiDryRun(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.memory_dir = self.tmp / "memory"
        self.memory_dir.mkdir()
        (self.memory_dir / "topic-9999.md").write_text(_MINIMAL_MEMORY, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _run(self, extra_args=None):
        bw = _load("build_wiki", "build-wiki.py")
        argv = ["build-wiki.py", "--memory-dir", str(self.memory_dir), "--dry-run"]
        if extra_args:
            argv += extra_args
        out = io.StringIO()
        with patch.object(sys, "argv", argv), patch("sys.stdout", out):
            ret = bw.main()
        return ret, out.getvalue()

    def test_returns_zero(self):
        ret, _ = self._run()
        self.assertEqual(ret, 0)

    def test_wiki_dir_not_created(self):
        self._run()
        self.assertFalse(
            (self.memory_dir / "wiki").exists(),
            "wiki/ directory must NOT be created in dry-run mode",
        )

    def test_output_contains_dry_run_marker(self):
        _, out = self._run()
        self.assertIn("[dry-run]", out)

    def test_output_contains_no_files_written(self):
        _, out = self._run()
        self.assertIn("No files written", out)

    def test_output_shows_would_build_summary(self):
        _, out = self._run()
        self.assertIn("Topics:", out)
        self.assertIn("Total facts:", out)

    def test_clean_flag_does_not_remove_existing_wiki_dir(self):
        """--clean --dry-run must not delete an existing wiki/ directory."""
        wiki_dir = self.memory_dir / "wiki"
        wiki_dir.mkdir()
        sentinel = wiki_dir / "sentinel.md"
        sentinel.write_text("keep me", encoding="utf-8")

        self._run(["--clean"])

        self.assertTrue(sentinel.exists(), "--clean --dry-run must not remove existing wiki/")

    def test_no_wiki_meta_json_created(self):
        self._run()
        self.assertFalse(
            (self.memory_dir / "wiki" / "WIKI_META.json").exists(),
            "WIKI_META.json must NOT be created in dry-run mode",
        )


# ---------------------------------------------------------------------------
# archive-batch-v2 --write --dry-run
# ---------------------------------------------------------------------------

class TestArchiveBatchV2DryRun(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.memory_dir = self.tmp / "memory"
        self.memory_dir.mkdir()
        self.facts_file = self.tmp / "facts.txt"
        self.facts_file.write_text(
            "- Dry-run fact one: agent must check schema\n"
            "- Dry-run fact two: risk=low required for promotion\n",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _run(self):
        ab = _load("archive_batch_v2", "archive-batch-v2.py")
        fake_messages = [
            {"role": "user", "text": "hello", "timestamp": "2026-01-01T00:00:00Z"},
        ]
        argv = [
            "archive-batch-v2.py", "9999",
            "--write", str(self.facts_file),
            "--memory-dir", str(self.memory_dir),
            "--dry-run",
        ]
        out = io.StringIO()
        with (
            patch.object(sys, "argv", argv),
            patch.object(ab, "load_messages", return_value=(fake_messages, 1, 0, [])),
            patch.object(ab, "load_progress", return_value={}),
            patch("sys.stdout", out),
        ):
            ret = ab.main()
        return ret, out.getvalue()

    def test_returns_zero(self):
        ret, _ = self._run()
        self.assertEqual(ret, 0)

    def test_memory_file_not_created(self):
        self._run()
        self.assertFalse(
            (self.memory_dir / "topic-9999.md").exists(),
            "memory file must NOT be created in dry-run mode",
        )

    def test_audit_log_not_created(self):
        self._run()
        self.assertFalse(
            (self.memory_dir / "raw").exists(),
            "L0 audit log directory must NOT be created in dry-run mode",
        )

    def test_memory_dir_remains_empty(self):
        self._run()
        memory_children = list(self.memory_dir.iterdir())
        self.assertEqual(memory_children, [], "memory_dir must remain empty in dry-run mode")

    def test_output_contains_dry_run_marker(self):
        _, out = self._run()
        self.assertIn("[dry-run]", out)

    def test_output_contains_no_files_written(self):
        _, out = self._run()
        self.assertIn("No files written", out)

    def test_output_shows_fact_count(self):
        _, out = self._run()
        self.assertIn("facts", out)
        self.assertIn("2", out)  # two non-empty lines in facts.txt

    def test_output_shows_audit_not_written(self):
        _, out = self._run()
        self.assertIn("audit", out.lower())
        self.assertIn("NOT written", out)

    def test_output_shows_progress_not_updated(self):
        _, out = self._run()
        self.assertIn("Progress", out)
        self.assertIn("NOT updated", out)


# ---------------------------------------------------------------------------
# manage-candidates --promote-auto --dry-run
# ---------------------------------------------------------------------------

class TestPromoteAutoDryRun(unittest.TestCase):
    def setUp(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("pyyaml not installed")

        import yaml

        self.tmp = Path(tempfile.mkdtemp())
        self.memory_dir = self.tmp / "memory"
        candidates_dir = self.memory_dir / "candidates"
        candidates_dir.mkdir(parents=True)

        # Correct filename: candidates_file() returns topic-{id}-candidates.yaml
        self.candidates_file = candidates_dir / "topic-9999-candidates.yaml"

        # Use build_candidate_v1() so the candidate is schema-v1 valid and
        # passes all can_auto_promote() gates (risk=low, confidence=high,
        # fact_type=process, evidence non-empty).
        mc = _load("manage_candidates", "manage-candidates.py")
        evidence = [mc.make_evidence_entry("session_history", "batch 0", "batch:0:msg:1")]
        candidate = mc.build_candidate_v1(
            topic_id="9999",
            fact_type="process",
            claim="Agent validates inputs before processing.",
            confidence="high",
            risk="low",
            evidence=evidence,
            created_by="test",
        )
        self.candidates_file.write_text(
            yaml.dump([candidate]), encoding="utf-8"
        )

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_candidates_file_not_modified(self):
        mc = _load("manage_candidates", "manage-candidates.py")
        mtime_before = self.candidates_file.stat().st_mtime

        out = io.StringIO()
        with patch("sys.stdout", out):
            mc.cmd_promote_auto(
                topic_id="9999",
                memory_dir=self.memory_dir,
                agents_base=self.tmp / "agents",
                dry_run=True,
            )

        mtime_after = self.candidates_file.stat().st_mtime
        self.assertEqual(
            mtime_before, mtime_after,
            "candidates file must NOT be modified in --promote-auto --dry-run",
        )

    def test_candidate_status_unchanged(self):
        import yaml
        mc = _load("manage_candidates", "manage-candidates.py")

        out = io.StringIO()
        with patch("sys.stdout", out):
            mc.cmd_promote_auto(
                topic_id="9999",
                memory_dir=self.memory_dir,
                agents_base=self.tmp / "agents",
                dry_run=True,
            )

        data = yaml.safe_load(self.candidates_file.read_text(encoding="utf-8"))
        self.assertEqual(
            data[0]["status"],
            "candidate",
            "candidate status must remain 'candidate' after dry-run promote-auto",
        )

    def test_dry_run_produces_no_mutation(self):
        """Whether or not candidates qualify, dry_run=True must never modify files.

        cmd_promote_auto may print '[dry-run] No changes written.' when candidates
        qualify, or 'nothing to auto-promote.' when none do — both are acceptable
        non-mutating outcomes. We verify the call completes without raising and
        that the output is one of the two expected messages.
        """
        mc = _load("manage_candidates", "manage-candidates.py")
        out = io.StringIO()
        with patch("sys.stdout", out):
            mc.cmd_promote_auto(
                topic_id="9999",
                memory_dir=self.memory_dir,
                agents_base=self.tmp / "agents",
                dry_run=True,
            )
        output = out.getvalue().lower()
        self.assertTrue(
            "dry-run" in output or "nothing to auto-promote" in output,
            f"Unexpected output from cmd_promote_auto(dry_run=True): {out.getvalue()!r}",
        )


# ---------------------------------------------------------------------------
# archive-batch-v2 --write without session files (A5)
# ---------------------------------------------------------------------------

class TestWriteWithoutSessions(unittest.TestCase):
    """Prove --write works even when agents_base contains no session files."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.memory_dir = self.tmp / "memory"
        self.memory_dir.mkdir()
        self.agents_base = self.tmp / "no_sessions_here"  # intentionally absent
        self.progress_dir = self.tmp / "progress"
        self.progress_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _run_write(self, facts_text: str, extra_args=None) -> tuple[int, str]:
        ab = _load("archive_batch_v2", "archive-batch-v2.py")
        facts_file = self.tmp / "facts.txt"
        facts_file.write_text(facts_text, encoding="utf-8")
        argv = [
            "archive-batch-v2.py",
            "9999",
            "--write", str(facts_file),
            "--memory-dir", str(self.memory_dir),
            "--agents-base", str(self.agents_base),
            "--progress-dir", str(self.progress_dir),
            "--session-id", "test-nosession",
            "--batch", "0",
        ]
        if extra_args:
            argv += extra_args
        out = io.StringIO()
        with patch.object(sys, "argv", argv), patch("sys.stdout", out):
            ret = ab.main()
        return ret, out.getvalue()

    def test_write_succeeds_without_agents_base(self):
        """--write with numeric topic_id must succeed even if agents_base doesn't exist."""
        facts = "- fact one: system works without session files\n- fact two: A5 decoupled\n"
        ret, _ = self._run_write(facts)
        self.assertEqual(ret, 0)

    def test_write_creates_memory_file(self):
        """Written facts must appear in the memory file."""
        facts = "- decoupled write: no sessions needed\n"
        self._run_write(facts)
        mem = self.memory_dir / "topic-9999.md"
        self.assertTrue(mem.exists(), "Memory file must be created by --write")
        content = mem.read_text()
        self.assertIn("decoupled write", content)

    def test_write_dry_run_without_agents_base(self):
        """--dry-run + --write must also work without session files."""
        facts = "- dry fact\n"
        ret, out = self._run_write(facts, extra_args=["--dry-run"])
        self.assertEqual(ret, 0)
        self.assertIn("dry-run", out)
        mem = self.memory_dir / "topic-9999.md"
        self.assertFalse(mem.exists(), "dry-run must not create memory file")

    def test_agents_base_dir_never_created(self):
        """--write must not create or touch agents_base at all."""
        facts = "- standalone write\n"
        self._run_write(facts)
        self.assertFalse(
            self.agents_base.exists(),
            "agents_base directory must not be created by --write mode",
        )


if __name__ == "__main__":
    unittest.main()
