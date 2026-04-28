"""
tests/test_name_resolver_e2e.py — E2E tests for archive-batch-v2.py topic name resolver.

Tests that topic names resolve correctly to numeric IDs by scanning
real OpenClaw session files on the current machine.

Marked @pytest.mark.e2e — skipped by default (requires live ~/.openclaw/agents/ data).
Run with:  pytest -m e2e
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "context_access" / "archive-batch-v2.py"
AGENTS_DIR = Path.home() / ".openclaw" / "agents"

pytestmark = pytest.mark.e2e


def _skip_if_no_agents():
    if not AGENTS_DIR.is_dir() or not any(AGENTS_DIR.iterdir()):
        pytest.skip("~/.openclaw/agents/ not found or empty — live data required")


def run(*args: str) -> tuple[str, str, int]:
    r = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def test_exact_lowercase_name() -> None:
    """'telemost' (lowercase) resolves to 7301."""
    _skip_if_no_agents()
    _, err, rc = run("telemost", "--status")
    assert rc == 0, f"Expected rc=0, got {rc}. stderr: {err}"
    assert "7301" in err, f"Expected '7301' in stderr, got: {err}"


def test_numeric_passthrough() -> None:
    """Numeric topic ID '7301' passes through unchanged."""
    _skip_if_no_agents()
    out, err, rc = run("7301", "--status")
    assert rc == 0, f"Expected rc=0, got {rc}. stderr: {err}"
    assert "7301" in out, f"Expected 'topic:7301' in stdout, got: {out}"


def test_case_insensitive() -> None:
    """'Telemost' (capital T) resolves to 7301 via case-insensitive match."""
    _skip_if_no_agents()
    _, err, rc = run("Telemost", "--status")
    assert rc == 0, f"Expected rc=0, got {rc}. stderr: {err}"
    assert "7301" in err, f"Expected '7301' in stderr, got: {err}"


def test_unknown_name_exits_nonzero() -> None:
    """An unknown topic name exits with non-zero and prints helpful message."""
    _skip_if_no_agents()
    _, err, rc = run("this-topic-does-not-exist-xyz", "--status")
    assert rc != 0, f"Expected non-zero rc for unknown topic, got {rc}"
    assert "not found" in err.lower() or "error" in err.lower(), \
        f"Expected error message, got: {err}"
