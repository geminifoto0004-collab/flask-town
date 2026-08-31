"""Short-lived in-process cache for the authoritative TiDB town world.

The browser has several independent consumers of /api/town/world. They may ask
for the same snapshot nearly simultaneously. TiDB remains authoritative; this
layer only coalesces identical reads for a very small window and invalidates on
writes so normal world changes stay visible immediately.
"""

from __future__ import annotations

import copy
import time

from . import town_ai_bp as _base

_CACHE_SECONDS = 1.5
_CACHE = {"at": 0.0, "value": None}


def install_world_read_cache():
    previous_read = _base._read_json
    previous_write = _base._write_json

    def read_json(path, default=None):
        if path != _base._WORLD_PATH:
            return previous_read(path, default)
        now = time.monotonic()
        cached = _CACHE.get("value")
        if cached is not None and now - float(_CACHE.get("at") or 0.0) < _CACHE_SECONDS:
            return copy.deepcopy(cached)
        data = previous_read(path, default)
        if isinstance(data, dict):
            _CACHE["value"] = copy.deepcopy(data)
            _CACHE["at"] = now
        return data

    def write_json(path, data):
        result = previous_write(path, data)
        if path == _base._WORLD_PATH:
            _CACHE["value"] = copy.deepcopy(data) if isinstance(data, dict) else {}
            _CACHE["at"] = time.monotonic()
        return result

    _base._read_json = read_json
    _base._write_json = write_json
