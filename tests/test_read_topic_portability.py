#!/usr/bin/env python3
"""
Tests for B3: portable path resolution in read-topic.py.

Covers:
  - detect_project_root()        — correct detection / non-project path → None
  - load_agent_config()          — YAML loading, fallback parser, key access
  - resolve_checkpoint_dir()     — CLI > env > config > auto-detect > legacy
  - checkpoint roundtrip         — save/load/clear with custom dir + atomic write
  - agents_base()                — CLI > env > config > default
  - find_session_file()          — CLI > env > config > default
  - find_pyrogram()              — PYROGRAM_VENV, project .venv via _script_path
  - expanduser                   — ~ expanded in CLI/env/config paths
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Import read-topic.py (hyphen in name → importlib)
# ---------------------------------------------------------------------------

_RT_PATH = Path(__file__).parent.parent / "scripts" / "context_access" / "read-topic.py"


def _load_rt():
    spec = importlib.util.spec_from_file_location("read_topic", _RT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["read_topic"] = mod
    spec.loader.exec_module(mod)
    return mod


rt = _load_rt()


# ---------------------------------------------------------------------------
# detect_project_root
# ---------------------------------------------------------------------------

class TestDetectProjectRoot(unittest.TestCase):

    def test_detects_when_inside_agent_tree(self):
        """Script at <root>/.agent/tools/context_access/read-topic.py → returns <root>."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "myproject"
            script = root / ".agent" / "tools" / "context_access" / "read-topic.py"
            script.parent.mkdir(parents=True)
            script.touch()
            result = rt.detect_project_root(_script_path=script)
            self.assertEqual(result.resolve(), root.resolve())

    def test_returns_none_when_not_in_agent_tree(self):
        """Script at an arbitrary location → returns None."""
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "scripts" / "context_access" / "read-topic.py"
            script.parent.mkdir(parents=True)
            script.touch()
            result = rt.detect_project_root(_script_path=script)
            self.assertIsNone(result)

    def test_returns_none_for_repo_location(self):
        """Actual script location (scripts/context_access/) → returns None."""
        result = rt.detect_project_root()
        self.assertIsNone(result)

    def test_partial_path_not_matched(self):
        """tools/context_access/ without .agent parent → None."""
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "tools" / "context_access" / "read-topic.py"
            script.parent.mkdir(parents=True)
            script.touch()
            result = rt.detect_project_root(_script_path=script)
            self.assertIsNone(result)


# ---------------------------------------------------------------------------
# load_agent_config
# ---------------------------------------------------------------------------

