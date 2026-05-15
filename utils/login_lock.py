# -*- coding: utf-8 -*-
"""Cross-process file locks for serialising shared resources under pytest-xdist.

Two lock kinds, both backed by the same `_file_lock` primitive:

- `login_lock(role)` — held only during `execute_login(...)` (login + wait_for_url).
  The dev backend rejects concurrent logins that share the same role credentials
  (observed: 5 simultaneous `frontdesk_user` submits all return "Login failed").
  This serialises just the login moment per role; work phases run unlocked.

- `mobile_lock(mobile)` — currently UNUSED. Was previously wired into a
  `_mobile_serialise` autouse fixture in `conftest.py` to serialise tests
  sharing a backend patient mobile, but that left workers idle for ~28 min
  while one drained the Aditya queue (autouse fixtures run before the
  browser fixture, so blocked workers had no browser open). Same-mobile
  tests now run concurrently and rely on each phase's `sample_id`-aware
  disambiguation to find the right report. Kept in this module as a ready
  primitive in case a narrowly-scoped serialisation is later needed (e.g.
  wrapping just the FD submit step).

Both locks live under `reports/locks/` and use O_CREAT|O_EXCL on a sentinel
file with an mtime-based stale guard so a crashed worker can't hold the lock
forever.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


_LOCK_DIR: Path = Path("reports") / "locks"


@contextmanager
def _file_lock(name: str, timeout: float, stale_after: float, poll: float = 0.25) -> Iterator[None]:
    """Acquire a named cross-process file lock; yield; release.

    Implementation: O_CREAT|O_EXCL on a sentinel file. If a stale lock is
    detected (older than `stale_after`), it's force-removed and retried —
    guards against worker crashes leaving the lock held forever.
    """
    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = _LOCK_DIR / f"{name}.lock"
    deadline = time.time() + timeout
    fd: int | None = None
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            break
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
                if age > stale_after:
                    lock_path.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.time() >= deadline:
                raise TimeoutError(
                    f"_file_lock({name}): could not acquire {lock_path} within {timeout}s"
                )
            time.sleep(poll)
    try:
        yield
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


@contextmanager
def login_lock(role: str, timeout: float = 300.0) -> Iterator[None]:
    """Per-role login lock. Held only during the login submit + wait_for_url."""
    with _file_lock(f"login_{role}", timeout=timeout, stale_after=180.0):
        yield


@contextmanager
def mobile_lock(mobile: str, timeout: float = 900.0) -> Iterator[None]:
    """Per-mobile test lock. Held for the entire test (including teardown).

    `stale_after=600.0` accommodates the longest single-test wall-clock
    (~5 min for 16-phase rejection tests) plus headroom; a crashed worker's
    lock is reclaimed after 10 minutes.
    """
    with _file_lock(f"mobile_{mobile}", timeout=timeout, stale_after=600.0):
        yield
