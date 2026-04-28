# Pre-Live Checklist

Run this before deploying any live agent that reads the L3 Knowledge Vault.

> **Scope**: This checklist covers build, integrity, and smoke validation only.
> It does not replace live-agent tests (planned separately).

## 1. Run unit + integration tests

```bash
pytest -v --tb=short
```

Expected: all tests pass, 0 failures.

## 2. Run setup smoke test

```bash
bash setup.sh --target /tmp/ocami-prelive --install-scripts copy --test
```

Expected: all PASS, no FAIL (WARN is acceptable for optional dependencies).

## 3. Build wiki from memory files

```bash
python scripts/context_access/build-wiki.py --memory-dir .agent/memory
```

Expected:
- `memory/wiki/index.md` created
- `memory/wiki/topic-*.md` created for each topic
- `memory/wiki/by-type/` populated
- `memory/wiki/WIKI_META.json` written (schema v2)

Dry-run preview:

```bash
python scripts/context_access/build-wiki.py --memory-dir .agent/memory --dry-run
```

## 4. Validate wiki integrity

```bash
python scripts/context_access/validate-wiki.py --memory-dir .agent/memory
```

Expected: `Wiki validation passed: no errors or warnings.`

Strict mode (warnings → errors):

```bash
python scripts/context_access/validate-wiki.py --memory-dir .agent/memory --strict
```

JSON output (CI-friendly):

```bash
python scripts/context_access/validate-wiki.py --memory-dir .agent/memory --json
```

Markdown audit report:

```bash
python scripts/context_access/validate-wiki.py \
  --memory-dir .agent/memory \
  --write-report .agent/memory/reports/wiki-audit.md
```

## 5. Validator checks

| # | Check | Severity |
|---|-------|----------|
| 1 | WIKI_META.json exists and is valid JSON | error |
| 2 | wiki_schema_version >= 2 | error |
| 3 | source_files[] is list of objects with required keys | error |
| 4 | facts[] all required provenance fields | error |
| 5 | every source_file exists on disk | error |
| 6 | line_number within source file range | error |
| 7 | fact text appears near referenced line | warning |
| 8 | fact_count consistency | error |
| 9 | conflict_facts count | error |
| 10 | per_topic_last_batch consistent | error |
| 11 | topic wiki page exists per topic | error |
| 12 | by-type page exists per fact_type | error |
| 13 | sha256 unchanged since build | warning |
| 14 | mtime not newer than built_at | warning |

Warnings do not cause exit 1 unless `--strict` is passed.

## Out of scope

- Live-agent tests (planned separately)
- Migration of old session_history files
- Semantic dedup or conflict resolution
- Changes to archive-batch-v2.py or candidate promotion logic

## Quick one-liner

```bash
pytest -v --tb=short && \
  bash setup.sh --target /tmp/ocami-prelive --install-scripts copy --test && \
  python scripts/context_access/build-wiki.py --memory-dir .agent/memory && \
  python scripts/context_access/validate-wiki.py --memory-dir .agent/memory
```
