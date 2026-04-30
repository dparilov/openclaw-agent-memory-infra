"""Tests for scripts/fix-pretooluse-hook.sh"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "fix-pretooluse-hook.sh"


def run_script(*args, env=None):
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True, text=True, env=e,
    )


def _write_settings(path: Path, with_hook: bool) -> None:
    cfg = {"version": 1, "hooks": {}}
    if with_hook:
        cfg["hooks"]["PreToolUse"] = [
            {"matcher": ".*", "hooks": [{"type": "command", "command": "callback"}]}
        ]
    path.write_text(json.dumps(cfg, indent=2))


# ── 1. --help exits 0 ─────────────────────────────────────────────────────────

def test_help_exits_zero():
    r = run_script("--help")
    assert r.returncode == 0
    assert "Usage" in r.stdout or "usage" in r.stdout.lower() or "fix-pretooluse" in r.stdout


# ── 2. exits 2 when no hook present ─────────────────────────────────────────

def test_no_hook_exits_2():
    with tempfile.TemporaryDirectory() as tmp:
        settings = Path(tmp) / "settings.json"
        _write_settings(settings, with_hook=False)
        r = run_script("--dry-run", env={"HOME": tmp})
    assert r.returncode == 2, f"Expected 2 (no hook), got {r.returncode}\n{r.stdout}\n{r.stderr}"


# ── 3. detects hook + dry-run does not modify file ───────────────────────────

def test_dry_run_does_not_modify_settings():
    with tempfile.TemporaryDirectory() as tmp:
        claude_dir = Path(tmp) / ".claude"
        claude_dir.mkdir()
        settings = claude_dir / "settings.json"
        _write_settings(settings, with_hook=True)
        original = settings.read_text()
        r = run_script("--dry-run", "--disable-pretooluse-hook", env={"HOME": tmp})
        assert settings.read_text() == original, "dry-run must not modify settings.json"


# ── 4. removes hook from settings.json ───────────────────────────────────────

def test_removes_pretooluse_hook():
    with tempfile.TemporaryDirectory() as tmp:
        claude_dir = Path(tmp) / ".claude"
        claude_dir.mkdir()
        settings = claude_dir / "settings.json"
        _write_settings(settings, with_hook=True)
        r = run_script("--disable-pretooluse-hook", env={"HOME": tmp})
        # Even if gateway restart fails (not installed), hook should be removed
        cfg = json.loads(settings.read_text())
        assert "PreToolUse" not in cfg.get("hooks", {}), \
            f"PreToolUse hook still present after fix\nstdout={r.stdout}\nstderr={r.stderr}"


# ── 5. creates backup before modifying ───────────────────────────────────────

def test_creates_backup():
    with tempfile.TemporaryDirectory() as tmp:
        claude_dir = Path(tmp) / ".claude"
        claude_dir.mkdir()
        settings = claude_dir / "settings.json"
        _write_settings(settings, with_hook=True)
        run_script("--disable-pretooluse-hook", env={"HOME": tmp})
        backups = list(claude_dir.glob("settings.json.bak.*"))
        assert len(backups) >= 1, "No backup file created"


# ── 6. backup contains original hook ─────────────────────────────────────────

def test_backup_contains_original_content():
    with tempfile.TemporaryDirectory() as tmp:
        claude_dir = Path(tmp) / ".claude"
        claude_dir.mkdir()
        settings = claude_dir / "settings.json"
        _write_settings(settings, with_hook=True)
        original = settings.read_text()
        run_script("--disable-pretooluse-hook", env={"HOME": tmp})
        backups = list(claude_dir.glob("settings.json.bak.*"))
        assert backups, "No backup found"
        assert backups[0].read_text() == original, "Backup does not match original"


# ── 7. runbook doc exists and covers all 8 steps ─────────────────────────────

def test_runbook_doc_exists_and_covers_steps():
    doc = Path(__file__).parent.parent / "docs" / "PRETOOLUSE_HOOK_RUNBOOK.md"
    assert doc.exists(), "PRETOOLUSE_HOOK_RUNBOOK.md must exist"
    content = doc.read_text()
    for required in [
        "Do NOT retry",
        "settings.json",
        "Backup",
        "Disable",
        "Restart",
        "doctor",
        "harmless tool test",
        "Escalate",
    ]:
        assert required.lower() in content.lower(), f"Runbook missing: {required}"


# ── 8. script is executable ───────────────────────────────────────────────────

def test_script_is_executable():
    assert SCRIPT.exists(), "fix-pretooluse-hook.sh must exist"
    assert os.access(SCRIPT, os.X_OK), "fix-pretooluse-hook.sh must be executable"
