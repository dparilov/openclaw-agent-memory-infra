#!/usr/bin/env python3
"""
onboard-project.py — Deterministic Fast Project Onboarding CLI

Replaces the manual Phase 0 / Path B → Phase 2/3 prompt flow.
Runs read-only preflight, detects scaffold, syncs infra tools (dry-run by
default), optionally creates a PR, and runs an initial-index dry-run.

Usage:
    python3 scripts/onboard-project.py \
        --target /path/to/project \
        --mode fast \
        --repo https://github.com/org/repo \
        --chat-id -1003596522926 \
        --infra-topic 15222 \
        --coder-topic 7301 \
        --reviewer-topic 13350 \
        --escalation @pariloff \
        [--sync-tools] \
        [--create-pr]
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------
EXIT_SUCCESS = 0
EXIT_VALIDATION = 1
EXIT_PREFLIGHT = 2
EXIT_NO_SCAFFOLD = 3
EXIT_SYNC_FAILED = 4
EXIT_COMPILE_FAILED = 5
EXIT_GIT_FAILED = 6
EXIT_INDEX_FAILED = 7

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class CheckResult(NamedTuple):
    name: str
    status: str  # PASS, WARN, FAIL, SKIP
    notes: str


class ToolDiff(NamedTuple):
    filename: str
    action: str  # COPY, UPDATE, UNCHANGED, EXTRA
    notes: str


class IndexResult(NamedTuple):
    topic: str
    role: str
    status: str
    notes: str


# ---------------------------------------------------------------------------
# URL normalisation
# ---------------------------------------------------------------------------
_SSH_RE = re.compile(r"^git@github\.com:(.+?)(?:\.git)?$")
_HTTPS_RE = re.compile(r"^https://github\.com/(.+?)(?:\.git)?$")


def normalise_repo_url(url: str) -> str:
    """Return canonical https://github.com/<owner>/<repo> form."""
    url = url.strip().rstrip("/")
    m = _SSH_RE.match(url)
    if m:
        return f"https://github.com/{m.group(1)}"
    m = _HTTPS_RE.match(url)
    if m:
        return f"https://github.com/{m.group(1)}"
    return url.rstrip("/").removesuffix(".git")


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], cwd: str | Path | None = None) -> tuple[int, str, str]:
    """Run a command; return (returncode, stdout, stderr). Never raises."""
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"
    except Exception as exc:  # noqa: BLE001
        return 1, "", str(exc)


# ---------------------------------------------------------------------------
# File hashing
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Step 1 — Fast Preflight
# ---------------------------------------------------------------------------

def run_preflight(
    *,
    infra_root: Path,
    target: Path,
    repo: str,
    strict: bool,
) -> list[CheckResult]:
    results: list[CheckResult] = []

    def add(name: str, status: str, notes: str = "") -> None:
        results.append(CheckResult(name, status, notes))

    has_scripts = (infra_root / "scripts" / "context_access").is_dir()
    add(
        "memory-infra repo detected",
        "PASS" if has_scripts else "FAIL",
        str(infra_root) if has_scripts else f"scripts/context_access/ missing in {infra_root}",
    )

    for script_name in ("initial-index.py", "manage-candidates.py"):
        p = infra_root / "scripts" / "context_access" / script_name
        add(
            f"infra script: {script_name}",
            "PASS" if p.is_file() else "FAIL",
            str(p) if p.is_file() else f"missing: {p}",
        )

    add(
        "target repo exists locally",
        "PASS" if target.is_dir() else "FAIL",
        str(target),
    )

    if target.is_dir():
        rc, stdout, stderr = _run(["git", "-C", str(target), "remote", "get-url", "origin"])
        if rc == 0:
            actual = normalise_repo_url(stdout)
            expected = normalise_repo_url(repo)
            if actual == expected:
                add("target remote matches --repo", "PASS", actual)
            else:
                add("target remote matches --repo", "WARN",
                    f"expected {expected!r}, got {actual!r}")
        else:
            add("target remote matches --repo", "WARN", f"git remote failed: {stderr}")
    else:
        add("target remote matches --repo", "SKIP", "target dir missing")

    gh_path = shutil.which("gh")
    add("GitHub CLI (gh) exists", "PASS" if gh_path else "FAIL",
        gh_path or "not found in PATH")

    if gh_path:
        rc, stdout, stderr = _run(["gh", "auth", "status"])
        add(
            "gh auth status",
            "PASS" if rc == 0 else "FAIL",
            stdout.splitlines()[0] if stdout else stderr.splitlines()[0] if stderr else "",
        )

    oc_path = shutil.which("openclaw")
    add(
        "OpenClaw CLI (openclaw) exists",
        "PASS" if oc_path else ("FAIL" if strict else "WARN"),
        oc_path or "not found in PATH",
    )

    def _oc_check(name: str, cmd: list[str]) -> None:
        if not oc_path:
            add(name, "SKIP", "openclaw not found")
            return
        rc, stdout, stderr = _run(cmd)
        if rc == 0:
            add(name, "PASS", stdout.splitlines()[0] if stdout else "ok")
        else:
            note = (stdout or stderr).splitlines()[0] if (stdout or stderr) else f"exit {rc}"
            add(name, "FAIL" if strict else "WARN", note)

    _oc_check("openclaw gateway status", ["openclaw", "gateway", "status"])
    _oc_check("openclaw channels status --probe", ["openclaw", "channels", "status", "--probe"])
    _oc_check("openclaw models status", ["openclaw", "models", "status"])

    return results


