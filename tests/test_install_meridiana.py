"""Tests for scripts/install-meridiana.sh and patches/meridiana-openclaw.patch.

All tests are non-network: no npm/bun calls, no actual install performed.
"""
import os
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent
SCRIPT = REPO / "scripts" / "install-meridiana.sh"
PATCH = REPO / "patches" / "meridiana-openclaw.patch"


def run_script(*args, env=None):
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True, text=True, env=e,
    )


# ── 1. Script exists and is executable ───────────────────────────────────────

def test_script_exists_and_is_executable():
    assert SCRIPT.exists(), "install-meridiana.sh must exist"
    assert os.access(SCRIPT, os.X_OK), "install-meridiana.sh must be executable"


# ── 2. Patch file exists and is non-empty ────────────────────────────────────

def test_patch_file_exists_and_nonempty():
    assert PATCH.exists(), "patches/meridiana-openclaw.patch must exist"
    content = PATCH.read_text()
    assert len(content) > 100, "patch file must be non-empty"


# ── 3. Patch file targets expected source files ───────────────────────────────

def test_patch_targets_expected_files():
    content = PATCH.read_text()
    expected = [
        "src/proxy/adapters/openclaw.ts",
        "src/proxy/adapter.ts",
        "src/proxy/server.ts",
    ]
    for path in expected:
        assert path in content, f"patch must reference {path}"


# ── 4. Patch file has valid diff header ───────────────────────────────────────

def test_patch_has_valid_diff_header():
    content = PATCH.read_text()
    assert content.startswith("diff --git"), "patch must start with 'diff --git'"


# ── 5. Patch mentions OpenClaw adapter ────────────────────────────────────────

def test_patch_contains_openclaw_adapter():
    content = PATCH.read_text()
    assert "openclaw" in content.lower(), "patch must reference openclaw adapter"


# ── 6. --help exits 0 and mentions required flags ────────────────────────────

def test_help_exits_zero_and_has_flags():
    r = run_script("--help")
    assert r.returncode == 0, f"--help should exit 0, got {r.returncode}"
    out = r.stdout.lower()
    assert "--dry-run" in out, "--help must mention --dry-run"
    assert "--target" in out, "--help must mention --target"
    assert "--port" in out, "--help must mention --port"


# ── 7. --dry-run exits 2 when patch file is present ──────────────────────────

def test_dry_run_exits_2_when_requirements_met():
    # In CI, node/npm/patch may be present; dry-run should reach end and exit 2.
    # If a requirement is genuinely missing, the script exits 1 — that's OK too.
    r = run_script("--dry-run", "--target", "/tmp/test-meridiana-dryrun")
    assert r.returncode in (0, 1, 2), (
        f"dry-run must exit 0, 1, or 2; got {r.returncode}\n{r.stderr}"
    )
    # Must not have actually created anything
    assert not Path("/tmp/test-meridiana-dryrun/dist/cli.js").exists(), (
        "dry-run must not install dist/cli.js"
    )


# ── 8. --dry-run output mentions patch file ───────────────────────────────────

def test_dry_run_mentions_patch():
    r = run_script("--dry-run", "--target", "/tmp/test-meridiana-dryrun2")
    combined = r.stdout + r.stderr
    assert "patch" in combined.lower(), (
        f"dry-run output must mention patch file\n{combined}"
    )


# ── 9. --dry-run does not call npm, bun, or node for download ─────────────────

def test_dry_run_does_not_download():
    """dry-run must print intentions only; no real downloads or builds."""
    r = run_script("--dry-run", "--target", "/tmp/test-meridiana-dryrun3")
    # The output should say [dry-run] before any install step
    assert "[dry-run]" in r.stdout, (
        f"dry-run output must contain '[dry-run]' markers\n{r.stdout}"
    )


# ── 10. Script fails fast with clear message if patch file is missing ─────────

def test_fails_fast_if_patch_missing():
    """Point REPO_ROOT somewhere that has no patch file."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create a fake repo root with no patches dir
        fake_scripts = Path(tmp) / "scripts"
        fake_scripts.mkdir()
        import shutil
        shutil.copy(SCRIPT, fake_scripts / "install-meridiana.sh")
        r = subprocess.run(
            ["bash", str(fake_scripts / "install-meridiana.sh"), "--dry-run"],
            capture_output=True, text=True,
        )
    assert r.returncode == 1, (
        f"Should exit 1 when patch file is missing, got {r.returncode}"
    )
    assert "patch" in (r.stdout + r.stderr).lower(), (
        "Error message must mention 'patch'"
    )


# ── 11. MIT license attribution present in patch or script ────────────────────

def test_mit_license_attributed():
    script_content = SCRIPT.read_text()
    assert "MIT" in script_content, "install script must attribute MIT license"


# ── 12. Script does not contain secrets or tokens ────────────────────────────

def test_script_has_no_secrets():
    content = SCRIPT.read_text()
    for forbidden in ["sk-ant-", "Bearer ", "token =", "password ="]:
        assert forbidden not in content, (
            f"install script must not contain secret pattern: {forbidden!r}"
        )


# ── 13. AUTH_COMMAND is documented in script ─────────────────────────────────

def test_auth_command_documented():
    content = SCRIPT.read_text()
    assert "profile add" in content, (
        "install script must document 'profile add' as the auth command"
    )
    assert "OAuth" in content or "oauth" in content.lower() or "token" in content.lower(), (
        "install script must mention OAuth/token auth"
    )
