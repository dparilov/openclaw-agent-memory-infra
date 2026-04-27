#!/usr/bin/env python3
"""E2E tests for archive-batch-v2.py topic name resolver.

Tests that topic names resolve correctly to numeric IDs by scanning
real OpenClaw session files on the current machine.

Requires: ~/.openclaw/agents/ with at least one session for the telemost topic (7301).
"""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "context_access" / "archive-batch-v2.py"


def run(*args: str) -> tuple[str, str, int]:
    r = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def test_exact_lowercase_name() -> None:
    """'telemost' (lowercase) resolves to 7301."""
    _, err, rc = run("telemost", "--status")
    assert rc == 0, f"Expected rc=0, got {rc}. stderr: {err}"
    assert "7301" in err, f"Expected '7301' in stderr, got: {err}"
    print(f"PASS test_exact_lowercase_name: {err.splitlines()[0]}")


def test_numeric_passthrough() -> None:
    """Numeric topic ID '7301' passes through unchanged."""
    out, err, rc = run("7301", "--status")
    assert rc == 0, f"Expected rc=0, got {rc}. stderr: {err}"
    assert "7301" in out, f"Expected 'topic:7301' in stdout, got: {out}"
    print("PASS test_numeric_passthrough")


def test_case_insensitive() -> None:
    """'Telemost' (capital T) resolves to 7301 via case-insensitive match."""
    _, err, rc = run("Telemost", "--status")
    assert rc == 0, f"Expected rc=0, got {rc}. stderr: {err}"
    assert "7301" in err, f"Expected '7301' in stderr, got: {err}"
    print(f"PASS test_case_insensitive: {err.splitlines()[0]}")


def test_unknown_name_exits_nonzero() -> None:
    """An unknown topic name exits with non-zero and prints helpful message."""
    _, err, rc = run("this-topic-does-not-exist-xyz", "--status")
    assert rc != 0, f"Expected non-zero rc for unknown topic, got {rc}"
    assert "not found" in err.lower() or "error" in err.lower(), \
        f"Expected error message, got: {err}"
    print("PASS test_unknown_name_exits_nonzero")


if __name__ == "__main__":
    tests = [
        test_exact_lowercase_name,
        test_numeric_passthrough,
        test_case_insensitive,
        test_unknown_name_exits_nonzero,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failed += 1
    print()
    if failed:
        print(f"{failed}/{len(tests)} tests FAILED")
        sys.exit(1)
    else:
        print(f"All {len(tests)} tests passed.")
