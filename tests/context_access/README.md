# Context Access Tests

Dependency-free smoke tests for context access scripts.

Run:

```bash
python3 tests/context_access/test_archive_batch_v2.py
```

Current coverage:

- fixture transcript discovery by topic filename;
- duplicate Telegram message dedupe across reset files;
- empty assistant transcript records are skipped;
- total/status counts use deduped messages.
