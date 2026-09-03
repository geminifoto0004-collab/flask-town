"""Protect server/TiDB-owned world fields from stale browser state snapshots.

The native browser periodically POSTs /api/town/state. That snapshot predates
several newer AI-world fields, so replacing the whole world with it can erase
fresh server state. Browser-owned native state remains writable while newer
server/TiDB fields are preserved atomically.
"""

from __future__ import annotations

import copy
import json
import time

from flask import jsonify, request

from . import town_ai_bp as _base
from .town_admin_manual_priority_patch import install_admin_manual_priority_patch
from .town_admin_spawn_persistence_guard import install_admin_spawn_persistence_guard
from .town_character_presence_runtime import install_character_presence_runtime
from .town_world_lock_runtime import WORLD_LOCK, install_world_lock_runtime


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
    "characterPresence",
)


def install_state_merge_guard(app):
    # Install only after TiDB runtime and all world wrappers are bound, so the
    # lock wraps authoritative storage rather than startup-local JSON helpers.
    install_world_lock_runtime()

    # Presence is stored independently from the historical three native sprite
    # slots. A 4th/5th/etc TiDB colleague therefore keeps manual on/off state
    # even if an older cleaner truncates world.agents internally.
    install_character_presence_runtime()

    # This is installed after the admin fast/reliability director stack. Manual
    # admin actions involving permanent colleagues override automatic night/day
    # presence rules and dynamic colleagues get visible generic scene actions.
    install_admin_manual_priority_patch()

    endpoint = "town_ai.save_state"
    previous = app.view_functions.get(endpoint)
    if previous is None:
        return False
    if getattr(previous, "_town_state_merge_guard", False):
        install_admin_spawn_persistence_guard(app)
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
            "character_presence_count": len(world.get("characterPresence") or {}) if isinstance(world, dict) else 0,
        })

    guarded_save_state._town_state_merge_guard = True
    app.view_functions[endpoint] = guarded_save_state

    # Verify successful generic spawns against an authoritative TiDB readback
    # before returning the admin response to the browser.
    install_admin_spawn_persistence_guard(app)
    return True
