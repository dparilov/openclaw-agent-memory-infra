#!/usr/bin/env python3
"""Minimal dependency-free tests for archive-batch-v2.py."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "context_access" / "archive-batch-v2.py"
FIXTURE_AGENTS = ROOT / "tests" / "context_access" / "fixtures" / "agents"


def run_cmd(*args: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [sys.executable, str(SCRIPT), *args, "--agents-base", str(FIXTURE_AGENTS), "--progress-dir", tmp]
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            raise AssertionError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
        return proc.stdout


def assert_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"Expected to find {needle!r} in:\n{text}")


def assert_not_contains(text: str, needle: str) -> None:
    if needle in text:
        raise AssertionError(f"Did not expect to find {needle!r} in:\n{text}")


def test_status_dedupes_fixture() -> None:
    out = run_cmd("7301", "--status")
    assert_contains(out, "Raw messages  : 8")
    assert_contains(out, "Deduped msgs   : 5")
    assert_contains(out, "Duplicates     : 3")
    assert_contains(out, "Batches done  : 0/1")


def test_total_uses_deduped_count() -> None:
    out = run_cmd("7301", "--total")
    assert_contains(out, "raw_msgs:8")
    assert_contains(out, "deduped_msgs:5")
    assert_contains(out, "duplicates:3")
    assert_contains(out, "total_batches:1")


def test_batch_has_no_duplicate_telegram_message_or_empty_assistant() -> None:
    out = run_cmd("7301", "--batch", "0", "--max-text", "0")
    if out.count("telegram:-1003596522926:7301:7302:user") != 1:
        raise AssertionError("message_id 7302 should appear exactly once")
    assert_not_contains(out, "a-empty")
    assert_not_contains(out, "fallback:assistant:1775984340000:e3b0c44298fc1c149afbf4c8")


def main() -> int:
    tests = [
        test_status_dedupes_fixture,
        test_total_uses_deduped_count,
        test_batch_has_no_duplicate_telegram_message_or_empty_assistant,
    ]
    for test in tests:
        test()
        print(f"ok - {test.__name__}")
    print(f"{len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
