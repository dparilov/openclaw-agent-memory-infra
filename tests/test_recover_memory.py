"""
tests/test_recover_memory.py — Unit tests for scripts/recover-memory.py

All tests are deterministic and require no external services, no Telegram,
no LLM, no OpenClaw runtime. Temporary directories are used for filesystem tests.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Load module (hyphen-free import via importlib)
# ---------------------------------------------------------------------------
_SCRIPT = Path(__file__).parent.parent / "scripts" / "recover-memory.py"
_spec = importlib.util.spec_from_file_location("recover_memory", _SCRIPT)
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_target(tmp: Path) -> Path:
    target = tmp / "proj"
    target.mkdir()
    return target


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_context(target: Path, content: str = "# Project\nTest project.\n") -> Path:
    p = target / ".agent" / "AGENT_CONTEXT.md"
    return _write(p, content)


def _write_working(target: Path, fname: str, content: str) -> Path:
    p = target / ".agent" / "memory" / "working" / fname
    return _write(p, content)


def _fresh_date() -> str:
    """Return a date string that is NOT stale (today)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _stale_date() -> str:
    """Return a date string that IS stale (> 7 days ago)."""
    return (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# TestArgParsing
# ---------------------------------------------------------------------------

class TestArgParsing(unittest.TestCase):

    def test_target_required(self):
        parser = rm.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args([])

    def test_target_accepted(self):
        parser = rm.build_parser()
        args = parser.parse_args(["--target", "/tmp/proj"])
        self.assertEqual(args.target, "/tmp/proj")

    def test_default_format_markdown(self):
        parser = rm.build_parser()
        args = parser.parse_args(["--target", "/tmp/proj"])
        self.assertEqual(args.fmt, "markdown")

    def test_format_text(self):
        parser = rm.build_parser()
        args = parser.parse_args(["--target", "/tmp/proj", "--format", "text"])
        self.assertEqual(args.fmt, "text")

    def test_topic_optional(self):
        parser = rm.build_parser()
        args = parser.parse_args(["--target", "/tmp/proj"])
        self.assertIsNone(args.topic)

    def test_topic_accepted(self):
        parser = rm.build_parser()
        args = parser.parse_args(["--target", "/tmp/proj", "--topic", "7301"])
        self.assertEqual(args.topic, "7301")

    def test_role_choices(self):
        parser = rm.build_parser()
        for role in ("coder", "reviewer", "infra"):
            args = parser.parse_args(["--target", "/tmp/proj", "--role", role])
            self.assertEqual(args.role, role)

    def test_role_invalid_rejected(self):
        parser = rm.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["--target", "/tmp/proj", "--role", "wizard"])


# ---------------------------------------------------------------------------
# TestExitCodes
# ---------------------------------------------------------------------------

class TestExitCodes(unittest.TestCase):

    def test_missing_target_exits_1(self):
        code, msg = rm.recover(Path("/nonexistent/path/xyz"))
        self.assertEqual(code, 1)
        self.assertIn("ERROR", msg)

    def test_target_is_file_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "not_a_dir.txt"
            f.write_text("x")
            code, msg = rm.recover(f)
            self.assertEqual(code, 1)

    def test_missing_agent_context_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            code, msg = rm.recover(target)
            self.assertEqual(code, 1)
            self.assertIn("AGENT_CONTEXT", msg)

    def test_context_present_no_working_files_exits_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            _write_context(target)
            code, _ = rm.recover(target)
            self.assertEqual(code, 0)

    def test_all_files_present_exits_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            _write_context(target)
            for fname in rm.REQUIRED_WORKING_FILES:
                _write_working(target, fname, f"# Brief\ncontent\n")
            code, _ = rm.recover(target)
            self.assertEqual(code, 0)


# ---------------------------------------------------------------------------
# TestFileStatuses
# ---------------------------------------------------------------------------

