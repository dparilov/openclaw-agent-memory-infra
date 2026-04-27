# Runbook: Infra Agent

> Standard operating procedure for an agent responsible for maintaining
> the memory infrastructure itself.

---

## Regular Maintenance Tasks

### Check memory health across all topics
```bash
for topic_id in $(ls memory/ | grep -oP '(?<=topic-)\d+'); do
  python3 .../archive-batch-v2.py $topic_id --status
done
```

### Identify stale memory files (>7 days since last write)
```bash
python3 -c "
from pathlib import Path
from datetime import datetime, timezone
import re

for f in Path('memory').glob('topic-*.md'):
    text = f.read_text()
    m = re.search(r'last-write: ([^|]+)', text)
    if m:
        ts = datetime.fromisoformat(m.group(1).strip())
        age = (datetime.now(timezone.utc) - ts).days
        if age > 7:
            print(f'{age}d stale: {f}')
"
```

### Run archive pass on stale topics
```bash
python3 .../archive-batch-v2.py <topic-id> \
  --write \
  --session-id "infra-maintenance-$(date +%Y%m%d)" \
  --auto-mark-done
```

---

## Bootstrap a New Project

```bash
# In the target project directory:
bash /path/to/openclaw-agent-memory-infra/.agent-template/bootstrap.sh .

# Then fill in AGENT_CONTEXT.md and run initial archive:
python3 .../archive-batch-v2.py <topic-id> \
  --write \
  --session-id "infra-init-$(date +%Y%m%d)"
```

---

## Memory File Audit

Check for ⚠️ CONFLICT markers:
```bash
grep -r "CONFLICT" memory/
```

Each CONFLICT should be reviewed:
- If the conflict is resolved by the most recent entry → leave as-is (reader uses recency)
- If the conflict indicates a genuine uncertainty → add a clarifying fact in a new archive pass
- Semantic deduplication (Phase 3) will eventually compact these automatically

---

## Backup

Memory files are plain Markdown in `.agent/memory/`. They're committed to the project repo.
No special backup needed beyond regular git commits.

---

## Adding a New Topic

1. Identify the Telegram chat_id and topic_id for the new topic
2. Create an initial archive pass:
   ```bash
   python3 .../archive-batch-v2.py <new-topic-id> --status  # verify detection
   python3 .../archive-batch-v2.py <new-topic-id> --write --session-id init-<date>
   ```
3. Add the topic to `.agent/AGENT_CONTEXT.md` under "Active Topics"
4. Commit the new `memory/topic-<id>.md`
