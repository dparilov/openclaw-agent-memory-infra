"""
tests/test_onboard_project.py — Unit tests for scripts/onboard-project.py

Tests cover:
- Argument validation
- URL normalisation
- Tool diff classification
- Safe staging allowlist
- PROJECT_TARGET_ACK formatting
- Final report section presence

All subprocess calls are mocked — no real OpenClaw install required.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Load onboard-project.py dynamically (hyphen in filename prevents normal import)
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "onboard_project",
    Path(__file__).parent.parent / "scripts" / "onboard-project.py",
)
op = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(op)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# 1. Argument validation
# ---------------------------------------------------------------------------

class TestArgValidation:
    REQUIRED = [
        "--target", "/tmp/fake-repo",
        "--repo", "https://github.com/test/repo",
        "--chat-id", "-123",
        "--infra-topic", "1",
        "--coder-topic", "2",
        "--reviewer-topic", "3",
        "--escalation", "@user",
    ]

    def test_all_required_present(self):
        parser = op.build_parser()
        args = parser.parse_args(self.REQUIRED)
        assert args.target == "/tmp/fake-repo"
        assert args.mode == "fast"

    def test_missing_target_exits(self):
        parser = op.build_parser()
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["--repo", "https://github.com/x/y",
                               "--chat-id", "1", "--infra-topic", "1",
                               "--coder-topic", "2", "--reviewer-topic", "3",
                               "--escalation", "@u"])
        assert exc.value.code != 0

    def test_missing_repo_exits(self):
        parser = op.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--target", "/tmp",
                               "--chat-id", "1", "--infra-topic", "1",
                               "--coder-topic", "2", "--reviewer-topic", "3",
                               "--escalation", "@u"])

    def test_unimplemented_mode_returns_1(self):
        for mode in ("full", "repair", "audit"):
            rc = op.main(self.REQUIRED + ["--mode", mode])
            assert rc == op.EXIT_VALIDATION

    def test_default_mode_is_fast(self):
        parser = op.build_parser()
        args = parser.parse_args(self.REQUIRED)
        assert args.mode == "fast"

    def test_sync_tools_default_false(self):
        parser = op.build_parser()
        args = parser.parse_args(self.REQUIRED)
        assert args.sync_tools is False

    def test_create_pr_default_false(self):
        parser = op.build_parser()
        args = parser.parse_args(self.REQUIRED)
        assert args.create_pr is False


# ---------------------------------------------------------------------------
# 2. URL normalisation
# ---------------------------------------------------------------------------

class TestNormaliseRepoUrl:
    def test_https_plain(self):
        assert op.normalise_repo_url("https://github.com/dparilov/olcRTC") == \
               "https://github.com/dparilov/olcRTC"

    def test_https_with_git_suffix(self):
        assert op.normalise_repo_url("https://github.com/dparilov/olcRTC.git") == \
               "https://github.com/dparilov/olcRTC"

    def test_ssh_format(self):
        assert op.normalise_repo_url("git@github.com:dparilov/olcRTC.git") == \
               "https://github.com/dparilov/olcRTC"

    def test_ssh_without_git_suffix(self):
        assert op.normalise_repo_url("git@github.com:dparilov/olcRTC") == \
               "https://github.com/dparilov/olcRTC"

    def test_all_three_normalise_to_same(self):
        urls = [
            "https://github.com/dparilov/olcRTC",
            "https://github.com/dparilov/olcRTC.git",
            "git@github.com:dparilov/olcRTC.git",
        ]
        normalised = {op.normalise_repo_url(u) for u in urls}
        assert len(normalised) == 1, f"Expected 1 unique form, got: {normalised}"

    def test_trailing_slash_stripped(self):
        assert op.normalise_repo_url("https://github.com/org/repo/") == \
               "https://github.com/org/repo"


# ---------------------------------------------------------------------------
# 3. Tool diff classification
# ---------------------------------------------------------------------------

class TestComputeToolDiff:
    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_missing_in_dest_is_copy(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        self._write(src / "foo.py", "# foo")
        diffs = op.compute_tool_diff(src, dst)
        assert any(d.filename == "foo.py" and d.action == "COPY" for d in diffs)

    def test_identical_content_is_unchanged(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        self._write(src / "foo.py", "# foo")
        self._write(dst / "foo.py", "# foo")
        diffs = op.compute_tool_diff(src, dst)
        assert any(d.filename == "foo.py" and d.action == "UNCHANGED" for d in diffs)

    def test_different_content_is_update(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        self._write(src / "foo.py", "# version 2")
        self._write(dst / "foo.py", "# version 1")
        diffs = op.compute_tool_diff(src, dst)
        assert any(d.filename == "foo.py" and d.action == "UPDATE" for d in diffs)

    def test_extra_in_dest_is_extra(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        self._write(src / "foo.py", "# foo")
        self._write(dst / "foo.py", "# foo")
        self._write(dst / "extra.py", "# extra")
        diffs = op.compute_tool_diff(src, dst)
        assert any(d.filename == "extra.py" and d.action == "EXTRA" for d in diffs)

    def test_empty_dest_all_copy(self, tmp_path):
        src = tmp_path / "src"
        for name in ("a.py", "b.py", "c.py"):
            self._write(src / name, f"# {name}")
        diffs = op.compute_tool_diff(src, tmp_path / "dst")
        actions = {d.action for d in diffs}
        assert actions == {"COPY"}

    def test_non_py_files_ignored(self, tmp_path):
        src = tmp_path / "src"
        self._write(src / "foo.py", "# py")
        self._write(src / "foo.txt", "text")
        self._write(src / "foo.sh", "#!/bin/bash")
        diffs = op.compute_tool_diff(src, tmp_path / "dst")
        names = {d.filename for d in diffs}
        assert "foo.txt" not in names
        assert "foo.sh" not in names
        assert "foo.py" in names


# ---------------------------------------------------------------------------
# 4. Safe staging allowlist
# ---------------------------------------------------------------------------

class TestIsSafeToStage:
    def test_valid_py_in_tools(self):
        assert op.is_safe_to_stage(".agent/tools/context_access/foo.py") is True

    def test_valid_py_another_name(self):
        assert op.is_safe_to_stage(".agent/tools/context_access/archive-batch-v2.py") is True

    def test_memory_file_rejected(self):
        assert op.is_safe_to_stage(".agent/memory/topic-7301.md") is False

    def test_agent_context_rejected(self):
        assert op.is_safe_to_stage(".agent/AGENT_CONTEXT.md") is False

    def test_non_py_in_tools_rejected(self):
        assert op.is_safe_to_stage(".agent/tools/context_access/foo.sh") is False

    def test_subdirectory_rejected(self):
        assert op.is_safe_to_stage(".agent/tools/context_access/sub/foo.py") is False

    def test_arbitrary_repo_file_rejected(self):
        assert op.is_safe_to_stage("main.go") is False

    def test_pycache_rejected(self):
        assert op.is_safe_to_stage(".agent/tools/context_access/__pycache__/foo.pyc") is False

    def test_locks_file_rejected(self):
        assert op.is_safe_to_stage(".agent/tools/context_access/.locks/foo.py") is False


# ---------------------------------------------------------------------------
# 5. PROJECT_TARGET_ACK formatting
# ---------------------------------------------------------------------------

class TestFormatAck:
    def test_all_required_fields_present(self):
        ack = op.format_ack(
            repo="https://github.com/org/repo",
            target=Path("/path/to/project"),
            chat_id="-123456",
            infra_topic="15222",
            coder_topic="7301",
            reviewer_topic="13350",
            escalation="@pariloff",
        )
        assert "PROJECT_TARGET_ACK" in ack
        assert "mode: C" in ack
        assert "repo_url: https://github.com/org/repo" in ack
        assert "local_path: /path/to/project" in ack
        assert "chat_id: -123456" in ack
        assert "infra_topic: 15222" in ack
        assert "coder_topic: 7301" in ack
        assert "reviewer_topic: 13350" in ack
        assert "escalation: @pariloff" in ack

    def test_no_secrets_in_output(self):
        ack = op.format_ack(
            repo="https://github.com/org/repo",
            target=Path("/path"),
            chat_id="-1",
            infra_topic="1",
            coder_topic="2",
            reviewer_topic="3",
            escalation="@u",
        )
        assert "token" not in ack.lower()
        assert "password" not in ack.lower()
        assert "secret" not in ack.lower()


# ---------------------------------------------------------------------------
# 6. Final report section presence
# ---------------------------------------------------------------------------

class TestFormatReport:
    def _make_report(self, **overrides) -> str:
        defaults: dict = dict(
            mode="fast",
            target=Path("/tmp/proj"),
            repo="https://github.com/org/repo",
            chat_id="-1",
            infra_topic="15222",
            coder_topic="7301",
            reviewer_topic="13350",
            escalation="@u",
            preflight=[op.CheckResult("gh auth status", "PASS", "ok")],
            scaffold=[op.CheckResult(".agent exists", "PASS", "/tmp/proj/.agent")],
            diffs=[op.ToolDiff("foo.py", "UNCHANGED", "")],
            compile_check=op.CheckResult("py_compile all tools", "PASS", "1 files ok"),
            help_check=op.CheckResult("initial-index.py --help", "PASS", "Bootstrap..."),
            git_plan_cmds=["git -C /tmp/proj checkout -b infra/sync-agent-tools-2026-05-04"],
            git_plan_warnings=[],
            git_executed=None,
            git_message="",
            create_pr=False,
            sync_tools=False,
            branch="infra/sync-agent-tools-2026-05-04",
            index_results=[op.IndexResult("7301", "coder", "PASS", "dry-run ok")],
            warnings=["some warning"],
            blockers=[],
            next_steps=["do something next"],
        )
        defaults.update(overrides)
        return op.format_report(**defaults)

    def test_header_present(self):
        assert "ONBOARD PROJECT REPORT" in self._make_report()

    def test_project_target_ack_present(self):
        assert "PROJECT_TARGET_ACK" in self._make_report()

    def test_preflight_section_present(self):
        assert "Preflight" in self._make_report()

    def test_scaffold_section_present(self):
        assert "Scaffold" in self._make_report()

    def test_tool_sync_section_present(self):
        assert "Tool Sync" in self._make_report()

    def test_git_pr_section_present(self):
        assert "Git / PR" in self._make_report()

    def test_index_dry_run_section_present(self):
        assert "Index Dry-Run" in self._make_report()

    def test_warnings_section_present(self):
        assert "Warnings:" in self._make_report()

    def test_blockers_section_present(self):
        assert "Blockers:" in self._make_report()

    def test_next_section_present(self):
        assert "Next:" in self._make_report()

    def test_dry_run_label_in_tool_sync(self):
        assert "dry-run" in self._make_report(sync_tools=False)

    def test_no_dry_run_label_when_synced(self):
        assert "UNCHANGED (dry-run)" not in self._make_report(sync_tools=True)

    def test_create_pr_false_shows_skip(self):
        assert "--create-pr not passed" in self._make_report(create_pr=False)

    def test_topics_in_header(self):
        r = self._make_report()
        assert "15222" in r
        assert "7301" in r
        assert "13350" in r


# ---------------------------------------------------------------------------
# 7. Table formatting helper
# ---------------------------------------------------------------------------

class TestTable:
    def test_basic_table(self):
        result = op._table(["A", "B"], [["hello", "world"], ["x", "y"]])
        assert "hello" in result
        assert "world" in result

    def test_column_widths_aligned(self):
        result = op._table(["Name", "Status"], [["short", "PASS"], ["a very long name here", "FAIL"]])
        lines = result.splitlines()
        lengths = {len(line) for line in lines}
        assert len(lengths) == 1, f"Table lines have inconsistent lengths: {lengths}"
