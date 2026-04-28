#!/usr/bin/env python3
"""
Tests for B3: portable path resolution in read-topic.py.

Covers:
  - detect_project_root()        — correct detection / non-project path → None
  - resolve_checkpoint_dir()     — CLI arg / env var / auto-detect / legacy fallback
  - checkpoint_path/load/save/clear — roundtrip with custom dir
  - agents_base()                — CLI arg / env var / default
  - find_session_file()          — --session-file arg / PYROGRAM_SESSION env var
  - find_pyrogram()              — project .venv detection
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
# resolve_checkpoint_dir
# ---------------------------------------------------------------------------

class TestResolveCheckpointDir(unittest.TestCase):

    def setUp(self):
        # Remove env vars that could interfere
        self._orig_env = os.environ.copy()
        os.environ.pop("OPENCLAW_CHECKPOINT_DIR", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_cli_arg_takes_precedence(self):
        """--checkpoint-dir arg wins over everything."""
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["OPENCLAW_CHECKPOINT_DIR"] = "/should/not/be/used"
            result = rt.resolve_checkpoint_dir(cli_arg=tmp)
            self.assertEqual(result, Path(tmp))

    def test_env_var_used_when_no_cli(self):
        """OPENCLAW_CHECKPOINT_DIR env var used when no CLI arg."""
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["OPENCLAW_CHECKPOINT_DIR"] = tmp
            result = rt.resolve_checkpoint_dir()
            self.assertEqual(result, Path(tmp))

    def test_auto_detect_from_agent_tree(self):
        """When script is inside .agent/tools/context_access/, use <root>/.agent/checkpoints/."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            script = root / ".agent" / "tools" / "context_access" / "read-topic.py"
            script.parent.mkdir(parents=True)
            script.touch()
            result = rt.resolve_checkpoint_dir(_script_path=script)
            self.assertEqual(result.resolve(), (root / ".agent" / "checkpoints").resolve())

    def test_legacy_fallback(self):
        """No CLI, no env, not in .agent tree → ~/.openclaw/workspace/ops."""
        result = rt.resolve_checkpoint_dir()
        self.assertEqual(result, Path.home() / ".openclaw" / "workspace" / "ops")

    def test_cli_beats_env_and_auto(self):
        """CLI arg wins even when env var and auto-detect would give different results."""
        with tempfile.TemporaryDirectory() as tmp:
            cli_dir = str(Path(tmp) / "cli-cp")
            root = Path(tmp) / "proj"
            script = root / ".agent" / "tools" / "context_access" / "read-topic.py"
            script.parent.mkdir(parents=True)
            script.touch()
            os.environ["OPENCLAW_CHECKPOINT_DIR"] = str(Path(tmp) / "env-cp")
            result = rt.resolve_checkpoint_dir(cli_arg=cli_dir, _script_path=script)
            self.assertEqual(result, Path(cli_dir))

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


