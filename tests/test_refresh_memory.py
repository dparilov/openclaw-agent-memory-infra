"""
tests/test_refresh_memory.py — Unit tests for scripts/refresh-memory.py

All tests are deterministic and require no external services, no Telegram,
no LLM, no OpenClaw runtime. Mock modules are injected to avoid running the
full archive-context / compile-working-memory pipelines.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import List, Optional

# ---------------------------------------------------------------------------
# Load module via importlib (hyphen-safe)
# ---------------------------------------------------------------------------
_SCRIPT = Path(__file__).parent.parent / "scripts" / "refresh-memory.py"
_spec = importlib.util.spec_from_file_location("refresh_memory", _SCRIPT)
rm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rm)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_target(tmp: Path) -> Path:
    target = tmp / "proj"
    target.mkdir()
    (target / ".agent").mkdir()
    (target / ".agent" / "AGENT_CONTEXT.md").write_text("# Project\n", encoding="utf-8")
    return target


def _make_input(tmp: Path, content: str = "# Context\nsome content\n") -> Path:
    f = tmp / "context.md"
    f.write_text(content, encoding="utf-8")
    return f


def _mock_mod(exit_code: int = 0) -> types.SimpleNamespace:
    """Return a mock script module whose main() returns exit_code."""
    calls: List[List[str]] = []

    def main(argv=None):
        calls.append(list(argv or []))
        return exit_code

    mod = types.SimpleNamespace(main=main, _calls=calls)
    return mod


def _mock_mod_raises(exc: Exception) -> types.SimpleNamespace:
    """Return a mock script module whose main() raises an exception."""
    def main(argv=None):
        raise exc
    return types.SimpleNamespace(main=main)


# ---------------------------------------------------------------------------
# TestArgParsing
# ---------------------------------------------------------------------------

class TestArgParsing(unittest.TestCase):

    def test_required_args(self):
        p = rm.build_parser()
        with self.assertRaises(SystemExit):
            p.parse_args([])

    def test_target_required(self):
        p = rm.build_parser()
        with self.assertRaises(SystemExit):
            p.parse_args(["--topic", "7301:coder", "--input", "/f.md",
                          "--source-type", "markdown_export"])

    def test_topic_required(self):
        p = rm.build_parser()
        with self.assertRaises(SystemExit):
            p.parse_args(["--target", "/t", "--input", "/f.md",
                          "--source-type", "markdown_export"])

    def test_input_required(self):
        p = rm.build_parser()
        with self.assertRaises(SystemExit):
            p.parse_args(["--target", "/t", "--topic", "7301:coder",
                          "--source-type", "markdown_export"])

    def test_source_type_required(self):
        p = rm.build_parser()
        with self.assertRaises(SystemExit):
            p.parse_args(["--target", "/t", "--topic", "7301:coder",
                          "--input", "/f.md"])

    def test_source_type_choices(self):
        p = rm.build_parser()
        for st in ("session_jsonl", "markdown_export", "operator_note"):
            args = p.parse_args(["--target", "/t", "--topic", "7301:coder",
                                  "--input", "/f.md", "--source-type", st])
            self.assertEqual(args.source_type, st)

    def test_source_type_invalid_rejected(self):
        p = rm.build_parser()
        with self.assertRaises(SystemExit):
            p.parse_args(["--target", "/t", "--topic", "7301:coder",
                          "--input", "/f.md", "--source-type", "telegram"])

    def test_default_no_write(self):
        p = rm.build_parser()
        args = p.parse_args(["--target", "/t", "--topic", "7301:coder",
                              "--input", "/f.md", "--source-type", "markdown_export"])
        self.assertFalse(args.write)
        self.assertFalse(args.dry_run)

    def test_write_flag(self):
        p = rm.build_parser()
        args = p.parse_args(["--target", "/t", "--topic", "7301:coder",
                              "--input", "/f.md", "--source-type", "markdown_export",
                              "--write"])
        self.assertTrue(args.write)

    def test_dry_run_flag(self):
        p = rm.build_parser()
        args = p.parse_args(["--target", "/t", "--topic", "7301:coder",
                              "--input", "/f.md", "--source-type", "markdown_export",
                              "--dry-run"])
        self.assertTrue(args.dry_run)

    def test_notes_optional(self):
        p = rm.build_parser()
        args = p.parse_args(["--target", "/t", "--topic", "7301:coder",
                              "--input", "/f.md", "--source-type", "markdown_export"])
        self.assertIsNone(args.notes)

    def test_chunk_size_default(self):
        p = rm.build_parser()
        args = p.parse_args(["--target", "/t", "--topic", "7301:coder",
                              "--input", "/f.md", "--source-type", "markdown_export"])
        self.assertEqual(args.chunk_size, 200)

    def test_max_chars_default(self):
        p = rm.build_parser()
        args = p.parse_args(["--target", "/t", "--topic", "7301:coder",
                              "--input", "/f.md", "--source-type", "markdown_export"])
        self.assertEqual(args.max_chars, 12000)


# ---------------------------------------------------------------------------
# TestTopicParsing
# ---------------------------------------------------------------------------

class TestTopicParsing(unittest.TestCase):

    def test_valid_topic(self):
        tid, role = rm.parse_topic("7301:coder")
        self.assertEqual(tid, "7301")
        self.assertEqual(role, "coder")

    def test_all_valid_roles(self):
        for role in ("coder", "reviewer", "infra", "unknown"):
            tid, r = rm.parse_topic(f"1234:{role}")
            self.assertEqual(r, role)

    def test_missing_colon_raises(self):
        with self.assertRaises(ValueError):
            rm.parse_topic("7301")

    def test_empty_topic_id_raises(self):
        with self.assertRaises(ValueError):
            rm.parse_topic(":coder")

    def test_invalid_role_raises(self):
        with self.assertRaises(ValueError):
            rm.parse_topic("7301:wizard")

    def test_whitespace_stripped(self):
        tid, role = rm.parse_topic(" 7301 : coder ")
        self.assertEqual(tid, "7301")
        self.assertEqual(role, "coder")


# ---------------------------------------------------------------------------
# TestValidation
# ---------------------------------------------------------------------------

class TestValidation(unittest.TestCase):

    def test_missing_target_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            inp = _make_input(Path(tmp))
            err = rm._validate(
                Path(tmp) / "nope", inp, "7301:coder", "markdown_export"
            )
            self.assertIsNotNone(err)
            self.assertIn("target", err)

    def test_target_is_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "file.txt"
            f.write_text("x")
            inp = _make_input(Path(tmp))
            err = rm._validate(f, inp, "7301:coder", "markdown_export")
            self.assertIsNotNone(err)

    def test_missing_agent_context_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "proj"
            target.mkdir()
            inp = _make_input(Path(tmp))
            err = rm._validate(target, inp, "7301:coder", "markdown_export")
            self.assertIsNotNone(err)
            self.assertIn("AGENT_CONTEXT", err)

    def test_missing_input_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            err = rm._validate(
                target, Path(tmp) / "nope.md", "7301:coder", "markdown_export"
            )
            self.assertIsNotNone(err)
            self.assertIn("input", err.lower())

    def test_invalid_topic_format_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            inp = _make_input(Path(tmp))
            err = rm._validate(target, inp, "7301", "markdown_export")
            self.assertIsNotNone(err)
            self.assertIn("topic", err.lower())

    def test_invalid_source_type_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            inp = _make_input(Path(tmp))
            err = rm._validate(target, inp, "7301:coder", "telegram")
            self.assertIsNotNone(err)
            self.assertIn("source-type", err)

    def test_valid_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            inp = _make_input(Path(tmp))
            err = rm._validate(target, inp, "7301:coder", "markdown_export")
            self.assertIsNone(err)


# ---------------------------------------------------------------------------
# TestRefreshCore (using mock modules)
# ---------------------------------------------------------------------------

class TestRefreshCore(unittest.TestCase):

    def _run(self, archive_code=0, compile_code=0, write=False):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            inp = _make_input(Path(tmp))
            arch = _mock_mod(archive_code)
            comp = _mock_mod(compile_code)
            code, report = rm.refresh(
                target=target,
                topic_id="7301",
                role="coder",
                input_path=inp,
                source_type="markdown_export",
                write=write,
                _archive_mod=arch,
                _compile_mod=comp,
            )
            return code, report, arch, comp

    def test_both_pass_exits_0(self):
        code, _, _, _ = self._run(0, 0)
        self.assertEqual(code, 0)

    def test_archive_fail_exits_1_and_skips_compile(self):
        code, report, _, comp = self._run(archive_code=1)
        self.assertEqual(code, 1)
        self.assertIn("FAIL", report)
        self.assertIn("SKIP", report)
        self.assertEqual(comp._calls, [])  # compile never called

    def test_compile_fail_exits_1(self):
        code, report, arch, _ = self._run(archive_code=0, compile_code=1)
        self.assertEqual(code, 1)
        self.assertIn("PASS", report)  # archive passed
        self.assertIn("FAIL", report)  # compile failed

    def test_dry_run_default_mode(self):
        code, report, arch, comp = self._run(write=False)
        self.assertEqual(code, 0)
        self.assertIn("dry-run", report)
        # archive_argv should NOT contain --write
        self.assertNotIn("--write", arch._calls[0])

    def test_write_mode_passes_write_flag_to_archive(self):
        code, report, arch, comp = self._run(write=True)
        self.assertEqual(code, 0)
        self.assertIn("write", report)
        self.assertIn("--write", arch._calls[0])

    def test_write_mode_passes_write_flag_to_compile(self):
        code, report, arch, comp = self._run(write=True)
        self.assertIn("--write", comp._calls[0])

    def test_archive_receives_correct_topic_and_role(self):
        _, _, arch, _ = self._run()
        argv = arch._calls[0]
        self.assertIn("--topic", argv)
        self.assertIn("7301", argv)
        self.assertIn("--role", argv)
        self.assertIn("coder", argv)

    def test_compile_receives_combined_topic_role(self):
        _, _, _, comp = self._run()
        argv = comp._calls[0]
        self.assertIn("--topics", argv)
        topics_idx = argv.index("--topics")
        self.assertEqual(argv[topics_idx + 1], "7301:coder")

    def test_archive_exception_records_warning_and_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            inp = _make_input(Path(tmp))
            arch = _mock_mod_raises(RuntimeError("boom"))
            comp = _mock_mod(0)
            code, report = rm.refresh(
                target=target, topic_id="7301", role="coder",
                input_path=inp, source_type="markdown_export",
                _archive_mod=arch, _compile_mod=comp,
            )
            self.assertEqual(code, 1)
            self.assertIn("FAIL", report)

    def test_compile_exception_records_warning_and_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            inp = _make_input(Path(tmp))
            arch = _mock_mod(0)
            comp = _mock_mod_raises(RuntimeError("compile boom"))
            code, report = rm.refresh(
                target=target, topic_id="7301", role="coder",
                input_path=inp, source_type="markdown_export",
                _archive_mod=arch, _compile_mod=comp,
            )
            self.assertEqual(code, 1)
            self.assertIn("FAIL", report)


# ---------------------------------------------------------------------------
# TestReport
# ---------------------------------------------------------------------------

class TestReport(unittest.TestCase):

    def _report(self, archive_status="PASS", compile_status="PASS", warnings=None):
        return rm._build_report(
            mode="dry-run",
            target=Path("/tmp/proj"),
            topic_id="7301",
            role="coder",
            input_path=Path("/tmp/context.md"),
            source_type="markdown_export",
            archive_status=archive_status,
            compile_status=compile_status,
            warnings=warnings or [],
        )

    def test_contains_header(self):
        self.assertIn("REFRESH MEMORY REPORT", self._report())

    def test_contains_mode(self):
        self.assertIn("Mode: dry-run", self._report())

    def test_contains_topic_and_role(self):
        r = self._report()
        self.assertIn("Topic: 7301", r)
        self.assertIn("Role: coder", r)

    def test_contains_archive_status(self):
        self.assertIn("Archive step: PASS", self._report())

    def test_contains_compile_status(self):
        self.assertIn("Compile step: PASS", self._report())

    def test_skip_shown_when_archive_fails(self):
        self.assertIn("Compile step: SKIP",
                      self._report(archive_status="FAIL", compile_status="SKIP"))

    def test_contains_raw_output_path(self):
        self.assertIn("topic-7301", self._report())

    def test_contains_working_files(self):
        r = self._report()
        self.assertIn("agent-brief.md", r)
        self.assertIn("current-state.md", r)
        self.assertIn("known-issues.md", r)

    def test_contains_notes_no_telegram(self):
        self.assertIn("No Telegram read performed.", self._report())

    def test_contains_notes_no_llm(self):
        self.assertIn("No LLM API calls performed.", self._report())

    def test_contains_notes_no_vector_db(self):
        self.assertIn("No vector DB / embeddings / memory-core used.", self._report())

    def test_no_warnings_shows_none(self):
        self.assertIn("- none", self._report())

    def test_warning_appears_in_report(self):
        r = self._report(warnings=["something went wrong"])
        self.assertIn("something went wrong", r)


# ---------------------------------------------------------------------------
# TestMainEntrypoint
# ---------------------------------------------------------------------------

class TestMainEntrypoint(unittest.TestCase):

    def test_missing_target_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            inp = _make_input(Path(tmp))
            code = rm.main([
                "--target", str(Path(tmp) / "nope"),
                "--topic", "7301:coder",
                "--input", str(inp),
                "--source-type", "markdown_export",
            ])
            self.assertEqual(code, 1)

    def test_missing_input_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            code = rm.main([
                "--target", str(target),
                "--topic", "7301:coder",
                "--input", str(Path(tmp) / "nope.md"),
                "--source-type", "markdown_export",
            ])
            self.assertEqual(code, 1)

    def test_invalid_topic_format_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            inp = _make_input(Path(tmp))
            code = rm.main([
                "--target", str(target),
                "--topic", "7301",  # missing :role
                "--input", str(inp),
                "--source-type", "markdown_export",
            ])
            self.assertEqual(code, 1)

    def test_invalid_source_type_rejected_by_argparse(self):
        """argparse choices= rejects invalid source-type before main logic."""
        with self.assertRaises(SystemExit) as cm:
            rm.main([
                "--target", "/t",
                "--topic", "7301:coder",
                "--input", "/f.md",
                "--source-type", "bad",
            ])
        self.assertNotEqual(cm.exception.code, 0)


# ---------------------------------------------------------------------------
# TestDryRunWritesNothing
# ---------------------------------------------------------------------------

class TestDryRunWritesNothing(unittest.TestCase):

    def test_dry_run_writes_no_files(self):
        """Dry-run with mock modules must not create any files."""
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            inp = _make_input(Path(tmp))
            arch = _mock_mod(0)
            comp = _mock_mod(0)

            files_before = set(Path(tmp).rglob("*"))
            rm.refresh(
                target=target, topic_id="7301", role="coder",
                input_path=inp, source_type="markdown_export",
                write=False,
                _archive_mod=arch, _compile_mod=comp,
            )
            files_after = set(Path(tmp).rglob("*"))
            self.assertEqual(files_before, files_after)


# ---------------------------------------------------------------------------
# TestNotesPassthrough
# ---------------------------------------------------------------------------

class TestNotesPassthrough(unittest.TestCase):

    def test_notes_passed_to_compile_when_provided(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            inp = _make_input(Path(tmp))
            notes = Path(tmp) / "notes.md"
            notes.write_text("operator note", encoding="utf-8")

            arch = _mock_mod(0)
            comp = _mock_mod(0)
            rm.refresh(
                target=target, topic_id="7301", role="coder",
                input_path=inp, source_type="markdown_export",
                notes_path=notes,
                _archive_mod=arch, _compile_mod=comp,
            )
            comp_argv = comp._calls[0]
            self.assertIn("--notes", comp_argv)
            notes_idx = comp_argv.index("--notes")
            self.assertIn("notes.md", comp_argv[notes_idx + 1])

    def test_no_notes_arg_absent_from_compile(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_target(Path(tmp))
            inp = _make_input(Path(tmp))
            arch = _mock_mod(0)
            comp = _mock_mod(0)
            rm.refresh(
                target=target, topic_id="7301", role="coder",
                input_path=inp, source_type="markdown_export",
                notes_path=None,
                _archive_mod=arch, _compile_mod=comp,
            )
            self.assertNotIn("--notes", comp._calls[0])


# ---------------------------------------------------------------------------
# TestStdlibOnly
# ---------------------------------------------------------------------------

class TestStdlibOnly(unittest.TestCase):

    def test_no_forbidden_imports(self):
        forbidden = {"anthropic", "openai", "numpy", "requests", "pyrogram",
                     "tiktoken", "chromadb", "langchain"}
        script_text = _SCRIPT.read_text(encoding="utf-8")
        for pkg in forbidden:
            self.assertNotIn(f"import {pkg}", script_text,
                             f"Forbidden import: {pkg}")
            self.assertNotIn(f"from {pkg}", script_text,
                             f"Forbidden import: {pkg}")

    def test_no_telegram_read(self):
        script_text = _SCRIPT.read_text(encoding="utf-8")
        # Check for actual import statements, not docstring mentions
        for forbidden_import in ("import pyrogram", "from pyrogram",
                                  "import read_topic", "from read_topic"):
            self.assertNotIn(forbidden_import, script_text)

    def test_no_llm_calls(self):
        script_text = _SCRIPT.read_text(encoding="utf-8")
        for forbidden in ("anthropic", "openai", "ChatCompletion", "completions.create"):
            self.assertNotIn(forbidden, script_text)


if __name__ == "__main__":
    unittest.main()
