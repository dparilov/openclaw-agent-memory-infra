#!/usr/bin/env python3
"""
tests/test_io_utils.py — verify atomic_write_text and atomic_append_text.

Tests cover:
 - basic round-trip
 - no temp file left on success
 - sequential writers do not lose data
 - lock dir respects OPENCLAW_MEMORY_LOCK_DIR env var
 - nonexistent parent directories are created automatically
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / "scripts" / "context_access"


def _load_io_utils():
    spec = importlib.util.spec_from_file_location("io_utils", SCRIPTS / "io_utils.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["io_utils"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestAtomicWriteText(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.iu = _load_io_utils()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_basic_write(self):
        target = self.tmp / "data.txt"
        self.iu.atomic_write_text(target, "hello world")
        self.assertEqual(target.read_text(), "hello world")

    def test_overwrites_existing(self):
        target = self.tmp / "data.txt"
        target.write_text("old content")
        self.iu.atomic_write_text(target, "new content")
        self.assertEqual(target.read_text(), "new content")

    def test_no_temp_file_left(self):
        target = self.tmp / "data.txt"
        self.iu.atomic_write_text(target, "clean")
        leftover = list(self.tmp.glob(".data.txt.tmp.*"))
        self.assertEqual(leftover, [], "No temp files should remain after successful write")

    def test_creates_parent_dir(self):
        target = self.tmp / "sub" / "deep" / "data.txt"
        self.iu.atomic_write_text(target, "nested")
        self.assertEqual(target.read_text(), "nested")

    def test_sequential_writes_no_lost_data(self):
        """Two sequential atomic_write_text calls must each fully land."""
        target = self.tmp / "seq.txt"
        self.iu.atomic_write_text(target, "first")
        self.iu.atomic_write_text(target, "second")
        self.assertEqual(target.read_text(), "second")

    def test_lock_dir_env_var(self):
        """OPENCLAW_MEMORY_LOCK_DIR controls where lock files are created."""
        lock_dir = self.tmp / "custom_locks"
        target = self.tmp / "data.txt"
        old_env = os.environ.get("OPENCLAW_MEMORY_LOCK_DIR")
        try:
            os.environ["OPENCLAW_MEMORY_LOCK_DIR"] = str(lock_dir)
            self.iu.atomic_write_text(target, "env-lock-test")
            self.assertTrue(lock_dir.exists(), "Custom lock dir must be created")
            lock_files = list(lock_dir.glob("*.lock"))
            self.assertTrue(len(lock_files) >= 1, "Lock file must be created in custom dir")
        finally:
            if old_env is None:
                os.environ.pop("OPENCLAW_MEMORY_LOCK_DIR", None)
            else:
                os.environ["OPENCLAW_MEMORY_LOCK_DIR"] = old_env

    def test_lock_dir_kwarg(self):
        """lock_dir= kwarg routes lock files to the given directory."""
        lock_dir = self.tmp / "kwarg_locks"
        target = self.tmp / "data.txt"
        self.iu.atomic_write_text(target, "kwarg-lock-test", lock_dir=lock_dir)
        self.assertTrue(lock_dir.exists())
        self.assertTrue(any(lock_dir.glob("*.lock")))


class TestAtomicAppendText(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.iu = _load_io_utils()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_append_to_new_file(self):
        target = self.tmp / "log.txt"
        self.iu.atomic_append_text(target, "line1\n")
        self.assertEqual(target.read_text(), "line1\n")

    def test_append_to_existing(self):
        target = self.tmp / "log.txt"
        target.write_text("line1\n")
        self.iu.atomic_append_text(target, "line2\n")
        self.assertEqual(target.read_text(), "line1\nline2\n")

    def test_no_temp_file_left(self):
        target = self.tmp / "log.txt"
        self.iu.atomic_append_text(target, "x\n")
        leftover = list(self.tmp.glob(".log.txt.tmp.*"))
        self.assertEqual(leftover, [], "No temp files should remain after successful append")

    def test_sequential_appends_no_lost_data(self):
        """Ten sequential appends must accumulate all lines — no lost update."""
        target = self.tmp / "audit.log"
        for i in range(10):
            self.iu.atomic_append_text(target, f"entry-{i}\n")
        lines = target.read_text().splitlines()
        self.assertEqual(len(lines), 10, "All 10 append entries must be present")
        for i in range(10):
            self.assertIn(f"entry-{i}", lines, f"entry-{i} missing from audit log")

    def test_two_sequential_writers_no_lost_data(self):
        """Simulate two agents appending sequentially — neither entry lost."""
        target = self.tmp / "shared.log"

        # Agent 1 writes
        self.iu.atomic_append_text(target, "agent-1-fact: uses atomic writes\n")
        # Agent 2 writes immediately after
        self.iu.atomic_append_text(target, "agent-2-fact: no lost updates\n")

        content = target.read_text()
        self.assertIn("agent-1-fact", content, "Agent 1 data must be present")
        self.assertIn("agent-2-fact", content, "Agent 2 data must be present")

    def test_creates_parent_dir(self):
        target = self.tmp / "sub" / "audit.log"
        self.iu.atomic_append_text(target, "ok\n")
        self.assertEqual(target.read_text(), "ok\n")


class TestConcurrentWrites(unittest.TestCase):
    """Prove that concurrent atomic_append_text calls do not lose data."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.iu = _load_io_utils()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_concurrent_appends_no_lost_data(self):
        """20 threads each appending a unique line — all 20 must survive."""
        target = self.tmp / "concurrent.log"
        n_threads = 20
        errors: list[Exception] = []

        def worker(idx: int) -> None:
            try:
                self.iu.atomic_append_text(target, f"thread-{idx:03d}\n")
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(errors, [], f"Worker exceptions: {errors}")
        lines = target.read_text().splitlines()
        self.assertEqual(
            len(lines), n_threads,
            f"Expected {n_threads} lines, got {len(lines)}: {lines}",
        )
        for i in range(n_threads):
            self.assertIn(f"thread-{i:03d}", lines, f"thread-{i:03d} missing")

    def test_concurrent_locked_path_transactions_no_lost_data(self):
        """20 threads doing read→increment→write inside locked_path — final value must be 20."""
        target = self.tmp / "counter.txt"
        target.write_text("0")
        n_threads = 20
        errors: list[Exception] = []

        def worker() -> None:
            try:
                with self.iu.locked_path(target):
                    current = int(target.read_text().strip())
                    self.iu.write_text_in_lock(target, str(current + 1))
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(errors, [], f"Worker exceptions: {errors}")
        final = int(target.read_text().strip())
        self.assertEqual(final, n_threads, f"Counter should be {n_threads}, got {final}")


if __name__ == "__main__":
    unittest.main()