# ---------------------------------------------------------------------------
# Step 3 — Scaffold detection
# ---------------------------------------------------------------------------

def detect_scaffold(target: Path) -> list[CheckResult]:
    checks = [
        (".agent exists", target / ".agent"),
        (".agent/AGENT_CONTEXT.md exists", target / ".agent" / "AGENT_CONTEXT.md"),
        (".agent/tools/context_access exists", target / ".agent" / "tools" / "context_access"),
    ]
    results = []
    for name, path in checks:
        ok = path.exists()
        results.append(CheckResult(
            name, "PASS" if ok else "FAIL",
            str(path) if ok else f"missing: {path}",
        ))
    return results


# ---------------------------------------------------------------------------
# Step 4 — Tool sync diff + apply
# ---------------------------------------------------------------------------

def compute_tool_diff(source_dir: Path, dest_dir: Path) -> list[ToolDiff]:
    """Classify each .py file as COPY / UPDATE / UNCHANGED / EXTRA."""
    diffs: list[ToolDiff] = []
    source_files = {p.name: p for p in source_dir.glob("*.py")}
    dest_files = {p.name: p for p in dest_dir.glob("*.py")} if dest_dir.exists() else {}

    for name, src_path in sorted(source_files.items()):
        if name not in dest_files:
            diffs.append(ToolDiff(name, "COPY", "missing in destination"))
        else:
            action = "UNCHANGED" if _sha256(src_path) == _sha256(dest_files[name]) else "UPDATE"
            diffs.append(ToolDiff(name, action, "" if action == "UNCHANGED" else "content differs"))

    for name in sorted(dest_files):
        if name not in source_files:
            diffs.append(ToolDiff(name, "EXTRA", "not in source; not touched"))

    return diffs


