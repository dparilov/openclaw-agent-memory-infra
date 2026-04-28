#!/usr/bin/env python3
"""Tests for setup.sh B1+B2: bootstrap structure and install modes."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
SETUP = REPO / "setup.sh"


def run_setup(*args, check=False):
    return subprocess.run(
        ["bash", str(SETUP)] + list(args),
        capture_output=True, text=True, check=check,
    )


class TestDryRun(unittest.TestCase):
    def test_dry_run_creates_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "proj"
            r = run_setup("--target", str(target), "--dry-run")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(target.exists(), "dry-run must not create any dirs")

    def test_dry_run_prints_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_setup("--target", str(tmp) + "/new", "--dry-run")
            self.assertIn("[dry-run]", r.stdout)

    def test_dry_run_with_install_scripts_creates_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "proj"
            r = run_setup("--target", str(target), "--install-scripts", "copy", "--dry-run")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse(target.exists(), "dry-run must not create any dirs even with --install-scripts")


class TestBootstrapStructure(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.target = Path(self._td.name) / "proj"
        result = run_setup("--target", str(self.target), "--topic-id", "9999")
        self.assertEqual(result.returncode, 0, result.stderr)

    def tearDown(self):
        self._td.cleanup()

    def _assert_dir(self, *parts):
        d = self.target.joinpath(*parts)
        self.assertTrue(d.is_dir(), f"Expected dir: {d}")

    def _assert_file(self, *parts):
        f = self.target.joinpath(*parts)
        self.assertTrue(f.is_file(), f"Expected file: {f}")

    # B1 — directory structure
    def test_memory_raw(self):          self._assert_dir(".agent", "memory", "raw")
    def test_memory_candidates(self):   self._assert_dir(".agent", "memory", "candidates")
    def test_memory_working(self):      self._assert_dir(".agent", "memory", "working")
    def test_memory_promoted(self):     self._assert_dir(".agent", "memory", "promoted")
    def test_memory_reports(self):      self._assert_dir(".agent", "memory", "reports")
    def test_memory_wiki(self):         self._assert_dir(".agent", "memory", "wiki")
    def test_checkpoints(self):         self._assert_dir(".agent", "checkpoints")
    def test_tasks(self):               self._assert_dir(".agent", "tasks")
    def test_reviews(self):             self._assert_dir(".agent", "reviews")
    def test_decisions(self):           self._assert_dir(".agent", "decisions")
    def test_runbooks(self):            self._assert_dir(".agent", "runbooks")
    def test_handoffs(self):            self._assert_dir(".agent", "handoffs")
    def test_tools_context_access(self):self._assert_dir(".agent", "tools", "context_access")
    def test_locks(self):               self._assert_dir(".agent", ".locks")

    def test_topic_memory_file(self):
        self._assert_file(".agent", "memory", "topic-9999.md")
        txt = (self.target / ".agent" / "memory" / "topic-9999.md").read_text()
        self.assertIn("topic-9999", txt)

    def test_idempotent_no_overwrite(self):
        mem = self.target / ".agent" / "memory" / "topic-9999.md"
        mem.write_text("SENTINEL")
        run_setup("--target", str(self.target), "--topic-id", "9999")
        self.assertEqual(mem.read_text(), "SENTINEL",
                         "Second run must not overwrite existing file without --force")

    def test_force_overwrites(self):
        mem = self.target / ".agent" / "memory" / "topic-9999.md"
        mem.write_text("SENTINEL")
        run_setup("--target", str(self.target), "--topic-id", "9999", "--force")
        self.assertNotEqual(mem.read_text(), "SENTINEL",
                            "--force must overwrite existing file")


class TestInstallScripts(unittest.TestCase):
    EXPECTED = [
        "archive-batch-v2.py", "read-topic.py",
        "manage-candidates.py", "build-wiki.py",
    ]

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.target = Path(self._td.name) / "proj"

    def tearDown(self):
        self._td.cleanup()

    @property
    def tool_dir(self):
        return self.target / ".agent" / "tools" / "context_access"

    def test_copy_mode(self):
        r = run_setup("--target", str(self.target), "--install-scripts", "copy")
        self.assertEqual(r.returncode, 0, r.stderr)
        for script in self.EXPECTED:
            dst = self.tool_dir / script
            self.assertTrue(dst.is_file(), f"Expected copied file: {dst}")
            self.assertFalse(dst.is_symlink(), f"copy must not create symlink: {dst}")

    def test_symlink_mode(self):
        r = run_setup("--target", str(self.target), "--install-scripts", "symlink")
        self.assertEqual(r.returncode, 0, r.stderr)
        for script in self.EXPECTED:
            dst = self.tool_dir / script
            self.assertTrue(dst.exists(), f"Expected symlinked file: {dst}")
            self.assertTrue(dst.is_symlink(), f"symlink mode must create symlink: {dst}")

    def test_none_mode_no_scripts(self):
        r = run_setup("--target", str(self.target), "--install-scripts", "none")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(list(self.tool_dir.glob("*.py")), [],
                         "none mode must not install any .py files")

    def test_no_global_bin_writes(self):
        """B2: setup.sh must never write to ~/.local/bin."""
        local_bin = Path.home() / ".local" / "bin"
        before = set(local_bin.iterdir()) if local_bin.exists() else set()
        run_setup("--target", str(self.target), "--install-scripts", "copy")
        after = set(local_bin.iterdir()) if local_bin.exists() else set()
        new_files = after - before
        self.assertEqual(new_files, set(),
                         f"setup.sh must not write to ~/.local/bin: {new_files}")

    def test_invalid_mode_exits_nonzero(self):
        r = run_setup("--target", str(self.target), "--install-scripts", "global")
        self.assertNotEqual(r.returncode, 0, "invalid --install-scripts value must exit non-zero")


if __name__ == "__main__":
    unittest.main()