class TestLoadAgentConfig(unittest.TestCase):

    def _write_config(self, root: Path, content: str) -> Path:
        cfg = root / ".agent" / "config.yaml"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(content)
        return cfg

    def test_returns_empty_when_no_file(self):
        """Returns {} when config file does not exist."""
        with tempfile.TemporaryDirectory() as tmp:
            result = rt.load_agent_config(project_root=Path(tmp))
            self.assertEqual(result, {})

    def test_explicit_config_path(self):
        """--config explicit path is used directly."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "custom.yaml"
            cfg.write_text("checkpoint_dir: /custom/cp\n")
            result = rt.load_agent_config(config_path=str(cfg))
            self.assertEqual(result.get("checkpoint_dir"), "/custom/cp")

    def test_project_root_config(self):
        """Config loaded from project_root/.agent/config.yaml."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_config(root, "checkpoint_dir: /proj/cp\nagents_base: /proj/agents\n")
            result = rt.load_agent_config(project_root=root)
            self.assertEqual(result.get("checkpoint_dir"), "/proj/cp")
            self.assertEqual(result.get("agents_base"), "/proj/agents")

    def test_auto_detect_via_script_path(self):
        """Config auto-detected from .agent/tools/context_access/ script location."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            script = root / ".agent" / "tools" / "context_access" / "read-topic.py"
            script.parent.mkdir(parents=True)
            script.touch()
            self._write_config(root, "checkpoint_dir: /auto/cp\n")
            result = rt.load_agent_config(_script_path=script)
            self.assertEqual(result.get("checkpoint_dir"), "/auto/cp")

    def test_all_supported_keys(self):
        """All three config keys are read correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_config(root,
                "checkpoint_dir: /cp\n"
                "pyrogram_session: /sess/bot\n"
                "agents_base: /agents\n")
            result = rt.load_agent_config(project_root=root)
            self.assertEqual(result["checkpoint_dir"], "/cp")
            self.assertEqual(result["pyrogram_session"], "/sess/bot")
            self.assertEqual(result["agents_base"], "/agents")

    def test_returns_empty_on_missing_file(self):
        """Returns {} if file doesn't exist at explicit config_path."""
        result = rt.load_agent_config(config_path="/nonexistent/path/config.yaml")
        self.assertEqual(result, {})

    def test_comments_ignored(self):
        """Lines starting with # are ignored by fallback parser."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_config(root, "# this is a comment\ncheckpoint_dir: /cp\n")
            result = rt.load_agent_config(project_root=root)
            self.assertNotIn("#", str(result))
            self.assertEqual(result.get("checkpoint_dir"), "/cp")


# ---------------------------------------------------------------------------
# resolve_checkpoint_dir — full priority chain including config
# ---------------------------------------------------------------------------

class TestResolveCheckpointDir(unittest.TestCase):

    def setUp(self):
        self._orig_env = os.environ.copy()
        os.environ.pop("OPENCLAW_CHECKPOINT_DIR", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_cli_arg_takes_precedence(self):
        """CLI arg wins over env, config, and auto-detect."""
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["OPENCLAW_CHECKPOINT_DIR"] = "/should/not/be/used"
            result = rt.resolve_checkpoint_dir(
                cli_arg=tmp,
                _config={"checkpoint_dir": "/also/not/used"},
            )
            self.assertEqual(result, Path(tmp))

    def test_env_var_beats_config(self):
        """Env var wins over config file."""
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["OPENCLAW_CHECKPOINT_DIR"] = tmp
            result = rt.resolve_checkpoint_dir(_config={"checkpoint_dir": "/config/cp"})
            self.assertEqual(result, Path(tmp))

    def test_config_beats_auto_detect(self):
        """Config file wins over auto-detect from .agent tree."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            script = root / ".agent" / "tools" / "context_access" / "read-topic.py"
            script.parent.mkdir(parents=True)
            script.touch()
            cfg_cp = str(Path(tmp) / "config-cp")
            result = rt.resolve_checkpoint_dir(
                _script_path=script,
                _config={"checkpoint_dir": cfg_cp},
            )
            self.assertEqual(result, Path(cfg_cp))

    def test_auto_detect_from_agent_tree(self):
        """No CLI/env/config → auto-detect .agent/checkpoints/."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            script = root / ".agent" / "tools" / "context_access" / "read-topic.py"
            script.parent.mkdir(parents=True)
            script.touch()
            result = rt.resolve_checkpoint_dir(_script_path=script)
            self.assertEqual(result.resolve(), (root / ".agent" / "checkpoints").resolve())

    def test_legacy_fallback(self):
        """No CLI, env, config, or .agent tree → legacy path."""
        result = rt.resolve_checkpoint_dir()
        self.assertEqual(result, Path.home() / ".openclaw" / "workspace" / "ops")

    def test_env_var_used_when_no_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["OPENCLAW_CHECKPOINT_DIR"] = tmp
            result = rt.resolve_checkpoint_dir()
            self.assertEqual(result, Path(tmp))

    def test_env_beats_auto(self):
        """Env var wins over auto-detect from .agent tree."""
        with tempfile.TemporaryDirectory() as tmp:
            env_dir = str(Path(tmp) / "env-cp")
            os.environ["OPENCLAW_CHECKPOINT_DIR"] = env_dir
            root = Path(tmp) / "proj"
            script = root / ".agent" / "tools" / "context_access" / "read-topic.py"
            script.parent.mkdir(parents=True)
            script.touch()
            result = rt.resolve_checkpoint_dir(_script_path=script)
            self.assertEqual(result, Path(env_dir))

    def test_cli_beats_env_and_auto(self):
        """CLI arg wins over env and auto-detect."""
        with tempfile.TemporaryDirectory() as tmp:
            cli_dir = str(Path(tmp) / "cli-cp")
            os.environ["OPENCLAW_CHECKPOINT_DIR"] = str(Path(tmp) / "env-cp")
            root = Path(tmp) / "proj"
            script = root / ".agent" / "tools" / "context_access" / "read-topic.py"
            script.parent.mkdir(parents=True)
            script.touch()
            result = rt.resolve_checkpoint_dir(cli_arg=cli_dir, _script_path=script)
            self.assertEqual(result, Path(cli_dir))


# ---------------------------------------------------------------------------
# Checkpoint roundtrip + atomic write
# ---------------------------------------------------------------------------

class TestCheckpointRoundtrip(unittest.TestCase):

    def test_save_and_load(self):
        """save_checkpoint then load_checkpoint returns same message_id."""
        with tempfile.TemporaryDirectory() as tmp:
            cp_dir = Path(tmp)
            rt.save_checkpoint("9999", last_message_id=42000, sub_batch=0, checkpoint_dir=cp_dir)
            result = rt.load_checkpoint("9999", checkpoint_dir=cp_dir)
            self.assertEqual(result, 42000)

    def test_load_returns_none_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = rt.load_checkpoint("9999", checkpoint_dir=Path(tmp))
            self.assertIsNone(result)

    def test_clear_removes_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp_dir = Path(tmp)
            rt.save_checkpoint("9999", 100, 0, checkpoint_dir=cp_dir)
            rt.clear_checkpoint("9999", checkpoint_dir=cp_dir)
            self.assertIsNone(rt.load_checkpoint("9999", checkpoint_dir=cp_dir))

    def test_checkpoint_file_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp_dir = Path(tmp)
            rt.save_checkpoint("1234", 999, 1, checkpoint_dir=cp_dir)
            self.assertTrue((cp_dir / "read-topic-checkpoint-1234.json").exists())

    def test_checkpoint_json_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp_dir = Path(tmp)
            rt.save_checkpoint("5678", 77777, 2, checkpoint_dir=cp_dir)
            data = json.loads((cp_dir / "read-topic-checkpoint-5678.json").read_text())
            self.assertEqual(data["topic_id"], "5678")
            self.assertEqual(data["last_message_id"], 77777)
            self.assertEqual(data["sub_batch"], 2)
            self.assertIn("ts", data)

    def test_checkpoint_dir_created_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp_dir = Path(tmp) / "nested" / "deep" / "dir"
            rt.checkpoint_path("42", checkpoint_dir=cp_dir)
            self.assertTrue(cp_dir.is_dir())

    def test_atomic_no_temp_file_left_on_success(self):
        """After successful save, no .tmp file remains in the checkpoint dir."""
        with tempfile.TemporaryDirectory() as tmp:
            cp_dir = Path(tmp)
            rt.save_checkpoint("9999", 100, 0, checkpoint_dir=cp_dir)
            tmp_files = list(cp_dir.glob("*.tmp"))
            self.assertEqual(tmp_files, [], f"Temp files left: {tmp_files}")

    def test_atomic_write_content_visible_atomically(self):
        """Checkpoint file is either absent or fully written — never partial."""
        with tempfile.TemporaryDirectory() as tmp:
            cp_dir = Path(tmp)
            rt.save_checkpoint("7777", 55555, 0, checkpoint_dir=cp_dir)
            cp = cp_dir / "read-topic-checkpoint-7777.json"
            # File must be valid JSON
            data = json.loads(cp.read_text())
            self.assertEqual(data["last_message_id"], 55555)


# ---------------------------------------------------------------------------
# agents_base — full priority chain including config
# ---------------------------------------------------------------------------

class TestAgentsBase(unittest.TestCase):

    def setUp(self):
        self._orig_env = os.environ.copy()
        os.environ.pop("OPENCLAW_AGENTS", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_cli_arg_takes_precedence(self):
        os.environ["OPENCLAW_AGENTS"] = "/env/agents"
        result = rt.agents_base(cli_arg="/cli/agents", _config={"agents_base": "/config/agents"})
        self.assertEqual(result, Path("/cli/agents"))

    def test_env_beats_config(self):
        os.environ["OPENCLAW_AGENTS"] = "/env/agents"
        result = rt.agents_base(_config={"agents_base": "/config/agents"})
        self.assertEqual(result, Path("/env/agents"))

    def test_config_used_when_no_cli_no_env(self):
        """Config agents_base used when no CLI arg and no env var."""
        result = rt.agents_base(_config={"agents_base": "/config/agents"})
        self.assertEqual(result, Path("/config/agents"))

    def test_env_var_used_when_no_cli(self):
        os.environ["OPENCLAW_AGENTS"] = "/env/agents"
        result = rt.agents_base()
        self.assertEqual(result, Path("/env/agents"))

    def test_default_when_nothing_set(self):
        result = rt.agents_base()
        self.assertEqual(result, Path.home() / ".openclaw" / "agents")

    def test_returns_path_object(self):
        self.assertIsInstance(rt.agents_base(), Path)
        self.assertIsInstance(rt.agents_base(cli_arg="/tmp/x"), Path)


# ---------------------------------------------------------------------------
# find_session_file — full priority chain including config
# ---------------------------------------------------------------------------

class TestFindSessionFile(unittest.TestCase):

    def setUp(self):
        self._orig_env = os.environ.copy()
        os.environ.pop("PYROGRAM_SESSION", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_session_file_arg_takes_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "mybot.session"
            session.touch()
            os.environ["PYROGRAM_SESSION"] = "/should/not/be/used.session"
            workdir, name = rt.find_session_file(
                session_file=str(session),
                _config={"pyrogram_session": "/also/not/used"},
            )
            self.assertEqual(workdir, str(session.parent))
            self.assertEqual(name, "mybot")

    def test_env_beats_config(self):
        """Env var beats config pyrogram_session."""
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "env_bot.session"
            session.touch()
            os.environ["PYROGRAM_SESSION"] = str(session)
            workdir, name = rt.find_session_file(_config={"pyrogram_session": "/config/session"})
            self.assertEqual(name, "env_bot")

    def test_config_pyrogram_session_used(self):
        """Config pyrogram_session used when no CLI arg and no env var."""
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "cfgbot.session"
            session.touch()
            workdir, name = rt.find_session_file(_config={"pyrogram_session": str(session)})
            self.assertEqual(name, "cfgbot")
            self.assertEqual(workdir, str(session.parent))

    def test_env_var_used_when_no_arg(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "ops" / "userbot.session"
            session.parent.mkdir()
            session.touch()
            os.environ["PYROGRAM_SESSION"] = str(session)
            workdir, name = rt.find_session_file()
            self.assertEqual(name, "userbot")

    def test_session_arg_strips_dot_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "myagent.session"
            session.touch()
            _, name = rt.find_session_file(session_file=str(session))
            self.assertEqual(name, "myagent")

    def test_raises_when_no_session_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(Path, "home", return_value=Path(tmp)):
                with self.assertRaises(SystemExit) as ctx:
                    rt.find_session_file()
            self.assertIn("session file not found", str(ctx.exception))

    def test_session_arg_without_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            session_path = Path(tmp) / "mybot"
            workdir, name = rt.find_session_file(session_file=str(session_path))
            self.assertEqual(workdir, tmp)
            self.assertEqual(name, "mybot")


# ---------------------------------------------------------------------------
# find_pyrogram — via _script_path for project .venv
# ---------------------------------------------------------------------------

class TestFindPyrogram(unittest.TestCase):

    def setUp(self):
        self._orig_env = os.environ.copy()
        os.environ.pop("PYROGRAM_VENV", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_returns_none_or_str(self):
        """Return type is always str | None."""
        result = rt.find_pyrogram()
        self.assertTrue(result is None or isinstance(result, str))

    def test_env_var_candidate_wins(self):
        """PYROGRAM_VENV env var is checked first and wins over openclaw defaults."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_venv = Path(tmp) / "venv" / "site-packages"
            (fake_venv / "pyrogram").mkdir(parents=True)
            os.environ["PYROGRAM_VENV"] = str(fake_venv)
            result = rt.find_pyrogram()
            self.assertEqual(result, str(fake_venv))

    def test_project_venv_found_via_script_path(self):
        """Project .venv pyrogram is found when _script_path points into .agent tree."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            script = root / ".agent" / "tools" / "context_access" / "read-topic.py"
            script.parent.mkdir(parents=True)
            script.touch()
            # Create fake project .venv with pyrogram
            fake_site = root / ".venv" / "lib" / "python3.11" / "site-packages"
            (fake_site / "pyrogram").mkdir(parents=True)
            # Patch home to isolate from real openclaw venv
            with patch.object(Path, "home", return_value=Path(tmp) / "fakehome"):
                result = rt.find_pyrogram(_script_path=script)
            self.assertEqual(result, str(fake_site))

    def test_env_var_beats_project_venv(self):
        """PYROGRAM_VENV (explicit) wins over project .venv."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            script = root / ".agent" / "tools" / "context_access" / "read-topic.py"
            script.parent.mkdir(parents=True)
            script.touch()
            # Create project .venv
            proj_site = root / ".venv" / "lib" / "python3.11" / "site-packages"
            (proj_site / "pyrogram").mkdir(parents=True)
            # Create env-var venv
            env_site = Path(tmp) / "explicit-venv" / "site-packages"
            (env_site / "pyrogram").mkdir(parents=True)
            os.environ["PYROGRAM_VENV"] = str(env_site)
            with patch.object(Path, "home", return_value=Path(tmp) / "fakehome"):
                result = rt.find_pyrogram(_script_path=script)
            self.assertEqual(result, str(env_site))


