"""Manual admin colleague actions have higher priority than automatic life/shift rules.

All permanent colleagues now live in the SAME native browser `agents` engine.
This server layer therefore only guarantees TiDB-driven recall/presence. It does
not mirror employees into genericEntities; generic entities are reserved for
visitors, celebrities, creatures, vehicles and other story actors.
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


def _requests_all_colleagues_back(prompt):
    """Expand only a generic whole-personnel recall/chat request against TiDB."""
    text = str(prompt or "").strip().lower()
    if not text:
        return False
    groups = (
        "所有同事", "全部同事", "同事都", "全體同事", "全体同事",
        "all colleagues", "all coworkers", "everyone at work",
        "todos los colegas", "todos los compañeros", "todo el personal",
    )
    recall = (
        "叫回來", "叫回来", "回來", "回来", "召回", "回辦公室", "回办公室", "聊天", "對話", "对话",
        "come back", "return", "recall", "chat", "talk",
        "volver", "vuelvan", "regresar", "regresen", "conversar", "charlar",
    )
    return any(group in text for group in groups) and any(action in text for action in recall)


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

        actions = [dict(a) for a in (result.get("actions") or []) if isinstance(a, dict)]
        used, explicit_off, explicit_on = _participants(actions)
        used &= id_set

        force_all = _requests_all_colleagues_back(prompt)
        if force_all:
            used.update(id_set)

        # A manual physical action means that employee must be present now.
        # Night/day automation cannot veto it. Explicit OFF in the same plan wins.
        summon = [person for person in ids if person in used and person not in explicit_off]
        prefix = []
        for person in summon:
            if person not in explicit_on:
                prefix.append({"type": "agent_shift", "agent": person, "mode": "on"})

        # Only validate presence actions here. Employee movement/speech/chat stays
        # as agent_* actions and is executed by the shared native browser engine.
        presence_actions = _base._validate_actions(prefix)
        result["actions"] = presence_actions + actions
        result["admin_manual_priority"] = True
        result["admin_force_all_colleagues"] = force_all
        result["admin_summoned_colleagues"] = summon
        result["admin_dynamic_colleagues"] = [v for v in summon if v not in set(ids[:3])]
        return result

    prioritized_admin_model_command._town_admin_manual_priority = True
    _admin._admin_model_command = prioritized_admin_model_command
    return True
