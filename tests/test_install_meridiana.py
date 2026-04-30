"""Tests for scripts/install-meridiana.sh (vendored-dist approach).

All tests are non-network: no npm calls, no actual install performed.
The install script copies pre-built JS from vendor/meridiana-dist/ and then
runs `npm ci --omit=dev` (reproducible, lockfile-pinned) for runtime deps.
No bun, no build step.

patches/meridiana-openclaw.patch remains in the repo as a documentation
artifact (historical record of the 6-commit OpenClaw diff).
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent
SCRIPT = REPO / "scripts" / "install-meridiana.sh"
VENDOR_DIR = REPO / "vendor" / "meridiana-dist"
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


# ── 2. Vendor directory exists with expected files ───────────────────────────

def test_vendor_dir_exists_with_cli():
    assert VENDOR_DIR.exists(), f"vendor dir must exist: {VENDOR_DIR}"
    assert (VENDOR_DIR / "cli.js").exists(), "vendor/meridiana-dist/cli.js must exist"


def test_vendor_dir_has_js_files():
    js_files = list(VENDOR_DIR.glob("*.js"))
    assert len(js_files) >= 10, (
        f"vendor dir must have >=10 JS files, found {len(js_files)}"
    )


# ── 3. Lockfile present ───────────────────────────────────────────────────────

def test_vendor_lockfile_exists():
    lockfile = VENDOR_DIR / "package-lock.json"
    assert lockfile.exists(), "vendor/meridiana-dist/package-lock.json must exist"
    data = json.loads(lockfile.read_text())
    assert data.get("lockfileVersion", 0) >= 2, (
        "package-lock.json must be lockfileVersion >= 2"
    )


# ── 4. Dependency versions are exact (no ^ or ~) ─────────────────────────────

def test_vendor_package_json_deps_are_exact():
    pkg = json.loads((VENDOR_DIR / "package.json").read_text())
    deps = pkg.get("dependencies", {})
    for name, version in deps.items():
        assert not version.startswith("^"), (
            f"dependency {name!r} must be exact (no ^): {version!r}"
        )
        assert not version.startswith("~"), (
            f"dependency {name!r} must be exact (no ~): {version!r}"
        )


def test_vendor_package_json_has_runtime_deps():
    pkg = json.loads((VENDOR_DIR / "package.json").read_text())
    deps = pkg.get("dependencies", {})
    assert "@anthropic-ai/claude-agent-sdk" in deps, (
        "package.json must declare @anthropic-ai/claude-agent-sdk"
    )
    assert "ws" in deps, "package.json must declare ws"
    assert deps["@anthropic-ai/claude-agent-sdk"] == "0.2.89", (
        f"claude-agent-sdk must be pinned to 0.2.89, got {deps['@anthropic-ai/claude-agent-sdk']!r}"
    )
    assert deps["ws"] == "8.20.0", (
        f"ws must be pinned to 8.20.0, got {deps['ws']!r}"
    )


def test_vendor_package_json_version():
    pkg = json.loads((VENDOR_DIR / "package.json").read_text())
    assert pkg.get("version") == "1.30.2", (
        f"vendor package.json must pin version 1.30.2, got {pkg.get('version')!r}"
    )


def test_vendor_package_json_mit_attribution():
    pkg = json.loads((VENDOR_DIR / "package.json").read_text())
    meridiana = pkg.get("_meridiana", {})
    assert "MIT" in meridiana.get("baseLicense", ""), (
        "package.json _meridiana.baseLicense must mention MIT"
    )


# ── 5. Patch file kept as documentation artifact ──────────────────────────────

def test_patch_doc_artifact_exists_and_nonempty():
    """The patch file is kept as historical documentation, not applied during install."""
    assert PATCH.exists(), (
        "patches/meridiana-openclaw.patch must exist as documentation artifact"
    )
    content = PATCH.read_text()
    assert len(content) > 100, "patch file must be non-empty"
    assert "diff --git" in content, "patch file must be a valid git diff"


# ── 6. --help exits 0 and documents all flags ────────────────────────────────

def test_help_exits_zero_and_has_flags():
    r = run_script("--help")
    assert r.returncode == 0, f"--help should exit 0, got {r.returncode}"
    out = r.stdout.lower()
    assert "--dry-run" in out, "--help must mention --dry-run"
    assert "--target" in out, "--help must mention --target"
    assert "--port" in out, "--help must mention --port"


# ── 7. --dry-run exits exactly 2 when node/npm and vendor are present ─────────

def test_dry_run_exits_2():
    """When node, npm, and vendor dir are all present, --dry-run must exit 2."""
    if not shutil.which("node") or not shutil.which("npm"):
        import pytest
        pytest.skip("node/npm not available in this environment")
    r = run_script("--dry-run", "--target", "/tmp/test-meridiana-dryrun")
    assert r.returncode == 2, (
        f"--dry-run must exit 2 (dry-run complete), got {r.returncode}\n"
        f"stdout: {r.stdout}\nstderr: {r.stderr}"
    )
    assert not Path("/tmp/test-meridiana-dryrun/dist/cli.js").exists(), (
        "--dry-run must not create dist/cli.js"
    )


# ── 8. --dry-run output mentions npm ci ───────────────────────────────────────

def test_dry_run_mentions_npm_ci():
    r = run_script("--dry-run", "--target", "/tmp/test-meridiana-dryrun2")
    assert "[dry-run]" in r.stdout, (
        f"--dry-run output must contain '[dry-run]' markers\n{r.stdout}"
    )
    assert "npm ci" in r.stdout, (
        f"--dry-run output must mention 'npm ci'\n{r.stdout}"
    )


# ── 9. Install script uses npm ci (not plain npm install) ─────────────────────

def test_script_uses_npm_ci():
    content = SCRIPT.read_text()
    assert "npm ci --omit=dev" in content, (
        "install script must use 'npm ci --omit=dev' for reproducible install"
    )
    assert "npm install --omit=dev" not in content, (
        "install script must not fall back to plain 'npm install --omit=dev'"
    )


# ── 10. Install script checks for lockfile ────────────────────────────────────

def test_script_checks_lockfile():
    content = SCRIPT.read_text()
    assert "package-lock.json" in content, (
        "install script must check for package-lock.json"
    )


# ── 11. Script fails fast when vendor dir is missing ──────────────────────────

def test_fails_fast_if_vendor_dir_missing():
    """Script must exit 1 if run from a dir with no vendor/meridiana-dist/."""
    with tempfile.TemporaryDirectory() as tmp:
        fake_scripts = Path(tmp) / "scripts"
        fake_scripts.mkdir()
        shutil.copy(SCRIPT, fake_scripts / "install-meridiana.sh")
        r = subprocess.run(
            ["bash", str(fake_scripts / "install-meridiana.sh"), "--dry-run"],
            capture_output=True, text=True,
        )
    assert r.returncode == 1, (
        f"Should exit 1 when vendor dir is missing, got {r.returncode}"
    )
    combined = r.stdout + r.stderr
    assert any(word in combined.lower() for word in ("vendor", "dist", "cli.js")), (
        f"Error must mention vendor/dist/cli.js\n{combined}"
    )


# ── 12. MIT license attribution ───────────────────────────────────────────────

def test_mit_license_attributed():
    content = SCRIPT.read_text()
    assert "MIT" in content, "install script must attribute MIT license"


# ── 13. No secrets in script ─────────────────────────────────────────────────

def test_script_has_no_secrets():
    content = SCRIPT.read_text()
    for forbidden in ["sk-ant-", "Bearer ", "token =", "password ="]:
        assert forbidden not in content, (
            f"install script must not contain secret pattern: {forbidden!r}"
        )


# ── 14. Auth command documented ───────────────────────────────────────────────

def test_auth_command_documented():
    content = SCRIPT.read_text()
    assert "profile add" in content, (
        "install script must document 'profile add' as the auth command"
    )
    assert any(w in content for w in ("OAuth", "oauth", "token", "Token")), (
        "install script must mention OAuth/token auth"
    )