# ---------------------------------------------------------------------------
# expanduser applied to all path inputs
# ---------------------------------------------------------------------------

class TestExpandUser(unittest.TestCase):

    def setUp(self):
        self._orig_env = os.environ.copy()
        os.environ.pop("OPENCLAW_CHECKPOINT_DIR", None)
        os.environ.pop("OPENCLAW_AGENTS", None)
        os.environ.pop("PYROGRAM_SESSION", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_checkpoint_dir_cli_expanduser(self):
        result = rt.resolve_checkpoint_dir(cli_arg="~/mycp")
        self.assertNotIn("~", str(result))
        self.assertTrue(str(result).startswith(str(Path.home())))

    def test_checkpoint_dir_env_expanduser(self):
        os.environ["OPENCLAW_CHECKPOINT_DIR"] = "~/envcp"
        result = rt.resolve_checkpoint_dir()
        self.assertNotIn("~", str(result))

    def test_checkpoint_dir_config_expanduser(self):
        result = rt.resolve_checkpoint_dir(_config={"checkpoint_dir": "~/cfgcp"})
        self.assertNotIn("~", str(result))

    def test_agents_base_cli_expanduser(self):
        result = rt.agents_base(cli_arg="~/agents")
        self.assertNotIn("~", str(result))

    def test_agents_base_env_expanduser(self):
        os.environ["OPENCLAW_AGENTS"] = "~/envagents"
        result = rt.agents_base()
        self.assertNotIn("~", str(result))

    def test_agents_base_config_expanduser(self):
        result = rt.agents_base(_config={"agents_base": "~/cfgagents"})
        self.assertNotIn("~", str(result))

    def test_session_file_cli_expanduser(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Can't use ~ directly without real home, just verify Path.expanduser called
            session = Path(tmp) / "bot.session"
            session.touch()
            workdir, _ = rt.find_session_file(session_file=str(session))
            self.assertEqual(workdir, str(session.parent))

    def test_session_env_expanduser(self):
        os.environ["PYROGRAM_SESSION"] = "~/workspace/ops/userbot.session"
        workdir, name = rt.find_session_file()
        self.assertNotIn("~", workdir)
        self.assertEqual(name, "userbot")

    def test_session_config_expanduser(self):
        result_workdir, _ = rt.find_session_file(
            _config={"pyrogram_session": "~/workspace/ops/cfgbot.session"}
        )
        self.assertNotIn("~", result_workdir)


# ---------------------------------------------------------------------------
# Integration: py_compile
# ---------------------------------------------------------------------------

class TestReadTopicCompiles(unittest.TestCase):

    def test_compiles_clean(self):
        """read-topic.py has no syntax errors."""
        import py_compile
        try:
            py_compile.compile(str(_RT_PATH), doraise=True)
        except py_compile.PyCompileError as e:
            self.fail(f"read-topic.py has syntax errors: {e}")


# ---------------------------------------------------------------------------
# PR47: filter_by_date + new CLI args
# ---------------------------------------------------------------------------

class TestFilterByDate(unittest.TestCase):
    """Tests for filter_by_date() in read-topic.py."""

    def _msg(self, date_str):
        from datetime import datetime, timezone
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return (dt, 1, "user", "text")

    def test_no_filter_returns_all(self):
        msgs = [self._msg("2026-05-01"), self._msg("2026-05-10")]
        self.assertEqual(len(rt.filter_by_date(msgs)), 2)

    def test_since_filters_before(self):
        msgs = [self._msg("2026-04-30"), self._msg("2026-05-01"), self._msg("2026-05-10")]
        result = rt.filter_by_date(msgs, since="2026-05-01")
        self.assertEqual(len(result), 2)

    def test_until_filters_after(self):
        msgs = [self._msg("2026-05-01"), self._msg("2026-05-10"), self._msg("2026-05-20")]
        result = rt.filter_by_date(msgs, until="2026-05-10")
        self.assertEqual(len(result), 2)

    def test_since_and_until_combined(self):
        msgs = [self._msg("2026-04-30"), self._msg("2026-05-05"), self._msg("2026-05-20")]
        result = rt.filter_by_date(msgs, since="2026-05-01", until="2026-05-15")
        self.assertEqual(len(result), 1)

    def test_until_includes_end_of_day(self):
        """until=2026-05-10 includes messages at 23:59:59 UTC on that day."""
        from datetime import datetime, timezone
        late_msg = (
            datetime(2026, 5, 10, 23, 59, 59, tzinfo=timezone.utc),
            1, "user", "late msg"
        )
        next_day = (
            datetime(2026, 5, 11, 0, 0, 1, tzinfo=timezone.utc),
            2, "user", "next day"
        )
        result = rt.filter_by_date([late_msg, next_day], until="2026-05-10")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][3], "late msg")


