"""B4: non-live smoke test / setup verification (19 tests).

These tests exercise the --test / --smoke-test flag added in B4.
No live Telegram connection is required.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SETUP_SH = REPO_ROOT / "setup.sh"


def run_setup(*extra_args: str, target: Path | None = None) -> subprocess.CompletedProcess:
    cmd = ["bash", str(SETUP_SH)]
    if target is not None:
        cmd += ["--target", str(target)]
    cmd += list(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True)


# ── Requires --target ─────────────────────────────────────────────────────────


class TestSmokeRequiresTarget:
    def test_smoke_test_without_target_exits_nonzero(self):
        result = run_setup("--test")
        assert result.returncode != 0

    def test_smoke_test_without_target_prints_error(self):
        result = run_setup("--test")
        combined = result.stdout + result.stderr
        assert "required" in combined.lower() or "error" in combined.lower()


# ── --smoke-test alias ────────────────────────────────────────────────────────


class TestSmokeAlias:
    def test_smoke_test_alias_not_rejected(self, tmp_path):
        result = run_setup("--smoke-test", target=tmp_path)
        assert "unknown option" not in result.stderr.lower()
        assert "unknown option" not in result.stdout.lower()


# ── Output format ─────────────────────────────────────────────────────────────


class TestSmokeOutputFormat:
    def test_output_contains_pass_label(self, tmp_path):
        result = run_setup("--test", target=tmp_path)
        assert "  PASS  " in result.stdout

    def test_output_contains_summary_counts(self, tmp_path):
        result = run_setup("--test", target=tmp_path)
        assert "PASS:" in result.stdout
        assert "WARN:" in result.stdout
        assert "FAIL:" in result.stdout

    def test_summary_line_format(self, tmp_path):
        """Summary line must look like: '  PASS: N  WARN: N  FAIL: N'"""
        result = run_setup("--test", target=tmp_path)
        import re
        assert re.search(r"PASS:\s*\d+\s+WARN:\s*\d+\s+FAIL:\s*\d+", result.stdout)

    def test_warn_alone_does_not_fail_smoke(self, tmp_path):
        """If only WARNs (e.g. pyrogram absent), exit code must be 0."""
        try:
            import pyrogram  # noqa: F401
        except ImportError:
            result = run_setup("--test", target=tmp_path)
            if "  WARN  pyrogram" in result.stdout and "  FAIL  " not in result.stdout:
                assert result.returncode == 0


# ── Structure checks ──────────────────────────────────────────────────────────


class TestSmokeStructureChecks:
    def test_all_7_dirs_mentioned_in_output(self, tmp_path):
        result = run_setup("--test", target=tmp_path)
        for d in ["memory", "checkpoints", "tasks", "reviews", "decisions", "runbooks", "handoffs"]:
            assert f".agent/{d}/" in result.stdout, f"missing .agent/{d}/ in output"

    def test_no_structure_fail_after_full_bootstrap(self, tmp_path):
        """After setup, all 7 dirs exist — no .agent/<dir>/ FAIL lines."""
        result = run_setup("--test", target=tmp_path)
        for d in ["memory", "checkpoints", "tasks", "reviews", "decisions", "runbooks", "handoffs"]:
            assert f"  FAIL  .agent/{d}/" not in result.stdout

    def test_fails_on_missing_structure(self, tmp_path):
        """--dry-run --test: dirs never created → smoke test reports FAILs."""
        result = run_setup("--dry-run", "--test", target=tmp_path)
        assert result.returncode != 0
        assert "  FAIL  .agent/" in result.stdout

    def test_fail_exit_code_nonzero(self, tmp_path):
        """Missing structure must produce non-zero exit."""
        result = run_setup("--dry-run", "--test", target=tmp_path)
        assert result.returncode != 0


# ── Telegram behaviour ────────────────────────────────────────────────────────


class TestSmokeTelegramBehavior:
    def test_no_telegram_required_by_default(self, tmp_path):
        """Smoke passes (exit 0) even when pyrogram is absent."""
        try:
            import pyrogram  # noqa: F401
        except ImportError:
            result = run_setup("--test", target=tmp_path)
            assert "  FAIL  pyrogram" not in result.stdout
            assert result.returncode == 0

    def test_require_telegram_flag_accepted(self, tmp_path):
        result = run_setup("--test", "--require-telegram", target=tmp_path)
        assert "unknown option" not in result.stderr.lower()

    def test_require_telegram_promotes_pyrogram_to_fail(self, tmp_path):
        """If pyrogram absent + --require-telegram → FAIL line + exit 1."""
        try:
            import pyrogram  # noqa: F401
            pytest.skip("pyrogram is installed; cannot test its absence")
        except ImportError:
            pass
        result = run_setup("--test", "--require-telegram", target=tmp_path)
        assert result.returncode != 0
        assert "  FAIL  pyrogram" in result.stdout

    def test_pyrogram_absence_is_warn_without_flag(self, tmp_path):
        try:
            import pyrogram  # noqa: F401
            pytest.skip("pyrogram is installed")
        except ImportError:
            pass
        result = run_setup("--test", target=tmp_path)
        assert "  WARN  pyrogram" in result.stdout
        assert "  FAIL  pyrogram" not in result.stdout


# ── Tool --help checks ────────────────────────────────────────────────────────


class TestSmokeToolHelp:
    TOOLS = [
        "read-topic.py",
        "archive-batch-v2.py",
        "manage-candidates.py",
        "build-wiki.py",
    ]

    def test_all_4_tools_mentioned_in_output(self, tmp_path):
        result = run_setup("--test", target=tmp_path)
        for tool in self.TOOLS:
            assert tool in result.stdout, f"{tool} not mentioned in smoke output"

    def test_tools_pass_with_source_fallback(self, tmp_path):
        """Without --install-scripts copy, source fallback must make tools PASS."""
        result = run_setup("--test", target=tmp_path)
        for tool in self.TOOLS:
            assert f"  PASS  {tool}" in result.stdout, f"{tool} did not PASS"


# ── Python / PyYAML checks ────────────────────────────────────────────────────


class TestSmokePythonCheck:
    def test_python_version_mentioned_in_output(self, tmp_path):
        result = run_setup("--test", target=tmp_path)
        assert "Python" in result.stdout

    def test_pyyaml_mentioned_in_output(self, tmp_path):
        result = run_setup("--test", target=tmp_path)
        assert "PyYAML" in result.stdout

    def test_python_passes_when_gte_310(self, tmp_path):
        import sys
        if sys.version_info < (3, 10):
            pytest.skip("Python < 3.10 on this runner")
        result = run_setup("--test", target=tmp_path)
        assert "  PASS  Python >= 3.10" in result.stdout


# ── config.yaml check ─────────────────────────────────────────────────────────


class TestSmokeConfigYaml:
    def test_config_yaml_mentioned_in_output(self, tmp_path):
        result = run_setup("--test", target=tmp_path)
        assert ".agent/config.yaml" in result.stdout

    def test_config_yaml_not_failed_after_bootstrap(self, tmp_path):
        result = run_setup("--test", target=tmp_path)
        assert "FAIL  .agent/config.yaml" not in result.stdout

    def test_dry_run_fails_on_missing_config_yaml(self, tmp_path):
        result = run_setup("--dry-run", "--test", target=tmp_path)
        assert result.returncode != 0
        assert "FAIL  .agent/config.yaml" in result.stdout
