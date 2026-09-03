"""Final server-side roster integrity for permanent TiDB colleagues.

Older town runtimes were composed when the browser had three officer slots. Even
when their validators are rebound to current TiDB IDs, an old apply/clean stage
can still truncate agents and the later character merger recreates the missing
colleague as a profile-only skeleton. This wrapper preserves the actual agent
state for every current TiDB colleague across those legacy stages.
"""

from __future__ import annotations

from . import town_ai_bp as _base
from .town_character_tidb_runtime import (
    _merge_world_characters,
    character_id_set,
    refresh_runtime_character_bindings,
)

_STATE_MARKERS = (
    "state", "x", "y", "task", "idle", "idleAction", "timer",
    "decisionTimer", "path", "pathTarget", "manualOffDuty", "dutyState",
    "chatText", "chatTimer", "intentLabel", "directorAction",
)


def _agent_id(agent):
    return str((agent or {}).get("name") or (agent or {}).get("slot") or "").strip().upper()[:64]


def _by_id(world, valid_ids):
    result = {}
    for agent in (world or {}).get("agents", []) if isinstance((world or {}).get("agents"), list) else []:
        if not isinstance(agent, dict):
            continue
        cid = _agent_id(agent)
        if cid in valid_ids:
            result[cid] = dict(agent)
    return result


def _has_runtime_state(agent):
    return isinstance(agent, dict) and any(key in agent for key in _STATE_MARKERS)


def _restore_dropped_agent_state(before_world, after_world):
    refresh_runtime_character_bindings()
    valid_ids = character_id_set()
    before = _by_id(before_world, valid_ids)
    after = _by_id(after_world, valid_ids)

    world = dict(after_world or {})
    agents = [dict(a) for a in world.get("agents", []) if isinstance(a, dict)]
    positions = {_agent_id(agent): index for index, agent in enumerate(agents)}

    for cid in valid_ids:
        old = before.get(cid)
        new = after.get(cid)
        if not old:
            continue
        # A character merger may recreate a truncated colleague using only
        # identity/profile fields. Restore the prior runtime state, then let the
        # new authoritative identity/profile fields win.
        if new is not None and _has_runtime_state(new):
            continue
        restored = dict(old)
        if new:
            restored.update(new)
        if cid in positions:
            agents[positions[cid]] = restored
        else:
            agents.append(restored)
            positions[cid] = len(agents) - 1

    world["agents"] = agents
    return _merge_world_characters(world)


def install_roster_integrity_runtime():
    if getattr(_base, "_town_roster_integrity_runtime", False):
        return True

    previous_clean = _base._clean_world
    previous_apply = _base._apply_persistent_actions

    def clean_world(world):
        source = _merge_world_characters(world)
        cleaned = previous_clean(source)
        return _restore_dropped_agent_state(source, cleaned)

    def apply_persistent_actions(world, actions):
        source = _merge_world_characters(world)
        evolved = previous_apply(source, actions)
        return _restore_dropped_agent_state(source, evolved)

    _base._clean_world = clean_world
    _base._apply_persistent_actions = apply_persistent_actions
    _base._town_roster_integrity_runtime = True
    return True
