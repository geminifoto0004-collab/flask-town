"""Protect server/TiDB-owned world fields from stale browser state snapshots.

The native browser periodically POSTs /api/town/state. That snapshot predates
several newer AI-world fields, so replacing the whole world with it can erase a
freshly spawned generic entity before the overlay's next /world poll.

This guard keeps browser-owned native state writable while preserving fields
whose source of truth is the server/TiDB AI runtime. The whole read/merge/write
section is serialized with the same process lock used by all TOWN world IO so a
concurrent browser save cannot race a fresh AI spawn.
"""

from __future__ import annotations

import copy
import json
import time

from flask import jsonify, request

from . import town_ai_bp as _base
from .town_world_lock_runtime import WORLD_LOCK


_SERVER_OWNED_FIELDS = (
    "genericEntities",
    "worldObjects",
    "seaCreatures",
    "visitors",
    "relationships",
    "entityTemplates",
    "recentDialogue",
    "recentDirectorActions",
    "characterProfiles",
)


def install_state_merge_guard(app):
    endpoint = "town_ai.save_state"
    previous = app.view_functions.get(endpoint)
    if previous is None:
        return False
    if getattr(previous, "_town_state_merge_guard", False):
        return True

    def guarded_save_state():
        if request.method == "OPTIONS":
            return _base._cors(jsonify({"ok": True}))

        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            try:
                body = json.loads(request.get_data(as_text=True) or "{}")
            except Exception:
                body = {}

        browser_world = body.get("world") if isinstance(body.get("world"), dict) else {}

        # Atomic read -> preserve server-owned fields -> write. WORLD_LOCK is an
        # RLock because _base._read_json/_write_json are also protected by it.
        with WORLD_LOCK:
            stored = _base._read_json(_base._WORLD_PATH, {})
            server_world = stored.get("world") if isinstance(stored, dict) and isinstance(stored.get("world"), dict) else {}

            merged = dict(browser_world)
            preserved = []
            for key in _SERVER_OWNED_FIELDS:
                if key in server_world:
                    merged[key] = copy.deepcopy(server_world.get(key))
                    preserved.append(key)

            world = _base._clean_world(merged)
            _base._write_json(_base._WORLD_PATH, {"saved_at": int(time.time()), "world": world})

        return jsonify({
            "ok": True,
            "merge_guard": True,
            "atomic": True,
            "preserved": preserved,
            "generic_entity_count": len(world.get("genericEntities") or []) if isinstance(world, dict) else 0,
        })

    guarded_save_state._town_state_merge_guard = True
    app.view_functions[endpoint] = guarded_save_state
    return True
