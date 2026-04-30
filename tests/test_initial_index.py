"""Tests for scripts/context_access/initial-index.py

Uses a fake ~/.openclaw/agents/<agent>/sessions/*-topic-<id>.jsonl layout
compatible with archive-batch-v2.py's find_topic_paths() pattern.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "context_access" / "initial-index.py"
ARCHIVE_BATCH = Path(__file__).parent.parent / "scripts" / "context_access" / "archive-batch-v2.py"

ARCHITECTURE_MSG = (
    "We decided to use PostgreSQL for storage. "
    "This architecture decision was made after evaluating trade-offs."
)
FEATURE_MSG = "Implemented the new auth module. Adding support for OAuth2."


def _make_fake_agents_base(tmp: Path, topic_id: str, messages: list[dict]) -> Path:
    """Create fake agents_base/<agent>/sessions/*-topic-<id>.jsonl structure."""
    agents_base = tmp / "agents"
    session_dir = agents_base / "agent-001" / "sessions"
    session_dir.mkdir(parents=True)
    session_file = session_dir / f"20260101T000000-topic-{topic_id}.jsonl"
    with session_file.open("w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")
    return agents_base


def run_script(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True,
    )


# ── 1. --help exits 0 ─────────────────────────────────────────────────────────

def test_help_exits_zero():
    r = run_script("--help")
    assert r.returncode == 0, f"--help returned {r.returncode}\n{r.stderr}"
    assert "topic" in r.stdout.lower()


# ── 2. artifact creation ──────────────────────────────────────────────────────

def test_artifact_creation():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        agents_base = _make_fake_agents_base(tmp, "7301", [
            {"role": "user", "content": ARCHITECTURE_MSG},
            {"role": "assistant", "content": FEATURE_MSG},
        ])
        out_dir = tmp / "output"
        r = run_script(
            "--topic", "7301",
            "--agents-base", str(agents_base),
            "--output-dir", str(out_dir),
        )
        assert r.returncode == 0, f"exit {r.returncode}\nstdout={r.stdout}\nstderr={r.stderr}"
        assert (out_dir / "index_meta.json").exists(), "index_meta.json missing"
        assert (out_dir / "timeline.json").exists(), "timeline.json missing"
        assert (out_dir / "cluster_map.json").exists(), "cluster_map.json missing"
        assert (out_dir / "sensitive_map.json").exists(), "sensitive_map.json missing"
        assert (out_dir / "recovery_index.json").exists(), "recovery_index.json missing"


# ── 3. sensitive values never stored ─────────────────────────────────────────

def test_sensitive_redaction():
    secret = "SUPER_SECRET_API_KEY_99XYZ"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        agents_base = _make_fake_agents_base(tmp, "7302", [
            {"role": "user", "content": f"api_key={secret}"},
        ])
        out_dir = tmp / "output"
        r = run_script(
            "--topic", "7302",
            "--agents-base", str(agents_base),
            "--output-dir", str(out_dir),
        )
        assert r.returncode == 0, f"exit {r.returncode}\nstderr={r.stderr}"
        for f in out_dir.rglob("*.json"):
            content = f.read_text()
            assert secret not in content, f"Secret leaked into {f.name}"


# ── 4. sensitive category stored but not value ────────────────────────────────

def test_detect_sensitive_no_value_stored():
    password = "hunter2absolutelysecure"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        agents_base = _make_fake_agents_base(tmp, "7303", [
            {"role": "user", "content": f"password={password} is the default"},
        ])
        out_dir = tmp / "output"
        r = run_script(
            "--topic", "7303",
            "--agents-base", str(agents_base),
            "--output-dir", str(out_dir),
        )
        assert r.returncode == 0, f"exit {r.returncode}\nstderr={r.stderr}"
        sm = out_dir / "sensitive_map.json"
        assert sm.exists(), "sensitive_map.json must exist"
        data = json.loads(sm.read_text())
        assert "credential" in data, "credential category must be detected"
        for f in out_dir.rglob("*.json"):
            assert password not in f.read_text(), f"password value leaked into {f.name}"


# ── 5. dry-run writes nothing ─────────────────────────────────────────────────

def test_dry_run_no_files_written():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        agents_base = _make_fake_agents_base(tmp, "7304", [
            {"role": "user", "content": "architecture decision: we use Redis for caching"},
        ])
        out_dir = tmp / "output"
        r = run_script(
            "--topic", "7304",
            "--agents-base", str(agents_base),
            "--output-dir", str(out_dir),
            "--dry-run",
        )
        assert r.returncode == 0, f"exit {r.returncode}\nstderr={r.stderr}"
        assert not out_dir.exists() or not any(out_dir.iterdir()), \
            "dry-run must not write any files"


# ── 6. gitignore fragment covers all runtime dirs ─────────────────────────────

def test_gitignore_fragment_covers_runtime_memory():
    frag = Path(__file__).parent.parent / "templates" / "agent-gitignore.fragment"
    assert frag.exists(), "agent-gitignore.fragment must exist"
    content = frag.read_text()
    assert ".agent/memory/" not in content.splitlines()[0:5] or \
        ".agent/memory/index/" in content, \
        "Fragment must NOT wholesale-ignore .agent/memory/ root"
    for required in [
        ".agent/memory/index/",
        ".agent/memory/candidates/",
        ".agent/memory/raw/",
        "!.agent/memory/README.md",
        "!.agent/memory/**/.gitkeep",
    ]:
        assert required in content, f"Fragment must contain: {required}"


# ── 7. architecture_decision cluster detected ─────────────────────────────────

def test_detect_clusters_architecture():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        agents_base = _make_fake_agents_base(tmp, "7305", [
            {"role": "user", "content": ARCHITECTURE_MSG},
        ])
        out_dir = tmp / "output"
        r = run_script(
            "--topic", "7305",
            "--agents-base", str(agents_base),
            "--output-dir", str(out_dir),
        )
        assert r.returncode == 0, f"exit {r.returncode}\nstderr={r.stderr}"
        cm = json.loads((out_dir / "cluster_map.json").read_text())
        assert "architecture_decision" in cm, \
            f"architecture_decision not detected; got: {list(cm.keys())}"


# ── 8. window splitting ───────────────────────────────────────────────────────

def test_make_windows_splits_correctly():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # 25 messages with window_size=10 → 3 windows
        msgs = [{"role": "user", "content": f"message {i}"} for i in range(25)]
        agents_base = _make_fake_agents_base(tmp, "7306", msgs)
        out_dir = tmp / "output"
        r = run_script(
            "--topic", "7306",
            "--agents-base", str(agents_base),
            "--output-dir", str(out_dir),
            "--window-size", "10",
        )
        assert r.returncode == 0, f"exit {r.returncode}\nstderr={r.stderr}"
        meta = json.loads((out_dir / "index_meta.json").read_text())
        assert meta["total_windows"] == 3, \
            f"expected 3 windows for 25 msgs/size 10, got {meta['total_windows']}"
        assert meta["total_messages"] == 25
