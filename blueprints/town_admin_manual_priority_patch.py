"""Manual admin colleague actions have higher priority than automatic life/shift rules.

This layer is generic and TiDB-driven. It does not inspect story keywords or
hard-code character names. If a manual admin plan physically involves a
permanent colleague, the server first summons that colleague unless the same
plan explicitly sends them off duty. For colleagues beyond the three historical
native sprite slots, the same admin plan is mirrored into generic-entity actions
so the browser has a visible actor and can render their speech/chat.
"""

from __future__ import annotations

from . import town_admin_runtime as _admin
from . import town_ai_bp as _base
from .town_character_tidb_runtime import character_context, refresh_runtime_character_bindings


def _agent(value):
    return str(value or "").strip().upper()[:64]


def _participants(actions):
    people = set()
    explicit_off = set()
    explicit_on = set()
    for action in actions or []:
        if not isinstance(action, dict):
            continue
        kind = str(action.get("type") or "")
        if kind == "agent_shift":
            person = _agent(action.get("agent"))
            mode = str(action.get("mode") or action.get("shift") or "").lower()
            if person:
                if mode == "off":
                    explicit_off.add(person)
                elif mode == "on":
                    explicit_on.add(person)
                    people.add(person)
        elif kind in {"agent_action", "agent_say"}:
            person = _agent(action.get("agent"))
            if person:
                people.add(person)
        elif kind == "agent_chat":
            a = _agent(action.get("from") or action.get("agent"))
            b = _agent(action.get("to") or action.get("target"))
            if a:
                people.add(a)
            if b:
                people.add(b)
    return people, explicit_off, explicit_on


def _extra_generic_actions(actions, rows, extra_ids):
    by_id = {str(row.get("id") or "").upper(): row for row in rows if isinstance(row, dict)}
    extras = []

    # Make every physically used dynamic colleague a visible persistent generic
    # representation. Repeated spawn_entity calls are harmless: the generic
    # persistence layer keeps the already-existing entity and applies new steps.
    used, explicit_off, _explicit_on = _participants(actions)
    for index, colleague_id in enumerate([v for v in used if v in extra_ids and v not in explicit_off]):
        row = by_id.get(colleague_id) or {}
        col = index % 4
        line = index // 4
        extras.append({
            "type": "spawn_entity",
            "id": colleague_id,
            "name": str(row.get("name") or colleague_id)[:28],
            "entityType": "human",
            "zone": "office",
            "x": 135 + col * 115,
            "y": 220 + line * 42,
            "bodyColor": "#536f86",
            "accentColor": "#d4a74a",
            "carrying": [],
        })

    for action in actions or []:
        if not isinstance(action, dict):
            continue
        kind = str(action.get("type") or "")
        if kind == "agent_shift":
            colleague_id = _agent(action.get("agent"))
            mode = str(action.get("mode") or action.get("shift") or "").lower()
            if colleague_id in extra_ids and mode == "off":
                extras.append({"type": "remove_entity", "entity": colleague_id})
        elif kind == "agent_say":
            colleague_id = _agent(action.get("agent"))
            if colleague_id in extra_ids:
                extras.append({
                    "type": "say",
                    "entity": colleague_id,
                    "text": str(action.get("text") or "")[:160],
                    "text_zh": str(action.get("text_zh") or action.get("textZh") or "")[:160],
                })
        elif kind == "agent_chat":
            a = _agent(action.get("from") or action.get("agent"))
            b = _agent(action.get("to") or action.get("target"))
            if a in extra_ids and b:
                extras.append({"type": "move_entity", "entity": a, "target": b, "speed": 38})
            if b in extra_ids and a:
                extras.append({"type": "move_entity", "entity": b, "target": a, "speed": 38})
            for turn in action.get("turns") if isinstance(action.get("turns"), list) else []:
                if not isinstance(turn, dict):
                    continue
                speaker = _agent(turn.get("speaker") or turn.get("from"))
                if speaker not in extra_ids:
                    continue
                text = str(turn.get("text") or turn.get("message") or "").strip()[:160]
                if not text:
                    continue
                extras.append({
                    "type": "say",
                    "entity": speaker,
                    "text": text,
                    "text_zh": str(turn.get("text_zh") or turn.get("textZh") or "")[:160],
                })
    return extras


def install_admin_manual_priority_patch():
    previous = _admin._admin_model_command
    if getattr(previous, "_town_admin_manual_priority", False):
        return True

    def prioritized_admin_model_command(prompt, world):
        result = previous(prompt, world)
        if not isinstance(result, dict) or not result.get("ok"):
            return result

        refresh_runtime_character_bindings(force=True)
        rows = character_context(force=True)
        ids = [str(row.get("id") or "").upper() for row in rows if isinstance(row, dict) and row.get("id")]
        id_set = set(ids)
        native_ids = set(ids[:3])
        extra_ids = id_set - native_ids

        actions = [dict(a) for a in (result.get("actions") or []) if isinstance(a, dict)]
        used, explicit_off, explicit_on = _participants(actions)
        used &= id_set

        # Any physical manual action means the administrator wants that colleague
        # present now. Automatic night/day rules cannot veto it. An explicit OFF
        # action in the same plan remains authoritative.
        summon = [person for person in ids if person in used and person not in explicit_off]
        prefix = []
        for person in summon:
            if person not in explicit_on:
                prefix.append({"type": "agent_shift", "agent": person, "mode": "on"})

        # Dynamic colleagues do not live in the three historical browser slots;
        # mirror their manual speech/chat into the generic entity engine.
        mirror = _extra_generic_actions(actions, rows, extra_ids)

        synthetic = _base._validate_actions(prefix + mirror)
        result["actions"] = synthetic[: len(prefix)] + actions + synthetic[len(prefix):]
        result["admin_manual_priority"] = True
        result["admin_summoned_colleagues"] = summon
        result["admin_dynamic_colleagues"] = [v for v in summon if v in extra_ids]
        return result

    prioritized_admin_model_command._town_admin_manual_priority = True
    _admin._admin_model_command = prioritized_admin_model_command
    return True
