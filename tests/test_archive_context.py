"""
tests/test_archive_context.py — Unit tests for scripts/archive-context.py

All tests are deterministic and require no external services, no Telegram,
no LLM, no OpenClaw runtime. Temporary directories are used for filesystem tests.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load module (hyphen-free import via importlib)
# ---------------------------------------------------------------------------
_SCRIPT = Path(__file__).parent.parent / "scripts" / "archive-context.py"
_spec = importlib.util.spec_from_file_location("archive_context", _SCRIPT)
ac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ac)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _run(argv: list[str]) -> int:
    return ac.main(argv)


# ---------------------------------------------------------------------------
# 1. Argument parsing
# ---------------------------------------------------------------------------

class TestArgParsing:
    REQUIRED = [
        "--target", "/tmp",
        "--topic", "7301",
        "--role", "coder",
        "--input", "/tmp/x.md",
        "--source-type", "markdown_export",
    ]

    def test_all_required_parse(self):
        p = ac.build_parser()
        args = p.parse_args(self.REQUIRED)
        assert args.topic == "7301"
        assert args.role == "coder"
        assert args.source_type == "markdown_export"

    def test_write_default_false(self):
        p = ac.build_parser()
        args = p.parse_args(self.REQUIRED)
        assert args.write is False

    def test_write_flag_true(self):
        p = ac.build_parser()
        args = p.parse_args(self.REQUIRED + ["--write"])
        assert args.write is True

    def test_chunk_size_default(self):
        p = ac.build_parser()
        args = p.parse_args(self.REQUIRED)
        assert args.chunk_size == ac.DEFAULT_CHUNK_SIZE

    def test_chunk_size_override(self):
        p = ac.build_parser()
        args = p.parse_args(self.REQUIRED + ["--chunk-size", "50"])
        assert args.chunk_size == 50

    def test_invalid_role_exits(self):
        p = ac.build_parser()
        with pytest.raises(SystemExit):
            p.parse_args(self.REQUIRED[:-4] + ["--role", "invalid",
                         "--input", "/tmp/x.md", "--source-type", "markdown_export"])

    def test_invalid_source_type_exits(self):
        p = ac.build_parser()
        with pytest.raises(SystemExit):
            p.parse_args(self.REQUIRED[:-2] + ["--source-type", "fake_type"])

    def test_missing_target_exits(self):
        p = ac.build_parser()
        with pytest.raises(SystemExit):
            p.parse_args(["--topic", "7301", "--role", "coder",
                          "--input", "/tmp/x.md", "--source-type", "markdown_export"])

    def test_missing_input_exits(self):
        p = ac.build_parser()
        with pytest.raises(SystemExit):
            p.parse_args(["--target", "/tmp", "--topic", "7301",
                          "--role", "coder", "--source-type", "markdown_export"])


# ---------------------------------------------------------------------------
# 2. Redaction
# ---------------------------------------------------------------------------

class TestRedaction:
    def test_clean_text_unchanged(self):
        rr = ac.redact_text("This is a normal project note.")
        assert rr.status == "clean"
        assert rr.counts == {}
        assert "normal project note" in rr.text

    def test_password_redacted(self):
        rr = ac.redact_text("password=supersecret123")
        assert rr.status == "redacted"
        assert "supersecret123" not in rr.text
        assert "[REDACTED:password]" in rr.text
        assert rr.counts.get("password", 0) >= 1

    def test_password_colon_redacted(self):
        rr = ac.redact_text("password: mysecretpass")
        assert "mysecretpass" not in rr.text
        assert "REDACTED" in rr.text

    def test_api_key_redacted(self):
        rr = ac.redact_text("api_key=sk-1234567890abcdef")
        assert "sk-1234567890abcdef" not in rr.text
        assert "REDACTED" in rr.text

    def test_bearer_token_redacted(self):
        rr = ac.redact_text("Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig")
        assert "eyJhbGciOiJSUzI1NiJ9" not in rr.text
        assert "REDACTED" in rr.text

    def test_pem_key_redacted(self):
        pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----"
        rr = ac.redact_text(pem)
        assert "MIIEowIBAAKCAQEA" not in rr.text
        assert "[REDACTED:pem_key]" in rr.text

    def test_telegram_bot_token_redacted(self):
        rr = ac.redact_text("bot token: 123456789:ABCDefghIJKLmnoPQRstuvwxyz1234567890ab")
        assert "ABCDefghIJKLmnoPQRstuvwxyz" not in rr.text
        assert "REDACTED" in rr.text

    def test_multiple_redactions_counted(self):
        text = "password=abc\napi_key=xyz"
        rr = ac.redact_text(text)
        assert rr.status == "redacted"
        total = sum(rr.counts.values())
        assert total >= 2

    def test_raw_secret_not_in_output(self):
        """Core safety check: raw secret values must not appear in redacted output."""
        secrets = ["supersecret", "sk-abcdef", "mypassword99"]
        text = f"password={secrets[0]}\napi_key={secrets[1]}\npassword: {secrets[2]}"
        rr = ac.redact_text(text)
        for s in secrets:
            assert s not in rr.text, f"Secret '{s}' found in redacted output"


# ---------------------------------------------------------------------------
# 3. Chunking — plain lines
# ---------------------------------------------------------------------------

class TestChunkLines:
    def test_single_chunk_when_under_limit(self):
        lines = [f"line {i}" for i in range(10)]
        chunks = ac.chunk_lines(lines, chunk_size=200)
        assert len(chunks) == 1
        assert chunks[0].message_count == 10

    def test_splits_into_multiple_chunks(self):
        lines = [f"line {i}" for i in range(250)]
        chunks = ac.chunk_lines(lines, chunk_size=100)
        assert len(chunks) == 3
        assert chunks[0].message_count == 100
        assert chunks[1].message_count == 100
        assert chunks[2].message_count == 50

    def test_chunk_indices_are_1_based(self):
        lines = ["a", "b", "c"]
        chunks = ac.chunk_lines(lines, chunk_size=2)
        assert chunks[0].index == 1
        assert chunks[1].index == 2

    def test_empty_input_returns_no_chunks(self):
        chunks = ac.chunk_lines([], chunk_size=200)
        assert len(chunks) == 0

    def test_exact_boundary(self):
        lines = [f"x{i}" for i in range(200)]
        chunks = ac.chunk_lines(lines, chunk_size=200)
        assert len(chunks) == 1

    def test_one_over_boundary(self):
        lines = [f"x{i}" for i in range(201)]
        chunks = ac.chunk_lines(lines, chunk_size=200)
        assert len(chunks) == 2


# ---------------------------------------------------------------------------
# 4. Chunking — JSONL
# ---------------------------------------------------------------------------

class TestChunkJsonl:
    def _jsonl(self, messages: list[dict]) -> str:
        return "\n".join(json.dumps(m) for m in messages)

    def test_splits_jsonl_by_message_count(self):
        messages = [{"id": i, "text": f"msg {i}"} for i in range(5)]
        content = self._jsonl(messages)
        lines = content.splitlines()
        chunks = ac.chunk_jsonl(lines, chunk_size=3)
        assert len(chunks) == 2
        assert chunks[0].message_count == 3
        assert chunks[1].message_count == 2

    def test_extracts_timestamps(self):
        messages = [
            {"text": "a", "timestamp": "2026-05-01T10:00:00Z"},
            {"text": "b", "timestamp": "2026-05-01T11:00:00Z"},
        ]
        content = self._jsonl(messages)
        lines = content.splitlines()
        chunks = ac.chunk_jsonl(lines, chunk_size=10)
        assert chunks[0].ts_start == "2026-05-01T10:00:00Z"
        assert chunks[0].ts_end == "2026-05-01T11:00:00Z"

    def test_invalid_json_lines_skipped_gracefully(self):
        content = "not json\n{\"text\": \"ok\"}\nalso not json"
        lines = content.splitlines()
        chunks = ac.chunk_jsonl(lines, chunk_size=10)
        assert len(chunks) >= 1
        assert chunks[0].message_count >= 1

    def test_empty_lines_ignored(self):
        content = "\n\n{\"text\": \"a\"}\n\n"
        lines = content.splitlines()
        chunks = ac.chunk_jsonl(lines, chunk_size=10)
        assert chunks[0].message_count == 1


# ---------------------------------------------------------------------------
# 5. Front-matter rendering
# ---------------------------------------------------------------------------

class TestRenderFrontmatter:
    def _make_chunk(self, **kw):
        defaults = dict(index=1, lines=["x"], message_count=5,
                        ts_start="", ts_end="")
        defaults.update(kw)
        return ac.Chunk(**defaults)

    def test_contains_required_fields(self):
        chunk = self._make_chunk()
        fm = ac.render_frontmatter(
            source_type="markdown_export",
            chat_id="-123",
            topic_id="7301",
            topic_role="coder",
            chunk=chunk,
            redaction_status="clean",
            created_at="2026-05-16T12:00:00Z",
        )
        assert "source_type: markdown_export" in fm
        assert 'chat_id: "-123"' in fm
        assert 'topic_id: "7301"' in fm
        assert "topic_role: coder" in fm
        assert "redaction_status: clean" in fm
        assert "created_at:" in fm
        assert fm.startswith("---\n")
        assert fm.rstrip().endswith("---")

    def test_redacted_status_in_frontmatter(self):
        chunk = self._make_chunk()
        fm = ac.render_frontmatter(
            source_type="operator_note",
            chat_id="",
            topic_id="15222",
            topic_role="infra",
            chunk=chunk,
            redaction_status="redacted",
            created_at="2026-05-16T12:00:00Z",
        )
        assert "redaction_status: redacted" in fm

    def test_message_count_in_range(self):
        chunk = self._make_chunk(message_count=42)
        fm = ac.render_frontmatter(
            source_type="session_jsonl",
            chat_id="",
            topic_id="7301",
            topic_role="coder",
            chunk=chunk,
            redaction_status="clean",
            created_at="2026-05-16T12:00:00Z",
        )
        assert "message_count: 42" in fm


# ---------------------------------------------------------------------------
# 6. Chunk filename
# ---------------------------------------------------------------------------

class TestChunkFilename:
    def test_zero_padded_4_digits(self):
        assert ac.chunk_filename(1) == "chunk-0001.md"
        assert ac.chunk_filename(42) == "chunk-0042.md"
        assert ac.chunk_filename(1000) == "chunk-1000.md"


# ---------------------------------------------------------------------------
# 7. Output directory resolution
# ---------------------------------------------------------------------------

class TestResolveOutDir:
    def test_default_path(self):
        result = ac.resolve_out_dir(Path("/proj"), "7301", None)
        assert result == Path("/proj/.agent/memory/raw/topic-7301")

    def test_override_path(self):
        result = ac.resolve_out_dir(Path("/proj"), "7301", "/custom/out")
        assert result == Path("/custom/out")


# ---------------------------------------------------------------------------
# 8. Dry-run — no filesystem writes
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_creates_no_files(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        input_file = tmp_path / "context.md"
        _write(input_file, "This is project context.\nNo secrets here.")

        rc = _run([
            "--target", str(target),
            "--topic", "7301",
            "--role", "coder",
            "--input", str(input_file),
            "--source-type", "markdown_export",
        ])
        assert rc == 0
        raw_dir = target / ".agent" / "memory" / "raw"
        assert not raw_dir.exists(), "raw/ directory must not be created in dry-run"

    def test_dry_run_is_default(self, tmp_path):
        """Absence of --write must not create files."""
        target = tmp_path / "proj"
        target.mkdir()
        input_file = _write(tmp_path / "ctx.md", "hello world")
        rc = _run([
            "--target", str(target), "--topic", "7301", "--role", "coder",
            "--input", str(input_file), "--source-type", "operator_note",
        ])
        assert rc == 0
        assert not (target / ".agent").exists()


# ---------------------------------------------------------------------------
# 9. Write mode — creates correct files
# ---------------------------------------------------------------------------

class TestWriteMode:
    def test_write_creates_chunk_files(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        lines = [f"line {i}" for i in range(10)]
        input_file = _write(tmp_path / "ctx.md", "\n".join(lines))

        rc = _run([
            "--target", str(target),
            "--topic", "7301",
            "--role", "coder",
            "--input", str(input_file),
            "--source-type", "markdown_export",
            "--chunk-size", "10",
            "--write",
        ])
        assert rc == 0
        out_dir = target / ".agent" / "memory" / "raw" / "topic-7301"
        chunks = sorted(out_dir.glob("chunk-*.md"))
        assert len(chunks) == 1
        assert chunks[0].name == "chunk-0001.md"

    def test_write_multiple_chunks(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        lines = [f"line {i}" for i in range(25)]
        input_file = _write(tmp_path / "ctx.md", "\n".join(lines))

        rc = _run([
            "--target", str(target),
            "--topic", "7301",
            "--role", "reviewer",
            "--input", str(input_file),
            "--source-type", "markdown_export",
            "--chunk-size", "10",
            "--write",
        ])
        assert rc == 0
        out_dir = target / ".agent" / "memory" / "raw" / "topic-7301"
        chunks = sorted(out_dir.glob("chunk-*.md"))
        assert len(chunks) == 3
        assert chunks[0].name == "chunk-0001.md"
        assert chunks[2].name == "chunk-0003.md"

    def test_chunk_contains_frontmatter(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        input_file = _write(tmp_path / "ctx.md", "Hello project.\nThis is a note.")

        _run([
            "--target", str(target),
            "--topic", "15222",
            "--role", "infra",
            "--input", str(input_file),
            "--source-type", "operator_note",
            "--write",
        ])
        chunk = (target / ".agent" / "memory" / "raw" / "topic-15222" / "chunk-0001.md")
        content = chunk.read_text()
        assert content.startswith("---\n")
        assert "source_type: operator_note" in content
        assert 'topic_id: "15222"' in content
        assert "topic_role: infra" in content
        assert "redaction_status:" in content
        assert "created_at:" in content

    def test_write_does_not_touch_working_memory(self, tmp_path):
        """Write mode must never create or modify .agent/memory/working/."""
        target = tmp_path / "proj"
        target.mkdir()
        input_file = _write(tmp_path / "ctx.md", "some context")

        _run([
            "--target", str(target),
            "--topic", "7301",
            "--role", "coder",
            "--input", str(input_file),
            "--source-type", "markdown_export",
            "--write",
        ])
        working = target / ".agent" / "memory" / "working"
        assert not working.exists(), "working/ must not be created by archive-context"

    def test_write_returns_zero_on_success(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        input_file = _write(tmp_path / "ctx.md", "ok")
        rc = _run([
            "--target", str(target), "--topic", "7301", "--role", "coder",
            "--input", str(input_file), "--source-type", "markdown_export", "--write",
        ])
        assert rc == 0


# ---------------------------------------------------------------------------
# 10. Redaction in write mode
# ---------------------------------------------------------------------------

class TestRedactionInOutput:
    def test_secret_not_written_to_chunk(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        input_file = _write(tmp_path / "ctx.md",
                            "Notes:\npassword=hunter2\nSome normal text.")

        _run([
            "--target", str(target),
            "--topic", "7301",
            "--role", "coder",
            "--input", str(input_file),
            "--source-type", "operator_note",
            "--write",
        ])
        chunk = (target / ".agent" / "memory" / "raw" / "topic-7301" / "chunk-0001.md")
        content = chunk.read_text()
        assert "hunter2" not in content, "Raw secret must not appear in written chunk"
        assert "REDACTED" in content
        assert "redaction_status: redacted" in content

    def test_clean_chunk_has_clean_status(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        input_file = _write(tmp_path / "ctx.md",
                            "Current state: working on v1.\nBlockers: none.")

        _run([
            "--target", str(target),
            "--topic", "7301",
            "--role", "coder",
            "--input", str(input_file),
            "--source-type", "markdown_export",
            "--write",
        ])
        chunk = (target / ".agent" / "memory" / "raw" / "topic-7301" / "chunk-0001.md")
        content = chunk.read_text()
        assert "redaction_status: clean" in content


# ---------------------------------------------------------------------------
# 11. Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_nonexistent_target_returns_1(self, tmp_path):
        input_file = _write(tmp_path / "ctx.md", "hello")
        rc = _run([
            "--target", str(tmp_path / "nonexistent"),
            "--topic", "7301", "--role", "coder",
            "--input", str(input_file),
            "--source-type", "markdown_export",
        ])
        assert rc == 1

    def test_nonexistent_input_returns_1(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        rc = _run([
            "--target", str(target),
            "--topic", "7301", "--role", "coder",
            "--input", str(tmp_path / "missing.md"),
            "--source-type", "markdown_export",
        ])
        assert rc == 1

    def test_out_override_used(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        custom_out = tmp_path / "custom_out"
        input_file = _write(tmp_path / "ctx.md", "hello")

        _run([
            "--target", str(target),
            "--topic", "7301", "--role", "coder",
            "--input", str(input_file),
            "--source-type", "markdown_export",
            "--out", str(custom_out),
            "--write",
        ])
        chunks = list(custom_out.glob("chunk-*.md"))
        assert len(chunks) == 1

    def test_chat_id_written_to_frontmatter(self, tmp_path):
        target = tmp_path / "proj"
        target.mkdir()
        input_file = _write(tmp_path / "ctx.md", "hello")

        _run([
            "--target", str(target),
            "--topic", "7301", "--role", "coder",
            "--input", str(input_file),
            "--source-type", "markdown_export",
            "--chat-id", "-1003596522926",
            "--write",
        ])
        chunk = (target / ".agent" / "memory" / "raw" / "topic-7301" / "chunk-0001.md")
        assert '-1003596522926' in chunk.read_text()
