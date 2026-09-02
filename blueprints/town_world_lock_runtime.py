"""Serialize shared TOWN world reads/writes inside one Gunicorn process.

The dedicated Render service uses one gthread worker. Browser /state sync,
manual AI commands, cron ticks and background world updates can therefore touch
the same TiDB snapshot concurrently. A stale browser read followed by a later
write used to be able to erase a freshly spawned AI entity.

This lock is intentionally process-local: TOWN runs one worker process, so it is
enough to make read/merge/write sections atomic without introducing another
storage layer. TiDB remains the authoritative store.
"""

from __future__ import annotations

import threading

from . import town_ai_bp as _base


WORLD_LOCK = threading.RLock()
_INSTALLED = False


def install_world_lock_runtime():
    global _INSTALLED
    if _INSTALLED:
        return True

    previous_read = _base._read_json
    previous_write = _base._write_json

    def locked_read(path, default=None):
        if path == _base._WORLD_PATH:
            with WORLD_LOCK:
                return previous_read(path, default)
        return previous_read(path, default)

    def locked_write(path, data):
        if path == _base._WORLD_PATH:
            with WORLD_LOCK:
                return previous_write(path, data)
        return previous_write(path, data)

    _base._read_json = locked_read
    _base._write_json = locked_write
    _INSTALLED = True
    return True