def apply_tool_sync(source_dir: Path, dest_dir: Path, diffs: list[ToolDiff]) -> list[ToolDiff]:
    """Copy COPY/UPDATE files; return updated diffs."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    applied: list[ToolDiff] = []
    for diff in diffs:
        if diff.action in ("COPY", "UPDATE"):
            shutil.copy2(source_dir / diff.filename, dest_dir / diff.filename)
            applied.append(ToolDiff(diff.filename, diff.action, "copied"))
        else:
            applied.append(diff)
    return applied


# ---------------------------------------------------------------------------
# Step 4b — Compile + help check
# ---------------------------------------------------------------------------

def check_compile_and_help(
    tools_dir: Path,
    initial_index_path: Path,
) -> tuple[CheckResult, CheckResult]:
    py_files = sorted(tools_dir.glob("*.py"))
    compile_errors: list[str] = []
    for f in py_files:
        rc, _, stderr = _run([sys.executable, "-m", "py_compile", str(f)])
        if rc != 0:
            compile_errors.append(f"{f.name}: {stderr}")

    compile_result = CheckResult(
        "py_compile all tools",
        "PASS" if not compile_errors else "FAIL",
        "; ".join(compile_errors) if compile_errors else f"{len(py_files)} files ok",
    )

    rc, stdout, stderr = _run([sys.executable, str(initial_index_path), "--help"])
    help_result = CheckResult(
        "initial-index.py --help",
        "PASS" if rc == 0 else "FAIL",
        stdout.splitlines()[0] if stdout else stderr.splitlines()[0] if stderr else f"exit {rc}",
    )
    return compile_result, help_result


# ---------------------------------------------------------------------------
# Step 5 — Safe git staging allowlist + PR
# ---------------------------------------------------------------------------

SAFE_STAGE_PATTERN = re.compile(r"^\.agent/tools/context_access/[^/]+\.py$")


def is_safe_to_stage(rel_path: str) -> bool:
    """Return True only for .agent/tools/context_access/*.py paths."""
    return bool(SAFE_STAGE_PATTERN.match(rel_path))


def plan_git_pr(
    *,
    target: Path,
    repo: str,
    branch: str,
    base_branch: str | None,
    commit_message: str,
    diffs: list[ToolDiff],
    create_pr: bool,
) -> tuple[list[str], list[str]]:
    to_stage = [
        str(Path(".agent/tools/context_access") / d.filename)
        for d in diffs if d.action in ("COPY", "UPDATE")
    ]
    unsafe = [p for p in to_stage if not is_safe_to_stage(p)]
    warnings: list[str] = []
    if unsafe:
        warnings.append(f"Unsafe paths blocked from staging: {unsafe}")
        to_stage = [p for p in to_stage if is_safe_to_stage(p)]

    cmds: list[str] = []
    if not to_stage:
        warnings.append("No files to stage — nothing changed or all unchanged")
        return cmds, warnings

    base_arg = base_branch or "(current branch)"
    cmds.append(f"git -C {target} checkout -b {branch}")
    for p in to_stage:
        cmds.append(f"git -C {target} add {p}")
    cmds.append(f'git -C {target} commit -m "{commit_message}"')
    cmds.append(f"git -C {target} push origin {branch}")
    cmds.append(
        f'gh pr create --repo {repo} --title "{commit_message}" '
        f'--body "Infra tool sync via onboard-project.py" '
        f'--head {branch} --base {base_arg}'
    )
    return cmds, warnings


def execute_git_pr(
    *,
    target: Path,
    repo: str,
    branch: str,
    base_branch: str | None,
    commit_message: str,
    diffs: list[ToolDiff],
) -> tuple[bool, str]:
    to_stage = [
        str(Path(".agent/tools/context_access") / d.filename)
        for d in diffs
        if d.action in ("COPY", "UPDATE")
        and is_safe_to_stage(str(Path(".agent/tools/context_access") / d.filename))
    ]
    if not to_stage:
        return False, "Nothing to stage"

    # Fix 1: fail-fast on branch mismatch when --base-branch is explicitly provided
    if base_branch is not None:
        rc, current_branch, _ = _run(["git", "-C", str(target), "rev-parse", "--abbrev-ref", "HEAD"])
        if rc == 0 and current_branch and current_branch != base_branch:
            return False, (
                f"Current target branch is '{current_branch}', but --base-branch is '{base_branch}'. "
                f"Checkout '{base_branch}' first or rerun without --create-pr."
            )

    if base_branch is None:
        rc, stdout, _ = _run(["git", "-C", str(target), "rev-parse", "--abbrev-ref", "HEAD"])
        base_branch = stdout if rc == 0 and stdout else "master"

    steps: list[tuple[list[str], str]] = [
        (["git", "-C", str(target), "checkout", "-b", branch], "checkout -b"),
        *[(["git", "-C", str(target), "add", p], f"add {p}") for p in to_stage],
        (["git", "-C", str(target), "commit", "-m", commit_message], "commit"),
        (["git", "-C", str(target), "push", "origin", branch], "push"),
        (
            ["gh", "pr", "create", "--repo", repo, "--title", commit_message,
             "--body", "Infra tool sync via onboard-project.py",
             "--head", branch, "--base", base_branch],
            "gh pr create",
        ),
    ]
    for cmd, label in steps:
        rc, stdout, stderr = _run(cmd)
        if rc != 0:
            return False, f"{label} failed (exit {rc}): {stderr or stdout}"
    return True, "PR created"


# ---------------------------------------------------------------------------
# Step 6 — Index dry-run
# ---------------------------------------------------------------------------

def run_index_dryruns(
    *,
    initial_index_path: Path,
    coder_topic: str,
    reviewer_topic: str,
    infra_topic: str,
) -> list[IndexResult]:
    results = []
    for topic, role in [(coder_topic, "coder"), (reviewer_topic, "reviewer"), (infra_topic, "infra")]:
        rc, stdout, stderr = _run(
            [sys.executable, str(initial_index_path), "--topic", topic, "--dry-run"]
        )
        if rc == 0:
            note = stdout.splitlines()[0] if stdout else "dry-run ok"
            results.append(IndexResult(topic, role, "PASS", note))
        else:
            note = (stderr or stdout).splitlines()[0] if (stderr or stdout) else f"exit {rc}"
            results.append(IndexResult(topic, role, "FAIL", note))
    return results


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def _table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [
        max(len(h), max((len(str(r[i])) for r in rows), default=0))
        for i, h in enumerate(headers)
    ]
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    header = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    lines = [header, sep]
    for row in rows:
        lines.append("| " + " | ".join(str(row[i]).ljust(widths[i]) for i in range(len(headers))) + " |")
    return "\n".join(lines)


def format_ack(
    *,
    repo: str,
    target: Path,
    chat_id: str,
    infra_topic: str,
    coder_topic: str,
    reviewer_topic: str,
    escalation: str,
) -> str:
    return (
        "PROJECT_TARGET_ACK\n"
        f"mode: C\n"
        f"repo_url: {repo}\n"
        f"local_path: {target}\n"
        f"chat_id: {chat_id}\n"
        f"infra_topic: {infra_topic}\n"
        f"coder_topic: {coder_topic}\n"
        f"reviewer_topic: {reviewer_topic}\n"
        f"escalation: {escalation}\n"
    )


def format_report(
    *,
    mode: str,
    target: Path,
    repo: str,
    chat_id: str,
    infra_topic: str,
    coder_topic: str,
    reviewer_topic: str,
    escalation: str,
    preflight: list[CheckResult],
    scaffold: list[CheckResult],
    diffs: list[ToolDiff],
    compile_check: CheckResult | None,
    help_check: CheckResult | None,
    git_plan_cmds: list[str],
    git_plan_warnings: list[str],
    git_executed: bool | None,
    git_message: str,
    create_pr: bool,
    sync_tools: bool,
    branch: str,
    index_results: list[IndexResult],
    warnings: list[str],
    blockers: list[str],
    next_steps: list[str],
) -> str:
    lines: list[str] = [
        "ONBOARD PROJECT REPORT",
        "======================",
        f"Mode:          {mode}",
        f"Target:        {target}",
        f"Repo:          {repo}",
        "Topics:",
        f"  infra:       {infra_topic}",
        f"  coder:       {coder_topic}",
        f"  reviewer:    {reviewer_topic}",
        f"Escalation:    {escalation}",
        "",
        "PROJECT_TARGET_ACK",
        "------------------",
        "mode: C",
        f"repo_url: {repo}",
        f"local_path: {target}",
        f"chat_id: {chat_id}",
        f"infra_topic: {infra_topic}",
        f"coder_topic: {coder_topic}",
        f"reviewer_topic: {reviewer_topic}",
        f"escalation: {escalation}",
        "",
        "Preflight",
        "---------",
    ]
    lines.append(_table(["Check", "Status", "Notes"], [[r.name, r.status, r.notes] for r in preflight]))
    lines += ["", "Scaffold", "--------"]
    lines.append(_table(["Check", "Status", "Notes"], [[r.name, r.status, r.notes] for r in scaffold]))
    lines += ["", "Tool Sync", "---------"]
    if diffs:
        label_suffix = "" if sync_tools else " (dry-run)"
        sync_rows = [[d.filename, f"{d.action}{label_suffix}", d.notes] for d in diffs]
        lines.append(_table(["File", "Action", "Notes"], sync_rows))
    else:
        lines.append("  (no tool files found)")
    if compile_check:
        lines.append(f"\n  compile: [{compile_check.status}] {compile_check.notes}")
    if help_check:
        lines.append(f"  --help:  [{help_check.status}] {help_check.notes}")
    lines += ["", "Git / PR", "--------"]
    if not create_pr:
        lines += [
            f"  branch:  {branch}",
            "  commit:  (skipped — --create-pr not passed)",
            "  PR:      (skipped)",
            "  skipped: --create-pr not passed",
        ]
        if git_plan_cmds:
            lines.append("  commands that would run:")
            lines += [f"    {cmd}" for cmd in git_plan_cmds]
        lines += [f"  warning: {w}" for w in git_plan_warnings]
    else:
        lines.append(f"  branch:  {branch}")
        lines.append(f"  result:  {'OK — ' if git_executed else 'FAILED — '}{git_message}")
    lines += ["", "Index Dry-Run", "-------------"]
    if index_results:
        lines.append(_table(
            ["Topic", "Role", "Status", "Notes"],
            [[r.topic, r.role, r.status, r.notes] for r in index_results],
        ))
    else:
        lines.append("  (skipped)")
    lines += ["", "Warnings:"]
    lines += ([f"  - {w}" for w in warnings] if warnings else ["  none"])
    lines += ["", "Blockers:"]
    lines += ([f"  - {b}" for b in blockers] if blockers else ["  none"])
    lines += ["", "Next:"]
    lines += ([f"  {s}" for s in next_steps] if next_steps else ["  no recommended next steps"])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Deterministic fast project onboarding CLI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--target", required=True)
    p.add_argument("--mode", choices=["fast", "full", "repair", "audit"], default="fast")
    p.add_argument("--repo", required=True)
    p.add_argument("--chat-id", required=True, dest="chat_id")
    p.add_argument("--infra-topic", required=True, dest="infra_topic")
    p.add_argument("--coder-topic", required=True, dest="coder_topic")
    p.add_argument("--reviewer-topic", required=True, dest="reviewer_topic")
    p.add_argument("--escalation", required=True)
    p.add_argument("--sync-tools", action="store_true")
    p.add_argument("--dry-run", action="store_true", default=False)
    p.add_argument("--create-pr", action="store_true", dest="create_pr")
    p.add_argument("--branch", default=None)
    p.add_argument("--base-branch", default=None, dest="base_branch")
    p.add_argument("--commit-message", default="infra: sync agent context tools", dest="commit_message")
    p.add_argument("--strict", action="store_true")
    return p


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:  # noqa: C901
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.mode != "fast":
        print(f"ERROR: --mode {args.mode!r} is not implemented in PR27 MVP. Use --mode fast.", file=sys.stderr)
        return EXIT_VALIDATION

    # Fix 2: --dry-run and --sync-tools are mutually exclusive
    if args.dry_run and args.sync_tools:
        print("ERROR: --dry-run cannot be combined with --sync-tools", file=sys.stderr)
        return EXIT_VALIDATION

    script_dir = Path(__file__).resolve().parent
    infra_root = script_dir.parent
    target = Path(args.target).resolve()
    source_tools_dir = infra_root / "scripts" / "context_access"
    dest_tools_dir = target / ".agent" / "tools" / "context_access"
    branch = args.branch or f"infra/sync-agent-tools-{date.today().isoformat()}"

    warnings: list[str] = []
    blockers: list[str] = []
    next_steps: list[str] = []
    git_executed: bool | None = None
    git_message = ""
    compile_check: CheckResult | None = None
    help_check: CheckResult | None = None
    index_results: list[IndexResult] = []
    diffs: list[ToolDiff] = []
    git_plan_cmds: list[str] = []
    git_plan_warnings: list[str] = []
    scaffold: list[CheckResult] = []

    preflight = run_preflight(
        infra_root=infra_root, target=target, repo=args.repo, strict=args.strict,
    )

    def _report(code: int) -> int:
        print(format_report(
            mode=args.mode, target=target, repo=args.repo,
            chat_id=args.chat_id, infra_topic=args.infra_topic,
            coder_topic=args.coder_topic, reviewer_topic=args.reviewer_topic,
            escalation=args.escalation, preflight=preflight, scaffold=scaffold,
            diffs=diffs, compile_check=compile_check, help_check=help_check,
            git_plan_cmds=git_plan_cmds, git_plan_warnings=git_plan_warnings,
            git_executed=git_executed, git_message=git_message,
            create_pr=args.create_pr, sync_tools=args.sync_tools, branch=branch,
            index_results=index_results, warnings=warnings,
            blockers=blockers, next_steps=next_steps,
        ))
        return code

    critical_fails = [
        r for r in preflight
        if r.status == "FAIL" and r.name in ("memory-infra repo detected", "gh auth status")
    ]
    if critical_fails:
        for r in critical_fails:
            print(f"PREFLIGHT HARD FAIL: {r.name}: {r.notes}", file=sys.stderr)
        scaffold = detect_scaffold(target)
        return _report(EXIT_PREFLIGHT)

    for r in preflight:
        if r.status == "FAIL":
            warnings.append(f"Preflight: {r.name}: {r.notes}")

    scaffold = detect_scaffold(target)
    agent_dir = target / ".agent"

    if not agent_dir.exists():
        blockers.append(".agent/ directory missing — run setup.sh first")
        next_steps.append(f"bash {infra_root}/setup.sh --target {target} --topic-id <topic-id>")
        return _report(EXIT_NO_SCAFFOLD)

    if not dest_tools_dir.exists():
        warnings.append(".agent/tools/context_access/ missing — will be created on --sync-tools")

    diffs = compute_tool_diff(source_tools_dir, dest_tools_dir)
    if args.sync_tools:
        diffs = apply_tool_sync(source_tools_dir, dest_tools_dir, diffs)

    check_dir = dest_tools_dir if (args.sync_tools and dest_tools_dir.exists()) else source_tools_dir
    initial_index_check = check_dir / "initial-index.py"
    if initial_index_check.exists():
        compile_check, help_check = check_compile_and_help(check_dir, initial_index_check)
        if compile_check.status == "FAIL":
            blockers.append(f"Tool compile failed: {compile_check.notes}")
            return _report(EXIT_COMPILE_FAILED)
        if help_check.status == "FAIL":
            warnings.append(f"initial-index.py --help failed: {help_check.notes}")
    else:
        warnings.append("initial-index.py not found — skipping compile/help check")

    git_plan_cmds, git_plan_warnings = plan_git_pr(
        target=target, repo=args.repo, branch=branch,
        base_branch=args.base_branch, commit_message=args.commit_message,
        diffs=diffs, create_pr=args.create_pr,
    )
    warnings.extend(git_plan_warnings)

    if args.create_pr:
        if not args.sync_tools:
            blockers.append("--create-pr requires --sync-tools")
            git_executed = False
            git_message = "--sync-tools not passed"
        else:
            git_executed, git_message = execute_git_pr(
                target=target, repo=args.repo, branch=branch,
                base_branch=args.base_branch, commit_message=args.commit_message,
                diffs=diffs,
            )
            if not git_executed:
                return _report(EXIT_GIT_FAILED)

    index_tool = dest_tools_dir / "initial-index.py"
    if not index_tool.exists():
        index_tool = source_tools_dir / "initial-index.py"

    if index_tool.exists():
        index_results = run_index_dryruns(
            initial_index_path=index_tool,
            coder_topic=args.coder_topic,
            reviewer_topic=args.reviewer_topic,
            infra_topic=args.infra_topic,
        )
        for r in index_results:
            if r.status == "FAIL":
                warnings.append(f"Index dry-run FAIL {r.role} (topic {r.topic}): {r.notes}")
    else:
        warnings.append("initial-index.py not found; index dry-run skipped")

    if not args.sync_tools:
        copy_count = sum(1 for d in diffs if d.action in ("COPY", "UPDATE"))
        if copy_count > 0:
            next_steps.append(f"Re-run with --sync-tools to copy {copy_count} changed/missing tool file(s)")
    if not args.create_pr and args.sync_tools:
        next_steps.append("Re-run with --create-pr to open a PR for the synced tools")
    if not next_steps:
        next_steps.append("Tools are up to date. Proceed to initial indexing write approval.")

    return _report(EXIT_SUCCESS if not blockers else EXIT_VALIDATION)


if __name__ == "__main__":
    sys.exit(main())