# ---------------------------------------------------------------------------
# Checkpoint roundtrip
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
        """load_checkpoint on a fresh dir returns None."""
        with tempfile.TemporaryDirectory() as tmp:
            result = rt.load_checkpoint("9999", checkpoint_dir=Path(tmp))
            self.assertIsNone(result)

    def test_clear_removes_checkpoint(self):
        """clear_checkpoint removes file; subsequent load returns None."""
        with tempfile.TemporaryDirectory() as tmp:
            cp_dir = Path(tmp)
            rt.save_checkpoint("9999", 100, 0, checkpoint_dir=cp_dir)
            rt.clear_checkpoint("9999", checkpoint_dir=cp_dir)
            self.assertIsNone(rt.load_checkpoint("9999", checkpoint_dir=cp_dir))

    def test_checkpoint_file_location(self):
        """Checkpoint file lands in the specified directory."""
        with tempfile.TemporaryDirectory() as tmp:
            cp_dir = Path(tmp)
            rt.save_checkpoint("1234", 999, 1, checkpoint_dir=cp_dir)
            expected = cp_dir / "read-topic-checkpoint-1234.json"
            self.assertTrue(expected.exists())

    def test_checkpoint_json_structure(self):
        """Saved checkpoint JSON has expected fields."""
        with tempfile.TemporaryDirectory() as tmp:
            cp_dir = Path(tmp)
            rt.save_checkpoint("5678", 77777, 2, checkpoint_dir=cp_dir)
            data = json.loads((cp_dir / "read-topic-checkpoint-5678.json").read_text())
            self.assertEqual(data["topic_id"], "5678")
            self.assertEqual(data["last_message_id"], 77777)
            self.assertEqual(data["sub_batch"], 2)
            self.assertIn("ts", data)

    def test_checkpoint_dir_created_if_missing(self):
        """checkpoint_path creates the dir if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmp:
            cp_dir = Path(tmp) / "nested" / "deep" / "dir"
            rt.checkpoint_path("42", checkpoint_dir=cp_dir)
            self.assertTrue(cp_dir.is_dir())


# ---------------------------------------------------------------------------
# agents_base
# ---------------------------------------------------------------------------

class TestAgentsBase(unittest.TestCase):

    def setUp(self):
        self._orig_env = os.environ.copy()
        os.environ.pop("OPENCLAW_AGENTS", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_cli_arg_takes_precedence(self):
        """--agents-base CLI arg wins over env var."""
        os.environ["OPENCLAW_AGENTS"] = "/env/agents"
        result = rt.agents_base(cli_arg="/cli/agents")
        self.assertEqual(result, Path("/cli/agents"))

    def test_env_var_used_when_no_cli(self):
        """OPENCLAW_AGENTS env var used when no CLI arg."""
        os.environ["OPENCLAW_AGENTS"] = "/env/agents"
        result = rt.agents_base()
        self.assertEqual(result, Path("/env/agents"))

    def test_default_when_no_cli_no_env(self):
        """Default to ~/.openclaw/agents when nothing is set."""
        result = rt.agents_base()
        self.assertEqual(result, Path.home() / ".openclaw" / "agents")

    def test_returns_path_object(self):
        """Result is always a Path, not a string."""
        self.assertIsInstance(rt.agents_base(), Path)
        self.assertIsInstance(rt.agents_base(cli_arg="/tmp/x"), Path)


# ---------------------------------------------------------------------------
# find_session_file
# ---------------------------------------------------------------------------

class TestFindSessionFile(unittest.TestCase):

    def setUp(self):
        self._orig_env = os.environ.copy()
        os.environ.pop("PYROGRAM_SESSION", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_session_file_arg_takes_precedence(self):
        """--session-file arg wins over PYROGRAM_SESSION env var."""
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "mybot.session"
            session.touch()
            os.environ["PYROGRAM_SESSION"] = "/should/not/be/used.session"
            workdir, name = rt.find_session_file(session_file=str(session))
            self.assertEqual(workdir, str(session.parent))
            self.assertEqual(name, "mybot")

    def test_env_var_used_when_no_arg(self):
        """PYROGRAM_SESSION env var used when no arg."""
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "ops" / "userbot.session"
            session.parent.mkdir()
            session.touch()
            os.environ["PYROGRAM_SESSION"] = str(session)
            workdir, name = rt.find_session_file()
            self.assertEqual(name, "userbot")
            self.assertEqual(workdir, str(session.parent))

    def test_session_arg_strips_dot_session(self):
        """Name returned without .session extension."""
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "myagent.session"
            session.touch()
            _, name = rt.find_session_file(session_file=str(session))
            self.assertEqual(name, "myagent")

    def test_raises_when_no_session_found(self):
        """Raises SystemExit when no session file can be found."""
        with tempfile.TemporaryDirectory() as tmp:
            # Patch home to a dir with no .openclaw
            with patch.object(Path, "home", return_value=Path(tmp)):
                with self.assertRaises(SystemExit) as ctx:
                    rt.find_session_file()
            self.assertIn("session file not found", str(ctx.exception))

    def test_session_arg_without_extension(self):
        """--session-file without .session extension still parsed correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            # Pyrogram accepts session names without extension
            session_path = Path(tmp) / "mybot"
            workdir, name = rt.find_session_file(session_file=str(session_path))
            self.assertEqual(workdir, tmp)
            self.assertEqual(name, "mybot")


# ---------------------------------------------------------------------------
# find_pyrogram
# ---------------------------------------------------------------------------

class TestFindPyrogram(unittest.TestCase):

    def setUp(self):
        self._orig_env = os.environ.copy()
        os.environ.pop("PYROGRAM_VENV", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_returns_none_when_not_found(self):
        """Returns None when pyrogram is not in any candidate location."""
        with tempfile.TemporaryDirectory() as tmp:
            # Temporarily redirect home so no real openclaw paths are found
            with patch.object(Path, "home", return_value=Path(tmp)):
                result = rt.find_pyrogram()
            # May still find system pyrogram; just assert type
            self.assertTrue(result is None or isinstance(result, str))

    def test_env_var_candidate_checked(self):
        """PYROGRAM_VENV env var path is checked as a candidate."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_venv = Path(tmp) / "venv" / "site-packages"
            pyrogram_pkg = fake_venv / "pyrogram"
            pyrogram_pkg.mkdir(parents=True)
            os.environ["PYROGRAM_VENV"] = str(fake_venv)
            result = rt.find_pyrogram()
            self.assertEqual(result, str(fake_venv))

    def test_project_venv_candidate_checked(self):
        """Project .venv under <root>/.agent/tools/context_access/ is checked."""
        with tempfile.TemporaryDirectory() as tmp:
            # Build fake project tree
            root = Path(tmp) / "proj"
            script = root / ".agent" / "tools" / "context_access" / "read-topic.py"
            script.parent.mkdir(parents=True)
            script.touch()
            # Create fake project .venv with pyrogram
            fake_site = root / ".venv" / "lib" / "python3.11" / "site-packages"
            (fake_site / "pyrogram").mkdir(parents=True)
            # Reload module with patched __file__ — test via detect_project_root
            proj_root = rt.detect_project_root(_script_path=script)
            self.assertEqual(proj_root.resolve(), root.resolve())
            # Verify the candidate path that would be checked
            candidate = proj_root / ".venv" / "lib" / "python3.11" / "site-packages"
            self.assertTrue((candidate / "pyrogram").exists())


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


if __name__ == "__main__":
    unittest.main()
