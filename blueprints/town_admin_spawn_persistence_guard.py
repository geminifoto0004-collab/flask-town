"""Verify that successful admin spawn actions are actually present in TiDB world.

Action logs prove validation, not persistence.  After the normal admin command
finishes, read the authoritative world back through the installed TiDB runtime.
If a requested generic spawn is missing, replay only that missing entity's
creation/script actions, then return the verified world to the browser.
"""

from __future__ import annotations

import json
import time

from . import town_ai_bp as _base
from .town_world_lock_runtime import WORLD_LOCK


_GENERIC_FOLLOWUPS = {"move_entity", "say", "give", "wait", "leave", "interact_entity"}


def _spawn_ids(actions):
    removed = {
        str(a.get("entity") or a.get("id") or "")
        for a in (actions or [])
        if isinstance(a, dict) and str(a.get("type") or "") == "remove_entity"
    }
    ids = []
    for action in actions or []:
        if not isinstance(action, dict):
            continue
        if str(action.get("type") or "") not in {"spawn_entity", "spawn_from_template"}:
            continue
        entity_id = str(action.get("id") or "").strip()[:64]
        if entity_id and entity_id not in removed and entity_id not in ids:
            ids.append(entity_id)
    return ids


def _world_entity_ids(world):
    return {
        str(row.get("id") or "")
        for row in (world.get("genericEntities") if isinstance(world, dict) and isinstance(world.get("genericEntities"), list) else [])
        if isinstance(row, dict) and str(row.get("id") or "")
    }


def _repair_actions(actions, missing):
    missing = set(missing or [])
    out = []
    for action in actions or []:
        if not isinstance(action, dict):
            continue
        kind = str(action.get("type") or "")
        if kind in {"spawn_entity", "spawn_from_template"}:
            if str(action.get("id") or "") in missing:
                out.append(dict(action))
        elif kind in _GENERIC_FOLLOWUPS:
            if str(action.get("entity") or action.get("id") or "") in missing:
                out.append(dict(action))
    return out


def install_admin_spawn_persistence_guard(app):
    endpoint = "town_ai.town_admin_command"
    previous = app.view_functions.get(endpoint)
    if previous is None:
        return False
    if getattr(previous, "_town_admin_spawn_persistence_guard", False):
        return True

    def guarded_admin_command():
        response = app.make_response(previous())
        if not response.is_json or response.status_code >= 400:
            return response
        data = response.get_json(silent=True)
        if not isinstance(data, dict) or not data.get("ok"):
            return response

        actions = data.get("actions") if isinstance(data.get("actions"), list) else []
        # A duplicate command_id is a replay of an already-finished request.  Do
        # not resurrect an entity that may have legitimately left afterwards.
        expected = [] if data.get("duplicate") else _spawn_ids(actions)
        repaired = False
        missing_before = []

        try:
            with WORLD_LOCK:
                stored = _base._read_json(_base._WORLD_PATH, {})
                world = _base._clean_world(stored.get("world") if isinstance(stored, dict) else {})
                present = _world_entity_ids(world)
                missing_before = [entity_id for entity_id in expected if entity_id not in present]

                if missing_before:
                    replay = _repair_actions(actions, missing_before)
                    if replay:
                        world = _base._apply_persistent_actions(world, replay)
                        _base._write_json(
                            _base._WORLD_PATH,
                            {"saved_at": int(time.time()), "world": world},
                        )
                        repaired = True

                # Always return an authoritative readback, never only the
                # pre-write in-memory value from the admin route.
                stored = _base._read_json(_base._WORLD_PATH, {})
                world = _base._clean_world(stored.get("world") if isinstance(stored, dict) else {})
                present = _world_entity_ids(world)

            data["world"] = world
            data["generic_entity_count"] = len(present)
            data["generic_entity_ids"] = sorted(present)[-40:]
            data["expected_spawn_ids"] = expected
            data["missing_spawn_ids_before_repair"] = missing_before
            data["spawn_persistence_repaired"] = repaired
            data["missing_spawn_ids_after_repair"] = [entity_id for entity_id in expected if entity_id not in present]
            response.set_data(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
            response.content_type = "application/json; charset=utf-8"
        except Exception as exc:
            # Do not turn an already successful admin command into an HTTP error
            # merely because the verification layer itself could not inspect it.
            data["spawn_persistence_guard_error"] = str(exc)[:180]
            response.set_data(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
            response.content_type = "application/json; charset=utf-8"
        return response

    guarded_admin_command._town_admin_spawn_persistence_guard = True
    app.view_functions[endpoint] = guarded_admin_command
    return True
