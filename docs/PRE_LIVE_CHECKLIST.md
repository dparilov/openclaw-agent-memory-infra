# Pre-Live Checklist

Run before deploying any live agent that reads the L3 Knowledge Vault.

> **Scope**: build, integrity, and smoke validation only. Live-agent tests are separate.

## 1. Unit + integration tests

```bash
pytest -v --tb=short
```

## 2. Setup smoke test

```bash
bash setup.sh --target /tmp/ocami-prelive --install-scripts copy --test
```

## 3. Build wiki

```bash
python scripts/context_access/build-wiki.py --memory-dir .agent/memory
```

Dry-run: `python scripts/context_access/build-wiki.py --memory-dir .agent/memory --dry-run`

## 4. Validate wiki integrity

```bash
python scripts/context_access/validate-wiki.py --memory-dir .agent/memory
python scripts/context_access/validate-wiki.py --memory-dir .agent/memory --strict
python scripts/context_access/validate-wiki.py --memory-dir .agent/memory --json
python scripts/context_access/validate-wiki.py --memory-dir .agent/memory --write-report .agent/memory/reports/wiki-audit.md
```

## Validator checks

| Check | Severity |
|-------|----------|
| WIKI_META.json exists | error |
| wiki_schema_version >= 2 | error |
| source_files[] structure | error |
| facts[] all 10 required fields | error |
| source files exist on disk | error |
| line_number in range | error |
| fact text near referenced line | warning |
| fact_count consistency | error |
| conflict_facts count | error |
| per_topic_last_batch consistent | error |
| topic wiki page per topic | error |
| by-type page per fact_type | error |
| sha256 unchanged since build | warning |
| mtime not newer than built_at | warning |
| stored mtime parseable (source_mtime_invalid_format) | warning |
| stored mtime matches actual file mtime (source_mtime_mismatch) | warning |

## Out of scope

- Live-agent tests, session_history migration, semantic dedup, conflict resolution

## Quick one-liner

```bash
pytest -v --tb=short && \
  bash setup.sh --target /tmp/ocami-prelive --install-scripts copy --test && \
  python scripts/context_access/build-wiki.py --memory-dir .agent/memory && \
  python scripts/context_access/validate-wiki.py --memory-dir .agent/memory
```