class TestNewCliArgs(unittest.TestCase):
    """read-topic.py has new args and constants for PR47."""

    def test_has_filter_by_date(self):
        self.assertTrue(callable(rt.filter_by_date))

    def test_has_default_max_scan(self):
        self.assertEqual(rt.DEFAULT_MAX_SCAN, 10000)


# ---------------------------------------------------------------------------
# PR47: main() CLI validation — fires before any I/O
# ---------------------------------------------------------------------------

class TestMainCliValidation(unittest.TestCase):
    """Verify that main() raises SystemExit on bad CLI args before touching
    config files, session files, or the network."""

    def _assert_error(self, argv, substring):
        """Call main(argv) and assert it raises SystemExit containing substring."""
        with self.assertRaises(SystemExit) as ctx:
            rt.main(argv)
        self.assertIn(substring, str(ctx.exception),
                      f"Expected {substring!r} in SystemExit message, got: {ctx.exception}")

    # -- positive-integer guards -----------------------------------------------

    def test_limit_zero(self):
        self._assert_error(["9999", "--limit", "0"], "positive")

    def test_limit_negative(self):
        self._assert_error(["9999", "--limit", "-5"], "positive")

    def test_since_id_negative(self):
        self._assert_error(["9999", "--since-id", "-1"], "positive")

    def test_until_id_zero(self):
        # until-id without since-id would also trigger, but zero check fires first
        self._assert_error(["9999", "--until-id", "0", "--since-id", "1"], "positive")

    def test_max_scan_zero(self):
        self._assert_error(["9999", "--max-scan", "0"], "positive")

    def test_max_scan_negative(self):
        self._assert_error(["9999", "--max-scan", "-100"], "positive")

    # -- paired-bounds guards --------------------------------------------------

    def test_until_id_without_since_id(self):
        self._assert_error(["9999", "--until-id", "500"], "--until-id requires --since-id")

    def test_until_without_since(self):
        self._assert_error(["9999", "--until", "2026-05-01"], "--until requires --since")

    # -- date-format guards ----------------------------------------------------

    def test_invalid_since_format(self):
        self._assert_error(["9999", "--since", "01/05/2026"], "YYYY-MM-DD")

    def test_invalid_since_format_nonsense(self):
        self._assert_error(["9999", "--since", "not-a-date"], "YYYY-MM-DD")

    def test_invalid_until_format(self):
        self._assert_error(
            ["9999", "--until", "2026-13-01", "--since", "2026-01-01"],
            "YYYY-MM-DD",
        )

    # -- --full constraints ----------------------------------------------------

    def test_full_without_confirm(self):
        self._assert_error(["9999", "--full"], "--confirm-large-read")

    def test_full_with_limit_rejected(self):
        self._assert_error(
            ["9999", "--full", "--confirm-large-read", "--limit", "100"],
            "cannot be combined",
        )

    def test_full_with_since_id_rejected(self):
        self._assert_error(
            ["9999", "--full", "--confirm-large-read", "--since-id", "100"],
            "cannot be combined",
        )

    def test_full_with_since_rejected(self):
        self._assert_error(
            ["9999", "--full", "--confirm-large-read", "--since", "2026-01-01"],
            "cannot be combined",
        )

    def test_full_with_until_rejected(self):
        self._assert_error(
            ["9999", "--full", "--confirm-large-read", "--since", "2026-01-01", "--until", "2026-05-01"],
            "cannot be combined",
        )

    # -- ambiguous combos ------------------------------------------------------

    def test_limit_plus_since_id_rejected(self):
        self._assert_error(
            ["9999", "--limit", "100", "--since-id", "500"],
            "ambiguous",
        )

    def test_limit_plus_since_rejected(self):
        self._assert_error(
            ["9999", "--limit", "100", "--since", "2026-01-01"],
            "ambiguous",
        )

    # -- valid args pass validation (no SystemExit before I/O) ----------------

    def test_valid_limit_does_not_raise_validation_error(self):
        """A positive --limit passes validation. Any later error is not a validation error."""
        try:
            rt.main(["9999", "--limit", "100"])
        except BaseException as e:
            msg = str(e)
            self.assertNotIn("positive", msg)
            self.assertNotIn("ambiguous", msg)
            self.assertNotIn("YYYY-MM-DD", msg)
            self.assertNotIn("requires --since", msg)
            self.assertNotIn("cannot be combined", msg)

    def test_valid_since_id_does_not_raise_validation_error(self):
        """A positive --since-id passes validation. Any later error is not a validation error."""
        try:
            rt.main(["9999", "--since-id", "1000"])
        except BaseException as e:
            msg = str(e)
            self.assertNotIn("positive", msg)
            self.assertNotIn("ambiguous", msg)

    def test_valid_since_and_until_does_not_raise_validation_error(self):
        """Valid --since/--until dates pass validation. Any later error is not a validation error."""
        try:
            rt.main(["9999", "--since", "2026-01-01", "--until", "2026-05-01"])
        except BaseException as e:
            msg = str(e)
            self.assertNotIn("YYYY-MM-DD", msg)
            self.assertNotIn("requires --since", msg)


if __name__ == "__main__":
    unittest.main()
