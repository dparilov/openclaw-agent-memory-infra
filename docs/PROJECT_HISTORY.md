# Project History

Observable facts about the `dparilov/openclaw-agent-memory-infra` repository.  
No causal claims are made about tool behaviour or session state across entries.

---

## PR Reference Table

| PR | Title | State | Date |
|----|-------|-------|------|
| [#1](https://github.com/dparilov/openclaw-agent-memory-infra/pull/1) | fix(A1+A2): candidate schema v1 + mandatory PyYAML | merged | 2026-04-27 |
| [#2](https://github.com/dparilov/openclaw-agent-memory-infra/pull/2) | feat(A3+A6): dry-run for archive-batch-v2 --write and build-wiki | merged | 2026-04-27 |
| [#3](https://github.com/dparilov/openclaw-agent-memory-infra/pull/3) | feat(A4): atomic writes + file locking via io_utils.py | merged | 2026-04-27 |
| [#4](https://github.com/dparilov/openclaw-agent-memory-infra/pull/4) | feat(A5): decouple archive-batch-v2 --write from OpenClaw session files | merged | 2026-04-27 |
| [#5](https://github.com/dparilov/openclaw-agent-memory-infra/pull/5) | fix(setup): portable realpath for macOS | merged | 2026-04-28 |
| [#6](https://github.com/dparilov/openclaw-agent-memory-infra/pull/6) | fix(deploy): register sys.modules in read-topic + add deployment guide | merged | 2026-04-28 |
| [#7](https://github.com/dparilov/openclaw-agent-memory-infra/pull/7) | test: GitHub control plane visibility | closed (not merged) | 2026-04-28 |
| [#8](https://github.com/dparilov/openclaw-agent-memory-infra/pull/8) | feat(B1-B2): bootstrap structure and local script install modes | merged | 2026-04-28 |
| [#9](https://github.com/dparilov/openclaw-agent-memory-infra/pull/9) | feat(B3): portable path resolution in read-topic.py | merged | 2026-04-28 |
| [#10](https://github.com/dparilov/openclaw-agent-memory-infra/pull/10) | feat(B4): add non-live setup smoke test | merged | 2026-04-28 |
| [#11](https://github.com/dparilov/openclaw-agent-memory-infra/pull/11) | docs: add PROJECT_HISTORY.md | merged | 2026-04-28 |

| [#12](https://github.com/dparilov/openclaw-agent-memory-infra/pull/12) | feat(C): CI hardening — pytest config, GitHub Actions, e2e marker | merged | 2026-04-28 |
| [#13](https://github.com/dparilov/openclaw-agent-memory-infra/pull/13) | feat(D1): WikiFact parser + WIKI_META provenance index | merged | 2026-04-28 |
| [#14](https://github.com/dparilov/openclaw-agent-memory-infra/pull/14) | feat(D2): render provenance in wiki pages | merged | 2026-04-28 |
| [#15](https://github.com/dparilov/openclaw-agent-memory-infra/pull/15) | feat(E1-E4): sha256/mtime in source index + wiki validator + tests + checklist | merged | 2026-04-28 |
| — | `60a84a8` docs: add source_mtime_mismatch + source_mtime_invalid_format to checklist | direct commit | 2026-04-28 |

### Notes on PRs #5 and #6

The GitHub API reports both PRs as `MERGED` (mergedAt is set).  
Commits `1f4332c` (PR #5) and `a328edd` (PR #6) are present on `main`.  
PR #7 was a control-plane visibility test; it was closed without merging.


---

## Section Summaries

| Section | PRs | Description |
|---------|-----|-------------|
| A | #1–#6 | Core pipeline, atomic writes, dry-run, sys.modules fix |
| B | #8–#11 | Bootstrap `setup.sh`, script install modes, smoke test, PROJECT_HISTORY |
| C | #12 | CI hardening: pytest config, GitHub Actions, e2e marker |
| D | #13–#14 | Wiki provenance: WIKI_META source index + rendered provenance |
| E | #15 | Pre-live validation: sha256/mtime, `validate-wiki.py`, checklist |

## Test Summary

As of PR #15 + integration fixes:

```
321 passed, 4 deselected
```

Test files: `tests/test_name_resolver.py`, `tests/test_validate_wiki.py` (18 tests), plus parametrized tests across the suite.

---

## Bootstrap Phases (B1–B4)

Implemented across PRs #8–#10, all merged to `main` on 2026-04-28.

| Phase | PR | Description |
|-------|----|-------------|
| B1 | #8 | `.agent/` directory skeleton + all template files + `.agent/config.yaml` |
| B2 | #8 | `--install-scripts copy\|symlink\|none` → `.agent/tools/context_access/` only |
| B3 | #9 | `read-topic.py` portable path resolution, `load_agent_config()`, atomic checkpoint writes |
| B4 | #10 | `--test` / `--smoke-test` non-live verification flag for `setup.sh` |

---

## Smoke Test Quick Reference

Added in PR #10.  No live Telegram connection required.

```bash
# Bootstrap + verify (uses source fallback for tool --help checks)
bash setup.sh --target /path/to/project --test

# With scripts installed to .agent/tools/context_access/
bash setup.sh --target /path/to/project --install-scripts copy --test

# Require Telegram (pyrogram absence → FAIL instead of WARN)
bash setup.sh --target /path/to/project --test --require-telegram
```

**Exit codes:** `0` = all required checks PASS (WARNs allowed) · `1` = one or more FAILs

**Checks performed:**

| Check | Default result if absent |
|-------|--------------------------|
| Python ≥ 3.10 | FAIL |
| PyYAML importable | FAIL |
| `.agent/memory/` | FAIL |
| `.agent/checkpoints/` | FAIL |
| `.agent/tasks/` | FAIL |
| `.agent/reviews/` | FAIL |
| `.agent/decisions/` | FAIL |
| `.agent/runbooks/` | FAIL |
| `.agent/handoffs/` | FAIL |
| `.agent/config.yaml` | FAIL |
| `read-topic.py --help` | FAIL |
| `archive-batch-v2.py --help` | FAIL |
| `manage-candidates.py --help` | FAIL |
| `build-wiki.py --help` | FAIL |
| `validate-wiki.py --help` | FAIL |
| pyrogram importable | WARN (FAIL with `--require-telegram`) |
| Claude Code CLI | WARN |

---

## Test Suite Summary

As of PR #10 merged to `main`:

| File | Tests | Covers |
|------|-------|--------|
| `tests/test_setup_structure.py` | 154 | B1+B2: `.agent/` skeleton, install modes |
| `tests/test_read_topic_portability.py` | 54 | B3: path resolution, atomic writes, expanduser |
| `tests/test_setup_smoke.py` | 23 | B4: smoke test flags, output, config.yaml check |
| **Total** | **231** | |
