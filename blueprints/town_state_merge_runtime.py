"""Protect server/TiDB-owned world fields from stale browser state snapshots.

The native browser periodically POSTs /api/town/state. That snapshot predates
several newer AI-world fields, so replacing the whole world with it can erase a
freshly spawned generic entity before the overlay's next /world poll.

This guard keeps browser-owned native state writable while preserving fields
whose source of truth is the server/TiDB AI runtime.
"""

from __future__ import annotations

import copy
import json
import time

from flask import jsonify, request

from . import town_ai_bp as _base


# These fields are created/updated by server-side AI runtimes and must not be
# deleted merely because an older browser build does not know about them.
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
        stored = _base._read_json(_base._WORLD_PATH, {})
        server_world = stored.get("world") if isinstance(stored, dict) and isinstance(stored.get("world"), dict) else {}

        # Merge BEFORE cleaning so every installed world cleaner/validator sees
        # one complete world instead of an old browser subset.
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
            "preserved": preserved,
            "generic_entity_count": len(world.get("genericEntities") or []) if isinstance(world, dict) else 0,
        })

    guarded_save_state._town_state_merge_guard = True
    app.view_functions[endpoint] = guarded_save_state
    return True
