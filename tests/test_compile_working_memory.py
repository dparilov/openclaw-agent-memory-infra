"""
tests/test_compile_working_memory.py — Unit tests for scripts/compile-working-memory.py

All tests are deterministic and require no external services, no Telegram,
no LLM, no OpenClaw runtime. Temporary directories are used for filesystem tests.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Load module (hyphen-free import via importlib)
# ---------------------------------------------------------------------------
_SCRIPT = Path(__file__).parent.parent / "scripts" / "compile-working-memory.py"
_spec = importlib.util.spec_from_file_location("compile_working_memory", _SCRIPT)
cwm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cwm)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_target(tmp: Path) -> Path:
    target = tmp / "proj"
    target.mkdir()
    return target


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _make_chunk(target: Path, topic_id: str, index: int, content: str) -> Path:
    raw_dir = target / ".agent" / "memory" / "raw" / f"topic-{topic_id}"
    raw_dir.mkdir(parents=True, exist_ok=True)
    chunk = raw_dir / f"chunk-{index:04d}.md"
    chunk.write_text(content)
    return chunk


def _run(args: list[str]) -> int:
    return cwm.main(args)


# ---------------------------------------------------------------------------
# TestArgParsing
# ---------------------------------------------------------------------------

class TestArgParsing(unittest.TestCase):

    def test_dry_run_is_default(self):
        """No --write → dry_run flag set internally."""
        parser = cwm.build_parser()
        args = parser.parse_args(["--target", "/tmp", "--topics", "7301:coder"])
        self.assertFalse(args.write)
        self.assertFalse(args.dry_run)  # flag not set yet; main() sets it

    def test_write_flag(self):
        parser = cwm.build_parser()
        args = parser.parse_args(["--target", "/tmp", "--topics", "7301:coder", "--write"])
        self.assertTrue(args.write)

    def test_dry_run_explicit(self):
        parser = cwm.build_parser()
        args = parser.parse_args(["--target", "/tmp", "--topics", "7301:coder", "--dry-run"])
        self.assertTrue(args.dry_run)

    def test_notes_path_optional(self):
        parser = cwm.build_parser()
        args = parser.parse_args(["--target", "/tmp", "--topics", "7301:coder"])
        self.assertIsNone(args.notes_path)

    def test_missing_target_exits(self):
        with self.assertRaises(SystemExit):
            cwm.build_parser().parse_args(["--topics", "7301:coder"])

    def test_missing_topics_exits(self):
        with self.assertRaises(SystemExit):
            cwm.build_parser().parse_args(["--target", "/tmp"])


# ---------------------------------------------------------------------------
# TestTopicParsing
# ---------------------------------------------------------------------------

class TestTopicParsing(unittest.TestCase):

    def test_single_topic(self):
        specs = cwm.parse_topics("7301:coder")
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].topic_id, "7301")
        self.assertEqual(specs[0].role, "coder")

    def test_multiple_topics(self):
        specs = cwm.parse_topics("7301:coder,13350:reviewer,15222:infra")
        self.assertEqual(len(specs), 3)
        self.assertEqual(specs[1].topic_id, "13350")
        self.assertEqual(specs[1].role, "reviewer")

    def test_invalid_role_raises(self):
        with self.assertRaises(ValueError):
            cwm.parse_topics("7301:badrole")

    def test_missing_colon_raises(self):
        with self.assertRaises(ValueError):
            cwm.parse_topics("7301coder")

    def test_empty_topic_id_raises(self):
        with self.assertRaises(ValueError):
            cwm.parse_topics(":coder")

    def test_empty_string_raises(self):
        with self.assertRaises(ValueError):
            cwm.parse_topics("")

    def test_all_roles_valid(self):
        for role in cwm.ALLOWED_ROLES:
            specs = cwm.parse_topics(f"7301:{role}")
            self.assertEqual(specs[0].role, role)

    def test_whitespace_stripped(self):
        specs = cwm.parse_topics(" 7301 : coder ")
        self.assertEqual(specs[0].topic_id, "7301")
        self.assertEqual(specs[0].role, "coder")


# ---------------------------------------------------------------------------
# TestChunkScanning
# ---------------------------------------------------------------------------

class TestChunkScanning(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.target = Path(self.tmp) / "proj"
        self.target.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_finds_chunks(self):
        _make_chunk(self.target, "7301", 1, "hello")
        _make_chunk(self.target, "7301", 2, "world")
        chunks = cwm.scan_chunks(self.target, "7301", "coder")
        self.assertEqual(len(chunks), 2)

    def test_chunks_sorted(self):
        _make_chunk(self.target, "7301", 3, "c")
        _make_chunk(self.target, "7301", 1, "a")
        _make_chunk(self.target, "7301", 2, "b")
        chunks = cwm.scan_chunks(self.target, "7301", "coder")
        names = [c.path.name for c in chunks]
        self.assertEqual(names, sorted(names))

    def test_no_chunks_returns_empty(self):
        chunks = cwm.scan_chunks(self.target, "9999", "coder")
        self.assertEqual(chunks, [])

    def test_topic_role_assigned(self):
        _make_chunk(self.target, "7301", 1, "content")
        chunks = cwm.scan_chunks(self.target, "7301", "reviewer")
        self.assertEqual(chunks[0].role, "reviewer")
        self.assertEqual(chunks[0].topic_id, "7301")

    def test_redaction_detected(self):
        _make_chunk(self.target, "7301", 1, "normal text")
        _make_chunk(self.target, "7301", 2, "has [REDACTED:api_key] here")
        chunks = cwm.scan_chunks(self.target, "7301", "coder")
        self.assertFalse(chunks[0].has_redactions)
        self.assertTrue(chunks[1].has_redactions)

    def test_char_count_correct(self):
        content = "x" * 500
        _make_chunk(self.target, "7301", 1, content)
        chunks = cwm.scan_chunks(self.target, "7301", "coder")
        self.assertEqual(chunks[0].char_count, 500)


# ---------------------------------------------------------------------------
# TestContextPacket
# ---------------------------------------------------------------------------

class TestContextPacket(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.target = Path(self.tmp) / "proj"
        self.target.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_empty_chunks_returns_placeholder(self):
        result = cwm.build_context_packet([])
        self.assertIn("no chunks", result)

    def test_includes_chunk_header(self):
        _make_chunk(self.target, "7301", 1, "some content")
        chunks = cwm.scan_chunks(self.target, "7301", "coder")
        packet = cwm.build_context_packet(chunks)
        self.assertIn("chunk-0001.md", packet)
        self.assertIn("topic-7301", packet)

    def test_includes_chunk_body(self):
        _make_chunk(self.target, "7301", 1, "my important fact")
        chunks = cwm.scan_chunks(self.target, "7301", "coder")
        packet = cwm.build_context_packet(chunks)
        self.assertIn("my important fact", packet)

    def test_bounded_by_max_chars(self):
        big = "x" * 20_000
        _make_chunk(self.target, "7301", 1, big)
        _make_chunk(self.target, "7301", 2, big)
        chunks = cwm.scan_chunks(self.target, "7301", "coder")
        packet = cwm.build_context_packet(chunks, max_chars=10_000)
        self.assertLessEqual(len(packet), 12_000)  # allow small overhead
        self.assertIn("omitted", packet)

    def test_multiple_chunks_all_included_when_under_limit(self):
        _make_chunk(self.target, "7301", 1, "fact one")
        _make_chunk(self.target, "7301", 2, "fact two")
        chunks = cwm.scan_chunks(self.target, "7301", "coder")
        packet = cwm.build_context_packet(chunks)
        self.assertIn("fact one", packet)
        self.assertIn("fact two", packet)


# ---------------------------------------------------------------------------
# TestExtractionPrompt
# ---------------------------------------------------------------------------

class TestExtractionPrompt(unittest.TestCase):

    def test_non_empty(self):
        prompt = cwm.build_extraction_prompt(
            topics=[cwm.TopicSpec("7301", "coder")],
            has_agent_context=True,
            has_notes=False,
            redacted_count=0,
        )
        self.assertTrue(len(prompt) > 100)

    def test_includes_topic(self):
        prompt = cwm.build_extraction_prompt(
            topics=[cwm.TopicSpec("7301", "coder")],
            has_agent_context=True,
            has_notes=False,
            redacted_count=0,
        )
        self.assertIn("7301:coder", prompt)

    def test_reports_redacted_count(self):
        prompt = cwm.build_extraction_prompt(
            topics=[cwm.TopicSpec("7301", "coder")],
            has_agent_context=False,
            has_notes=False,
            redacted_count=3,
        )
        self.assertIn("3", prompt)

    def test_no_llm_import(self):
        """Script must not import openai, anthropic, or requests."""
        import ast
        src = _SCRIPT.read_text()
        tree = ast.parse(src)
        forbidden = {"openai", "anthropic", "requests", "httpx"}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in getattr(node, "names", []):
                    self.assertNotIn(alias.name.split(".")[0], forbidden,
                                     f"forbidden import: {alias.name}")
                if isinstance(node, ast.ImportFrom) and node.module:
                    self.assertNotIn(node.module.split(".")[0], forbidden,
                                     f"forbidden import: {node.module}")


# ---------------------------------------------------------------------------
# TestDraftTemplates
# ---------------------------------------------------------------------------

class TestDraftTemplates(unittest.TestCase):

    def _draft(self, filename):
        return cwm.build_draft(
            filename=filename,
            compiled_at="2026-05-16T14:00:00Z",
            topics=[cwm.TopicSpec("7301", "coder")],
            source_count=2,
            extraction_prompt="extract facts",
            context_packet="chunk content here",
        )

    def test_agent_brief_has_required_sections(self):
        draft = self._draft("agent-brief.md")
        for section in ["Project identity", "Repository", "Current objective",
                        "Do-not-do rules", "Memory load order", "Next useful actions"]:
            self.assertIn(section, draft)

    def test_agent_brief_contains_context_packet(self):
        draft = self._draft("agent-brief.md")
        self.assertIn("chunk content here", draft)
        self.assertIn("extract facts", draft)

    def test_current_state_has_required_sections(self):
        draft = self._draft("current-state.md")
        for section in ["Current State", "Active branch", "Recent completed work",
                        "In-progress work", "Current blockers"]:
            self.assertIn(section, draft)

    def test_current_state_no_context_packet(self):
        """Context packet only in agent-brief.md to avoid duplication."""
        draft = self._draft("current-state.md")
        self.assertNotIn("chunk content here", draft)

    def test_known_issues_has_required_sections(self):
        draft = self._draft("known-issues.md")
        self.assertIn("Known Issues", draft)
        self.assertIn("severity", draft)

    def test_draft_frontmatter_present(self):
        for fname in cwm.WORKING_FILES:
            draft = self._draft(fname)
            self.assertIn("draft: true", draft)
            self.assertIn("compiled_at", draft)

    def test_draft_no_raw_secrets(self):
        """Draft templates must not contain raw credential strings."""
        for fname in cwm.WORKING_FILES:
            draft = self._draft(fname)
            for secret in ["supersecret", "sk-", "Bearer eyJ", "password=abc"]:
                self.assertNotIn(secret, draft)


# ---------------------------------------------------------------------------
# TestDryRun
# ---------------------------------------------------------------------------

class TestDryRun(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.target = Path(self.tmp) / "proj"
        self.target.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _args(self, extra=None):
        base = ["--target", str(self.target), "--topics", "7301:coder"]
        return base + (extra or [])

    def test_dry_run_creates_no_files(self):
        _make_chunk(self.target, "7301", 1, "content")
        rc = _run(self._args())
        working_dir = self.target / ".agent" / "memory" / "working"
        self.assertFalse(working_dir.exists())
        self.assertEqual(rc, 0)

    def test_dry_run_explicit_flag_creates_no_files(self):
        _make_chunk(self.target, "7301", 1, "content")
        rc = _run(self._args(["--dry-run"]))
        working_dir = self.target / ".agent" / "memory" / "working"
        self.assertFalse(working_dir.exists())
        self.assertEqual(rc, 0)

    def test_dry_run_returns_zero(self):
        rc = _run(self._args())
        self.assertEqual(rc, 0)

    def test_dry_run_does_not_create_raw_dir(self):
        _run(self._args())
        raw_dir = self.target / ".agent" / "memory" / "raw"
        self.assertFalse(raw_dir.exists())

    def test_dry_run_with_no_chunks_returns_zero(self):
        # No chunks for topic — valid, just warns
        rc = _run(self._args())
        self.assertEqual(rc, 0)


# ---------------------------------------------------------------------------
# TestWriteMode
# ---------------------------------------------------------------------------

class TestWriteMode(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.target = Path(self.tmp) / "proj"
        self.target.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _args(self, extra=None):
        base = ["--target", str(self.target), "--topics", "7301:coder", "--write"]
        return base + (extra or [])

    def test_write_creates_working_files(self):
        _make_chunk(self.target, "7301", 1, "some context")
        rc = _run(self._args())
        working_dir = self.target / ".agent" / "memory" / "working"
        self.assertEqual(rc, 0)
        for fname in cwm.WORKING_FILES:
            self.assertTrue((working_dir / fname).exists(), f"missing {fname}")

    def test_write_returns_zero(self):
        rc = _run(self._args())
        self.assertEqual(rc, 0)

    def test_write_does_not_touch_raw(self):
        _run(self._args())
        raw_dir = self.target / ".agent" / "memory" / "raw"
        self.assertFalse(raw_dir.exists())

    def test_write_does_not_create_forbidden_dirs(self):
        _run(self._args())
        memory_dir = self.target / ".agent" / "memory"
        for forbidden in cwm.FORBIDDEN_MEMORY_DIRS:
            self.assertFalse((memory_dir / forbidden).exists(),
                             f"forbidden dir created: {forbidden}")

    def test_write_does_not_stage_or_commit(self):
        """Script must not contain git commit/push commands."""
        src = _SCRIPT.read_text()
        for forbidden in ["subprocess", "git commit", "git push", "git add"]:
            self.assertNotIn(forbidden, src,
                             f"forbidden string found in script: {forbidden!r}")

    def test_agent_brief_contains_context_packet_in_write(self):
        _make_chunk(self.target, "7301", 1, "my unique fact xyz")
        _run(self._args())
        brief = (self.target / ".agent" / "memory" / "working" / "agent-brief.md").read_text()
        self.assertIn("my unique fact xyz", brief)

    def test_current_state_written(self):
        _run(self._args())
        cs = (self.target / ".agent" / "memory" / "working" / "current-state.md").read_text()
        self.assertIn("Current State", cs)
        self.assertIn("draft: true", cs)

    def test_known_issues_written(self):
        _run(self._args())
        ki = (self.target / ".agent" / "memory" / "working" / "known-issues.md").read_text()
        self.assertIn("Known Issues", ki)

    def test_write_idempotent_second_run_overwrites(self):
        """Second write overwrites without error (no overwrite guard on working/)."""
        _make_chunk(self.target, "7301", 1, "v1 content")
        _run(self._args())
        brief_v1 = (self.target / ".agent" / "memory" / "working" / "agent-brief.md").read_text()

        _make_chunk(self.target, "7301", 2, "v2 content added")
        rc = _run(self._args())
        self.assertEqual(rc, 0)
        brief_v2 = (self.target / ".agent" / "memory" / "working" / "agent-brief.md").read_text()
        # Second run is allowed (no overwrite guard on working/)
        self.assertIn("draft: true", brief_v2)


# ---------------------------------------------------------------------------
# TestWarnings
# ---------------------------------------------------------------------------

class TestWarnings(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.target = Path(self.tmp) / "proj"
        self.target.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _inputs_for(self, topics_str="7301:coder", chunks=None, agent_ctx="",
                    existing_working=None):
        topics = cwm.parse_topics(topics_str)
        chunk_list = chunks or []
        return cwm.CompileInputs(
            agent_context=agent_ctx,
            topics=topics,
            chunks=chunk_list,
            notes="",
            existing_working=existing_working or {},
        )

    def test_warns_missing_agent_context(self):
        inputs = self._inputs_for(agent_ctx="")
        warnings = cwm.collect_warnings(inputs)
        self.assertTrue(any("AGENT_CONTEXT" in w for w in warnings))

    def test_no_warning_when_agent_context_present(self):
        inputs = self._inputs_for(agent_ctx="# Agent Context\nsome content")
        warnings = cwm.collect_warnings(inputs)
        self.assertFalse(any("AGENT_CONTEXT" in w for w in warnings))

    def test_warns_no_chunks(self):
        inputs = self._inputs_for(chunks=[])
        warnings = cwm.collect_warnings(inputs)
        self.assertTrue(any("no raw chunks" in w for w in warnings))

    def test_warns_redacted_chunks(self):
        chunk = cwm.ChunkInfo(
            path=Path("/fake/chunk-0001.md"),
            topic_id="7301",
            role="coder",
            char_count=100,
            has_redactions=True,
        )
        inputs = self._inputs_for(chunks=[chunk])
        warnings = cwm.collect_warnings(inputs)
        self.assertTrue(any("redacted" in w for w in warnings))

    def test_warns_existing_working_will_overwrite(self):
        inputs = self._inputs_for(existing_working={"agent-brief.md": "old content"})
        warnings = cwm.collect_warnings(inputs)
        self.assertTrue(any("overwritten" in w for w in warnings))


# ---------------------------------------------------------------------------
# TestErrorHandling
# ---------------------------------------------------------------------------

class TestErrorHandling(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.target = Path(self.tmp) / "proj"
        self.target.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_nonexistent_target_returns_1(self):
        rc = _run(["--target", "/nonexistent/path/xyz", "--topics", "7301:coder"])
        self.assertEqual(rc, 1)

    def test_nonexistent_notes_returns_1(self):
        rc = _run([
            "--target", str(self.target),
            "--topics", "7301:coder",
            "--notes", "/nonexistent/notes.md",
        ])
        self.assertEqual(rc, 1)

    def test_invalid_topics_returns_1(self):
        rc = _run(["--target", str(self.target), "--topics", "7301:badrole"])
        self.assertEqual(rc, 1)

    def test_notes_read_when_provided(self):
        notes = Path(self.tmp) / "notes.md"
        notes.write_text("operator note content")
        rc = _run([
            "--target", str(self.target),
            "--topics", "7301:coder",
            "--notes", str(notes),
        ])
        self.assertEqual(rc, 0)

    def test_agent_context_read_when_present(self):
        ctx = self.target / ".agent" / "AGENT_CONTEXT.md"
        ctx.parent.mkdir(parents=True, exist_ok=True)
        ctx.write_text("# Agent Context\nproject: test")
        rc = _run(["--target", str(self.target), "--topics", "7301:coder"])
        self.assertEqual(rc, 0)


# ---------------------------------------------------------------------------
# TestSensitiveData
# ---------------------------------------------------------------------------

class TestSensitiveData(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.target = Path(self.tmp) / "proj"
        self.target.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_redacted_placeholder_passes_through_not_raw_secret(self):
        """[REDACTED:api_key] in chunk is OK to include; raw secret value is not."""
        _make_chunk(self.target, "7301", 1,
                    "context: api_key=[REDACTED:api_key] used here")
        _run(["--target", str(self.target), "--topics", "7301:coder", "--write"])
        brief = (self.target / ".agent" / "memory" / "working" / "agent-brief.md").read_text()
        # The placeholder is acceptable
        self.assertIn("[REDACTED:api_key]", brief)
        # Raw secret values must not appear
        self.assertNotIn("supersecret", brief)
        self.assertNotIn("sk-abcdef", brief)

    def test_write_does_not_reconstruct_secrets(self):
        """Chunks with only redacted placeholders — output must not contain raw values."""
        chunk_content = (
            "Session: user configured api_key=[REDACTED:api_key]\n"
            "bearer=[REDACTED:bearer_token]\n"
        )
        _make_chunk(self.target, "7301", 1, chunk_content)
        _run(["--target", str(self.target), "--topics", "7301:coder", "--write"])
        working_dir = self.target / ".agent" / "memory" / "working"
        for fname in cwm.WORKING_FILES:
            text = (working_dir / fname).read_text()
            # No raw credential patterns
            for bad in ["password=", "sk-test", "eyJhbGci", "supersecret"]:
                self.assertNotIn(bad, text,
                                 f"raw secret found in {fname}: {bad!r}")
