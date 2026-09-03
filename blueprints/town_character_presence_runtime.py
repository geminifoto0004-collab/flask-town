"""Persist manual presence/duty state for every TiDB colleague.

Several historical world cleaners were written for exactly three native sprite
slots and can truncate agent state. Character identity is now unlimited and
TiDB-driven, so presence must live in a server-owned map independent of the
legacy agents array. This wrapper restores that state after every clean/apply.
"""

from __future__ import annotations

from . import town_ai_bp as _base
from .town_character_tidb_runtime import character_id_set, refresh_runtime_character_bindings


_PRESENCE_KEYS = ("manualOffDuty", "dutyState")


def _agent_id(agent):
    return str((agent or {}).get("name") or (agent or {}).get("slot") or "").strip().upper()[:64]


def _clean_presence(raw, valid_ids):
    result = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            cid = str(key or "").strip().upper()[:64]
            if cid not in valid_ids or not isinstance(value, dict):
                continue
            row = {}
            if isinstance(value.get("manualOffDuty"), bool):
                row["manualOffDuty"] = value.get("manualOffDuty")
            duty = str(value.get("dutyState") or "").lower()
            if duty in {"on", "off"}:
                row["dutyState"] = duty
            if row:
                result[cid] = row
    return result


def _presence_from_agents(agents, valid_ids):
    result = {}
    for agent in agents if isinstance(agents, list) else []:
        if not isinstance(agent, dict):
            continue
        cid = _agent_id(agent)
        if cid not in valid_ids:
            continue
        row = {}
        if isinstance(agent.get("manualOffDuty"), bool):
            row["manualOffDuty"] = agent.get("manualOffDuty")
        duty = str(agent.get("dutyState") or "").lower()
        if duty in {"on", "off"}:
            row["dutyState"] = duty
        if row:
            result[cid] = row
    return result


def _merge_presence(base, overlay):
    result = {k: dict(v) for k, v in (base or {}).items() if isinstance(v, dict)}
    for cid, values in (overlay or {}).items():
        if not isinstance(values, dict):
            continue
        current = dict(result.get(cid) or {})
        current.update(values)
        result[cid] = current
    return result


def _apply_to_agents(world, presence):
    world = dict(world or {})
    agents = [dict(a) for a in world.get("agents", []) if isinstance(a, dict)]
    for agent in agents:
        cid = _agent_id(agent)
        row = presence.get(cid) if cid else None
        if not isinstance(row, dict):
            continue
        if isinstance(row.get("manualOffDuty"), bool):
            agent["manualOffDuty"] = row["manualOffDuty"]
        if row.get("dutyState") in {"on", "off"}:
            agent["dutyState"] = row["dutyState"]
    world["agents"] = agents
    world["characterPresence"] = {k: dict(v) for k, v in presence.items()}
    return world


def install_character_presence_runtime():
    if getattr(_base, "_town_character_presence_runtime", False):
        return True

    previous_clean = _base._clean_world
    previous_apply = _base._apply_persistent_actions

    def clean_world(world):
        refresh_runtime_character_bindings()
        valid_ids = character_id_set()
        source = world if isinstance(world, dict) else {}
        presence = _clean_presence(source.get("characterPresence"), valid_ids)
        presence = _merge_presence(presence, _presence_from_agents(source.get("agents"), valid_ids))
        cleaned = previous_clean(world)
        # The character runtime outside older three-slot cleaners recreates all
        # TiDB agents; reapply server-owned presence afterwards.
        return _apply_to_agents(cleaned, presence)

    def apply_persistent_actions(world, actions):
        refresh_runtime_character_bindings()
        valid_ids = character_id_set()
        source = world if isinstance(world, dict) else {}
        presence = _clean_presence(source.get("characterPresence"), valid_ids)
        presence = _merge_presence(presence, _presence_from_agents(source.get("agents"), valid_ids))

        evolved = previous_apply(world, actions)
        presence = _merge_presence(presence, _presence_from_agents((evolved or {}).get("agents"), valid_ids))

        # Reapply every shift action after the legacy chain, because an older
        # three-slot shift runtime can otherwise discard the 4th+ colleague's
        # updated state before the character runtime recreates that agent.
        for action in actions or []:
            if not isinstance(action, dict) or str(action.get("type") or "") != "agent_shift":
                continue
            cid = str(action.get("agent") or "").strip().upper()[:64]
            mode = str(action.get("mode") or action.get("shift") or "").lower()
            if cid not in valid_ids or mode not in {"on", "off"}:
                continue
            presence[cid] = {
                "manualOffDuty": mode == "off",
                "dutyState": mode,
            }

        return _apply_to_agents(evolved, presence)

    _base._clean_world = clean_world
    _base._apply_persistent_actions = apply_persistent_actions
    _base._town_character_presence_runtime = True
    return True
