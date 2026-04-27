"""
io_utils.py — Transactional file I/O for openclaw-agent-memory-infra.

Provides atomic, locked file writes to prevent data loss when multiple agents
write to the same memory / candidate / progress / wiki files concurrently.

Public API
----------
atomic_write_text(path, content, *, encoding="utf-8", lock_dir=None)
    Replace *path* atomically: temp-file → fsync → os.replace.

atomic_append_text(path, content, *, encoding="utf-8", lock_dir=None)
    Append *content* atomically: read → concat → temp-file → fsync → os.replace.

Lock file location
------------------
Default : <parent>/.locks/<filename>.lock
Override: OPENCLAW_MEMORY_LOCK_DIR env var   OR   lock_dir= kwarg.

Concurrency model
-----------------
Uses fcntl.LOCK_EX (exclusive flock). Protects concurrent processes/threads
on the same machine. Cross-machine locking is out of scope.
"""
from __future__ import annotations

import fcntl
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

_ENV_LOCK_DIR = "OPENCLAW_MEMORY_LOCK_DIR"
_LOCK_SUBDIR = ".locks"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_lock_dir(path: Path, lock_dir: Optional[Path]) -> Path:
    if lock_dir is not None:
        return Path(lock_dir)
    env = os.environ.get(_ENV_LOCK_DIR)
    if env:
        return Path(env)
    return path.parent / _LOCK_SUBDIR


def _lock_path(path: Path, lock_dir: Optional[Path]) -> Path:
    ld = _resolve_lock_dir(path, lock_dir)
    ld.mkdir(parents=True, exist_ok=True)
    safe = path.name.replace("/", "_") + ".lock"
    return ld / safe


@contextmanager
def _acquire_lock(path: Path, lock_dir: Optional[Path]):
    """Acquire an exclusive flock on the lock sentinel for *path*."""
    lp = _lock_path(path, lock_dir)
    lp.parent.mkdir(parents=True, exist_ok=True)
    with open(lp, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def atomic_write_text(
    path: "Path | str",
    content: str,
    *,
    encoding: str = "utf-8",
    lock_dir: Optional[Path] = None,
) -> None:
    """Write *content* to *path* atomically under an exclusive lock.

    Sequence:
      1. Acquire lock for *path*.
      2. Write content to a sibling temp file.
      3. fsync the temp file.
      4. os.replace(temp, path)  — atomic on POSIX.
      5. Release lock.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with _acquire_lock(path, lock_dir):
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.tmp.")
        try:
            with os.fdopen(fd, "w", encoding=encoding) as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


def atomic_append_text(
    path: "Path | str",
    content: str,
    *,
    encoding: str = "utf-8",
    lock_dir: Optional[Path] = None,
) -> None:
    """Append *content* to *path* atomically under an exclusive lock.

    Reads the current file content (if any), concatenates *content*, then
    performs an atomic write-and-replace — so partial appends are impossible.

    Sequence:
      1. Acquire lock for *path*.
      2. Read existing content.
      3. Write (existing + content) to a sibling temp file.
      4. fsync.
      5. os.replace(temp, path).
      6. Release lock.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with _acquire_lock(path, lock_dir):
        existing = path.read_text(encoding=encoding) if path.exists() else ""
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.tmp.")
        try:
            with os.fdopen(fd, "w", encoding=encoding) as fh:
                fh.write(existing + content)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