class TestFileStatuses(unittest.TestCase):

    def test_required_missing_shows_MISSING(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            _write_context(target)
            _, output = rm.recover(target)
            self.assertIn("[MISSING]", output)

    def test_optional_missing_shows_optional_MISSING(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            _write_context(target)
            _, output = rm.recover(target)
            self.assertIn("optional [MISSING]", output)

    def test_fresh_file_shows_OK(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            _write_context(target)
            _write_working(target, "agent-brief.md",
                           f"_Last updated: {_fresh_date()}_\n# Brief\nok\n")
            _, output = rm.recover(target)
            self.assertIn("agent-brief.md — OK", output)

    def test_stale_file_shows_STALE(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            _write_context(target)
            _write_working(target, "agent-brief.md",
                           f"_Last updated: {_stale_date()}_\n# Brief\nstale content\n")
            _, output = rm.recover(target)
            self.assertIn("[STALE]", output)

    def test_no_date_not_stale(self):
        """Files without a date should be OK, not STALE."""
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            _write_context(target)
            _write_working(target, "current-state.md", "# Current State\nno date here\n")
            _, output = rm.recover(target)
            self.assertIn("current-state.md — OK", output)

    def test_context_md_always_listed_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            _write_context(target)
            _, output = rm.recover(target)
            idx_context = output.find("AGENT_CONTEXT.md")
            idx_brief = output.find("agent-brief.md")
            self.assertGreater(idx_brief, idx_context)


# ---------------------------------------------------------------------------
# TestStalenessHelper
# ---------------------------------------------------------------------------

class TestStalenessHelper(unittest.TestCase):

    def test_fresh_not_stale(self):
        text = f"_Last updated: {_fresh_date()}_\n"
        self.assertFalse(rm._is_stale(text))

    def test_old_date_is_stale(self):
        text = f"_Last updated: {_stale_date()}_\n"
        self.assertTrue(rm._is_stale(text))

    def test_no_date_not_stale(self):
        self.assertFalse(rm._is_stale("no date in here"))

    def test_case_insensitive_last_updated(self):
        text = f"Last updated: {_stale_date()}\n"
        self.assertTrue(rm._is_stale(text))

    def test_parse_returns_datetime(self):
        text = "Last updated: 2024-01-15\n"
        dt = rm._parse_last_updated(text)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2024)
        self.assertEqual(dt.month, 1)
        self.assertEqual(dt.day, 15)

    def test_parse_returns_none_when_absent(self):
        self.assertIsNone(rm._parse_last_updated("nothing here"))


# ---------------------------------------------------------------------------
# TestSectionExtraction
# ---------------------------------------------------------------------------

class TestSectionExtraction(unittest.TestCase):

    def test_extracts_matching_heading(self):
        text = "## Project\nThis is the project.\n## Other\nignore this\n"
        result = rm._extract_sections(text, frozenset({"project"}))
        self.assertIn("This is the project.", result)
        self.assertNotIn("ignore this", result)

    def test_no_match_returns_empty(self):
        text = "## Unrelated\nsome content\n"
        result = rm._extract_sections(text, frozenset({"project"}))
        self.assertEqual(result, "")

    def test_heading_case_insensitive_normalised(self):
        # heading_set contains lowercase; heading in text may be mixed
        text = "## Current State\nstate info\n"
        result = rm._extract_sections(text, frozenset({"current state"}))
        self.assertIn("state info", result)

    def test_truncates_at_max_chars(self):
        long_body = "x" * 1000
        text = f"## Project\n{long_body}\n"
        result = rm._extract_sections(text, frozenset({"project"}), max_chars=50)
        self.assertLessEqual(len(result), 60)  # some buffer for ellipsis
        self.assertIn("…", result)

    def test_multiple_matching_sections_combined(self):
        text = "## Project\nfirst\n## Project\nsecond\n"
        result = rm._extract_sections(text, frozenset({"project"}))
        self.assertIn("first", result)
        self.assertIn("second", result)


# ---------------------------------------------------------------------------
# TestOutputFormat
# ---------------------------------------------------------------------------

class TestOutputFormat(unittest.TestCase):

    def _full_target(self, tmp: Path) -> Path:
        target = _make_target(tmp)
        _write_context(target, "# Project\nMy project.\n## Current Objective\nBuild thing.\n")
        _write_working(target, "agent-brief.md",
                       f"_Last updated: {_fresh_date()}_\n## Brief\nAgent is briefed.\n"
                       "## Do not do\n- No hacks\n")
        _write_working(target, "current-state.md",
                       f"_Last updated: {_fresh_date()}_\n## Current State\nWorking fine.\n"
                       "## Blockers\n- None\n")
        _write_working(target, "known-issues.md",
                       f"_Last updated: {_fresh_date()}_\n## Known Issues\n- Issue A\n"
                       "## Next\n- Step 1\n")
        return target

    def test_markdown_contains_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._full_target(Path(tmp))
            _, output = rm.recover(target, fmt="markdown")
            self.assertIn("# Recovered Project Memory", output)

    def test_markdown_loaded_files_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._full_target(Path(tmp))
            _, output = rm.recover(target, fmt="markdown")
            self.assertIn("## Loaded files", output)

    def test_markdown_notes_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._full_target(Path(tmp))
            _, output = rm.recover(target, fmt="markdown")
            self.assertIn("## Notes", output)
            self.assertIn("No Telegram read performed.", output)
            self.assertIn("No raw chunks read.", output)
            self.assertIn("No vector DB", output)

    def test_markdown_startup_context_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._full_target(Path(tmp))
            _, output = rm.recover(target, fmt="markdown")
            self.assertIn("## Startup context", output)

    def test_markdown_donot_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._full_target(Path(tmp))
            _, output = rm.recover(target, fmt="markdown")
            self.assertIn("## Do not do", output)

    def test_markdown_blockers_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._full_target(Path(tmp))
            _, output = rm.recover(target, fmt="markdown")
            self.assertIn("## Current blockers", output)

    def test_markdown_next_actions_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._full_target(Path(tmp))
            _, output = rm.recover(target, fmt="markdown")
            self.assertIn("## Next useful actions", output)

    def test_text_format_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._full_target(Path(tmp))
            _, output = rm.recover(target, fmt="text")
            self.assertIn("=== Recovered Project Memory ===", output)
            self.assertNotIn("# Recovered Project Memory", output)

    def test_text_format_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._full_target(Path(tmp))
            _, output = rm.recover(target, fmt="text")
            self.assertIn("Notes:", output)
            self.assertIn("No Telegram read performed.", output)

    def test_filters_appear_in_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._full_target(Path(tmp))
            _, output = rm.recover(target, topic="7301", role="coder", fmt="markdown")
            self.assertIn("topic=7301", output)
            self.assertIn("role=coder", output)

    def test_no_filters_no_filter_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._full_target(Path(tmp))
            _, output = rm.recover(target, fmt="markdown")
            self.assertNotIn("Filters:", output)

    def test_extracted_context_content_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._full_target(Path(tmp))
            _, output = rm.recover(target, fmt="markdown")
            # "My project." is under ## Project in AGENT_CONTEXT
            self.assertIn("My project.", output)

    def test_extracted_donot_content_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._full_target(Path(tmp))
            _, output = rm.recover(target, fmt="markdown")
            self.assertIn("No hacks", output)

    def test_extracted_blockers_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._full_target(Path(tmp))
            _, output = rm.recover(target, fmt="markdown")
            self.assertIn("None", output)

    def test_extracted_next_actions_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._full_target(Path(tmp))
            _, output = rm.recover(target, fmt="markdown")
            self.assertIn("Step 1", output)


# ---------------------------------------------------------------------------
# TestFallbackBrief
# ---------------------------------------------------------------------------

class TestFallbackBrief(unittest.TestCase):
    """When agent-brief.md has no recognised context heading, use first-n-chars fallback."""

    def test_brief_without_heading_uses_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            _write_context(target)
            # Write brief with no recognised headings
            _write_working(target, "agent-brief.md",
                           "No headings here. Just plain text about the project.")
            _, output = rm.recover(target, fmt="markdown")
            self.assertIn("No headings here", output)


# ---------------------------------------------------------------------------
# TestMainEntrypoint
# ---------------------------------------------------------------------------

class TestMainEntrypoint(unittest.TestCase):

    def test_main_returns_1_for_bad_target(self):
        code = rm.main(["--target", "/nonexistent/path/xyz"])
        self.assertEqual(code, 1)

    def test_main_returns_0_for_valid_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            _write_context(target)
            code = rm.main(["--target", str(target)])
            self.assertEqual(code, 0)

    def test_main_text_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            _write_context(target)
            code = rm.main(["--target", str(target), "--format", "text"])
            self.assertEqual(code, 0)

    def test_main_with_topic_and_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            _write_context(target)
            code = rm.main(["--target", str(target), "--topic", "1234", "--role", "infra"])
            self.assertEqual(code, 0)


# ---------------------------------------------------------------------------
# TestStdlibOnly (smoke: no forbidden imports)
# ---------------------------------------------------------------------------

class TestStdlibOnly(unittest.TestCase):

    def test_no_forbidden_imports(self):
        """The script must not import non-stdlib packages."""
        forbidden = {"anthropic", "openai", "numpy", "requests", "pyrogram",
                     "tiktoken", "chromadb", "langchain"}
        script_text = _SCRIPT.read_text(encoding="utf-8")
        for pkg in forbidden:
            self.assertNotIn(f"import {pkg}", script_text,
                             f"Forbidden import found: {pkg}")
            self.assertNotIn(f"from {pkg}", script_text,
                             f"Forbidden import found: {pkg}")


if __name__ == "__main__":
    unittest.main()
