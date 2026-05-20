"""Tests for scripts/handoff-dispatch.py (25 test cases per spec)."""

import importlib.util
import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

# ---------------------------------------------------------------------------
# Load the hyphenated script as a module
# ---------------------------------------------------------------------------
_SCRIPT = Path(__file__).parent.parent / "scripts" / "handoff-dispatch.py"


def _load_hd():
    spec = importlib.util.spec_from_file_location("handoff_dispatch", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hd = _load_hd()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_active_md(tmp_path: Path, frontmatter: dict, body: str = "# ACTIVE\n") -> Path:
    p = tmp_path / ".agent" / "handoffs" / "ACTIVE.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    content = "---\n" + yaml.dump(frontmatter) + "---\n" + body
    p.write_text(content, encoding="utf-8")
    return p


def make_config(tmp_path: Path, cfg: dict) -> Path:
    p = tmp_path / ".agent" / "config.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.dump(cfg), encoding="utf-8")
    return p


def base_config(topics=None):
    return {
        "handoff_dispatch": {
            "enabled": True,
            "transport": "pyrogram_user",
            "telegram": {
                "chat_id": -1234567890,
                "topics": topics or {
                    "coder": 7301,
                    "reviewer": 13350,
                    "human": 15222,
                },
            },
            "pyrogram": {
                "session_name": "test_session",
                "workdir": "~/.pyrogram",
            },
            "messages": {
                "ready_for_implementation": "Read ACTIVE handoff and implement the task.",
                "changes_requested": "Read ACTIVE handoff and fix reviewer blockers only.",
                "ready_for_review": "Read ACTIVE handoff and review the implementation.",
                "approved": "APPROVED. Human may merge after final checks.",
            },
        }
    }


def run(argv, tmp_path=None):
    """Parse argv and call dispatch(). Returns (stdout, stderr, exit_code)."""
    args = hd.parse_args(argv)
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    code = 0
    try:
        with redirect_stdout(out_buf), redirect_stderr(err_buf):
            hd.dispatch(args)
    except SystemExit as e:
        code = int(e.code) if e.code is not None else 0
    return out_buf.getvalue(), err_buf.getvalue(), code


# ---------------------------------------------------------------------------
# 1–4  Dry-run routing for all four dispatch events
# ---------------------------------------------------------------------------

def test_01_dry_run_coder_ready_for_implementation(tmp_path):
    """Dry-run reads ACTIVE.md and config, prints planned CODER dispatch."""
    make_active_md(tmp_path, {"status": "ready_for_implementation", "to_role": "CODER"})
    make_config(tmp_path, base_config())
    out, err, code = run(["--target", str(tmp_path), "--dry-run"])
    assert code == 0
    assert "DRY RUN" in out
    assert "ready_for_implementation" in out
    assert "CODER" in out
    assert "implement the task" in out


def test_02_dry_run_changes_requested(tmp_path):
    make_active_md(tmp_path, {"status": "changes_requested", "to_role": "CODER"})
    make_config(tmp_path, base_config())
    out, err, code = run(["--target", str(tmp_path), "--dry-run"])
    assert code == 0
    assert "changes_requested" in out
    assert "CODER" in out
    assert "fix reviewer blockers" in out


def test_03_dry_run_ready_for_review(tmp_path):
    make_active_md(tmp_path, {"status": "ready_for_review", "to_role": "REVIEWER"})
    make_config(tmp_path, base_config())
    out, err, code = run(["--target", str(tmp_path), "--dry-run"])
    assert code == 0
    assert "ready_for_review" in out
    assert "REVIEWER" in out
    assert "review the implementation" in out


def test_04_dry_run_approved(tmp_path):
    make_active_md(tmp_path, {"status": "approved", "to_role": "HUMAN"})
    make_config(tmp_path, base_config())
    out, err, code = run(["--target", str(tmp_path), "--dry-run"])
    assert code == 0
    assert "approved" in out
    assert "HUMAN" in out
    assert "APPROVED" in out


# ---------------------------------------------------------------------------
# 5–9  Failure cases
# ---------------------------------------------------------------------------

def test_05_unsupported_status_to_role_combination_fails_cleanly(tmp_path):
    make_active_md(tmp_path, {"status": "approved", "to_role": "CODER"})
    make_config(tmp_path, base_config())
    out, err, code = run(["--target", str(tmp_path), "--dry-run"])
    assert code != 0
    assert "Unsupported" in err


def test_06_missing_target_fails(tmp_path):
    out, err, code = run(["--target", str(tmp_path / "nonexistent"), "--dry-run"])
    assert code != 0
    assert "not exist" in err


def test_07_missing_active_md_fails(tmp_path):
    make_config(tmp_path, base_config())
    (tmp_path / ".agent").mkdir(parents=True, exist_ok=True)
    out, err, code = run(["--target", str(tmp_path), "--dry-run"])
    assert code != 0
    assert "ACTIVE.md not found" in err


def test_08_missing_config_fails(tmp_path):
    make_active_md(tmp_path, {"status": "ready_for_implementation", "to_role": "CODER"})
    out, err, code = run(["--target", str(tmp_path), "--dry-run"])
    assert code != 0
    assert "Config not found" in err


def test_09_missing_handoff_dispatch_section_fails(tmp_path):
    make_active_md(tmp_path, {"status": "ready_for_implementation", "to_role": "CODER"})
    make_config(tmp_path, {"other_section": {"key": "value"}})
    out, err, code = run(["--target", str(tmp_path), "--dry-run"])
    assert code != 0
    assert "handoff_dispatch" in err


# ---------------------------------------------------------------------------
# 10  Disabled dispatch
# ---------------------------------------------------------------------------

def test_10_disabled_dispatch_exits_cleanly(tmp_path):
    make_active_md(tmp_path, {"status": "ready_for_implementation", "to_role": "CODER"})
    cfg = base_config()
    cfg["handoff_dispatch"]["enabled"] = False
    make_config(tmp_path, cfg)
    out, err, code = run(["--target", str(tmp_path), "--dry-run"])
    assert code == 0
    assert "disabled" in out or "SKIPPED" in out


# ---------------------------------------------------------------------------
# 11–12  Idempotency
# ---------------------------------------------------------------------------

def test_11_idempotency_skip_when_already_dispatched(tmp_path):
    make_active_md(tmp_path, {
        "status": "ready_for_implementation",
        "to_role": "CODER",
        "dispatch": {
            "last_status": "ready_for_implementation",
            "last_to_role": "CODER",
        },
    })
    make_config(tmp_path, base_config())
    out, err, code = run(["--target", str(tmp_path), "--dry-run"])
    assert code == 0
    assert "SKIPPED" in out
    assert "already dispatched" in out


def test_12_force_bypasses_idempotency_in_dry_run(tmp_path):
    make_active_md(tmp_path, {
        "status": "ready_for_implementation",
        "to_role": "CODER",
        "dispatch": {
            "last_status": "ready_for_implementation",
            "last_to_role": "CODER",
        },
    })
    make_config(tmp_path, base_config())
    out, err, code = run(["--target", str(tmp_path), "--dry-run", "--force"])
    assert code == 0
    assert "DRY RUN" in out
    assert "force" in out.lower()


# ---------------------------------------------------------------------------
# 13–14  Dry-run safety
# ---------------------------------------------------------------------------

def test_13_dry_run_does_not_require_pyrogram(tmp_path):
    """Dry-run must work even if pyrogram is not importable."""
    make_active_md(tmp_path, {"status": "ready_for_implementation", "to_role": "CODER"})
    make_config(tmp_path, base_config())
    with patch.dict(sys.modules, {"pyrogram": None}):
        out, err, code = run(["--target", str(tmp_path), "--dry-run"])
    assert code == 0
    assert "DRY RUN" in out


def test_14_dry_run_does_not_modify_active_md(tmp_path):
    p = make_active_md(tmp_path, {"status": "ready_for_implementation", "to_role": "CODER"})
    make_config(tmp_path, base_config())
    original = p.read_text(encoding="utf-8")
    run(["--target", str(tmp_path), "--dry-run"])
    assert p.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# 15–16  Successful mocked send
# ---------------------------------------------------------------------------

def test_15_successful_mocked_send_updates_dispatch_metadata(tmp_path):
    make_active_md(tmp_path, {"status": "ready_for_review", "to_role": "REVIEWER"})
    make_config(tmp_path, base_config())
    mock_pyr = MagicMock()
    with patch.dict(sys.modules, {"pyrogram": mock_pyr}), \
         patch.object(hd, "_send_message", return_value=99001):
        out, err, code = run(["--target", str(tmp_path), "--send"])
    assert code == 0
    fm = hd.read_frontmatter(tmp_path / ".agent" / "handoffs" / "ACTIVE.md")
    assert fm["dispatch"]["last_status"] == "ready_for_review"
    assert fm["dispatch"]["last_to_role"] == "REVIEWER"
    assert fm["dispatch"]["telegram_message_id"] == 99001


def test_16_mocked_send_records_all_metadata_fields(tmp_path):
    make_active_md(tmp_path, {"status": "ready_for_implementation", "to_role": "CODER"})
    make_config(tmp_path, base_config())
    mock_pyr = MagicMock()
    with patch.dict(sys.modules, {"pyrogram": mock_pyr}), \
         patch.object(hd, "_send_message", return_value=12345):
        out, err, code = run(["--target", str(tmp_path), "--send"])
    assert code == 0
    d = hd.read_frontmatter(tmp_path / ".agent" / "handoffs" / "ACTIVE.md")["dispatch"]
    assert d["telegram_chat_id"] == -1234567890
    assert d["telegram_topic_id"] == 7301
    assert d["telegram_message_id"] == 12345
    assert d["transport"] == "pyrogram_user"
    assert d["dispatched_at"]  # non-empty ISO timestamp


# ---------------------------------------------------------------------------
# 17  Security: no secrets in config
# ---------------------------------------------------------------------------

def test_17_no_secrets_required_in_config(tmp_path):
    """Config must not require API hash, API ID, phone, session string, or bot token."""
    make_active_md(tmp_path, {"status": "ready_for_implementation", "to_role": "CODER"})
    cfg = base_config()
    cfg_text = yaml.dump(cfg)
    for secret_key in ("api_hash", "api_id", "phone", "session_string", "bot_token"):
        assert secret_key not in cfg_text, f"Secret key found in config: {secret_key}"


# ---------------------------------------------------------------------------
# 18  CLI argument parsing
# ---------------------------------------------------------------------------

def test_18_parser_accepts_all_options(tmp_path):
    args = hd.parse_args([
        "--target", str(tmp_path),
        "--dry-run",
        "--send",
        "--force",
        "--config", str(tmp_path / "custom.yaml"),
        "--active", str(tmp_path / "custom-active.md"),
    ])
    assert args.target == str(tmp_path)
    assert args.dry_run is True
    assert args.send is True
    assert args.force is True
    assert args.config == str(tmp_path / "custom.yaml")
    assert args.active == str(tmp_path / "custom-active.md")


# ---------------------------------------------------------------------------
# 19–20  Numeric vs string topic config
# ---------------------------------------------------------------------------

def test_19_numeric_topic_id_used_directly_in_dry_run(tmp_path):
    make_active_md(tmp_path, {"status": "ready_for_review", "to_role": "REVIEWER"})
    make_config(tmp_path, base_config(
        topics={"coder": 7301, "reviewer": 13350, "human": 15222}
    ))
    out, err, code = run(["--target", str(tmp_path), "--dry-run"])
    assert code == 0
    assert "13350" in out


def test_20_string_topic_name_shown_in_dry_run(tmp_path):
    """Topic name config is shown in dry-run; resolution deferred to send path."""
    make_active_md(tmp_path, {"status": "ready_for_review", "to_role": "REVIEWER"})
    make_config(tmp_path, base_config(topics={
        "coder": "my-coder-topic",
        "reviewer": "my-reviewer-topic",
        "human": "my-human-topic",
    }))
    out, err, code = run(["--target", str(tmp_path), "--dry-run"])
    assert code == 0
    assert "my-reviewer-topic" in out


# ---------------------------------------------------------------------------
# 21–23  Topic-name resolution (send path, mocked)
# ---------------------------------------------------------------------------

def test_21_topic_name_resolution_success_routes_to_resolved_id(tmp_path):
    make_active_md(tmp_path, {"status": "ready_for_review", "to_role": "REVIEWER"})
    make_config(tmp_path, base_config(topics={
        "coder": "coder-topic",
        "reviewer": "reviewer-topic",
        "human": "human-topic",
    }))
    mock_pyr = MagicMock()
    with patch.dict(sys.modules, {"pyrogram": mock_pyr}), \
         patch.object(hd, "_resolve_topic_name", return_value=(13350, None)), \
         patch.object(hd, "_send_message", return_value=55555):
        out, err, code = run(["--target", str(tmp_path), "--send"])
    assert code == 0
    assert "13350" in out


def test_22_topic_name_no_match_fails_clearly_with_manual_fallback(tmp_path):
    make_active_md(tmp_path, {"status": "ready_for_review", "to_role": "REVIEWER"})
    make_config(tmp_path, base_config(topics={
        "coder": "coder-topic",
        "reviewer": "no-such-topic",
        "human": "human-topic",
    }))
    mock_pyr = MagicMock()
    with patch.dict(sys.modules, {"pyrogram": mock_pyr}), \
         patch.object(hd, "_resolve_topic_name",
                      return_value=(None, "no topic titled 'no-such-topic' in chat -1234567890")):
        out, err, code = run(["--target", str(tmp_path), "--send"])
    assert code != 0
    assert "BLOCKED" in out
    assert "no-such-topic" in out
    assert "review the implementation" in out  # manual fallback message present


def test_23_topic_name_multiple_matches_fails_clearly(tmp_path):
    make_active_md(tmp_path, {"status": "ready_for_review", "to_role": "REVIEWER"})
    make_config(tmp_path, base_config(topics={
        "coder": "coder-topic",
        "reviewer": "ambiguous-topic",
        "human": "human-topic",
    }))
    mock_pyr = MagicMock()
    with patch.dict(sys.modules, {"pyrogram": mock_pyr}), \
         patch.object(hd, "_resolve_topic_name",
                      return_value=(None, "multiple topics titled 'ambiguous-topic' in chat -1234567890")):
        out, err, code = run(["--target", str(tmp_path), "--send"])
    assert code != 0
    assert "BLOCKED" in out
    assert "ambiguous-topic" in out


# ---------------------------------------------------------------------------
# 24–25  Failure cases in send path
# ---------------------------------------------------------------------------

def test_24_pyrogram_unavailable_fails_clearly_with_manual_fallback(tmp_path):
    """When pyrogram is not installed, --send prints FAILED with manual fallback."""
    make_active_md(tmp_path, {"status": "ready_for_implementation", "to_role": "CODER"})
    make_config(tmp_path, base_config())
    with patch.dict(sys.modules, {"pyrogram": None}):
        out, err, code = run(["--target", str(tmp_path), "--send"])
    assert code != 0
    assert "FAILED" in out
    assert "implement the task" in out  # manual fallback


def test_25_failed_send_does_not_update_dispatch_metadata(tmp_path):
    """A failed send must not mark ACTIVE.md as dispatched."""
    p = make_active_md(tmp_path, {"status": "ready_for_implementation", "to_role": "CODER"})
    make_config(tmp_path, base_config())
    original_fm = hd.read_frontmatter(p)
    mock_pyr = MagicMock()
    with patch.dict(sys.modules, {"pyrogram": mock_pyr}), \
         patch.object(hd, "_send_message", return_value=None):
        out, err, code = run(["--target", str(tmp_path), "--send"])
    assert code != 0
    fm_after = hd.read_frontmatter(p)
    assert fm_after.get("dispatch") == original_fm.get("dispatch")


# ---------------------------------------------------------------------------
# 26–27  Low-level send call shape (reply_to_message_id, not message_thread_id)
# ---------------------------------------------------------------------------

def _make_pyrogram_mock(message_id: int):
    """Build a Pyrogram Client mock that records send_message kwargs."""
    mock_msg = MagicMock()
    mock_msg.id = message_id

    mock_client = MagicMock()
    mock_client.send_message = AsyncMock(return_value=mock_msg)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_pyr = MagicMock()
    mock_pyr.Client = MagicMock(return_value=mock_client)
    return mock_pyr, mock_client


def test_26_send_message_uses_reply_to_message_id_for_forum_topics():
    """_send_message must call client.send_message with reply_to_message_id.

    message_thread_id is a Bot API parameter; Pyrogram's Client.send_message
    does NOT accept it.  This test pins the exact kwarg used.
    """
    mock_pyr, mock_client = _make_pyrogram_mock(message_id=42)

    with patch.dict(sys.modules, {"pyrogram": mock_pyr}):
        result = hd._send_message(-1234567890, 13350, "hello", "test_sess", "/tmp")

    assert result == 42
    call_kwargs = mock_client.send_message.call_args.kwargs
    assert "message_thread_id" not in call_kwargs, (
        "message_thread_id is a Bot API parameter — must not appear in Pyrogram call"
    )
    assert call_kwargs.get("reply_to_message_id") == 13350


def test_27_send_message_no_reply_to_when_topic_id_is_zero():
    """For DM / main chat (topic_id=0), send_message must omit reply_to_message_id."""
    mock_pyr, mock_client = _make_pyrogram_mock(message_id=77)

    with patch.dict(sys.modules, {"pyrogram": mock_pyr}):
        result = hd._send_message(-1234567890, 0, "hello", "test_sess", "/tmp")

    assert result == 77
    call_kwargs = mock_client.send_message.call_args.kwargs
    assert "reply_to_message_id" not in call_kwargs
    assert "message_thread_id" not in call_kwargs
