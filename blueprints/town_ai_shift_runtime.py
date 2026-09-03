"""Persistent on/off-duty and temporary visitor capabilities for CUSTOMS AGENT TOWN.

Permanent officer identity/count is TiDB-owned. The historical three browser
slots are not an authorization boundary and this runtime never truncates agents.
"""

import time

from . import town_ai_bp as _base
from .town_ai_director_runtime import DIRECTOR_TOOLS, _AGENT_ENUM, _fn

# Refreshed in-place by town_character_tidb_runtime. Source code does not own
# permanent character names.
_AGENT_IDS = set()


def _current_ids():
    try:
        from .town_character_tidb_runtime import character_id_set, refresh_runtime_character_bindings
        refresh_runtime_character_bindings()
        ids = character_id_set()
        if ids:
            return ids
    except Exception:
        pass
    return set(_AGENT_IDS)


def _ensure_tools():
    names = {(item.get("function") or {}).get("name") for item in DIRECTOR_TOOLS}
    if "agent_shift" not in names:
        DIRECTOR_TOOLS.append(_fn(
            "agent_shift",
            "Change one permanent officer's duty state. Officer IDs come from the current TiDB roster.",
            {
                "agent": {"type": "string", "enum": _AGENT_ENUM},
                "mode": {"type": "string", "enum": ["off", "on"]},
            },
            ["agent", "mode"],
        ))
    if "visitor_visit" not in names:
        DIRECTOR_TOOLS.append(_fn(
            "visitor_visit",
            "Bring a temporary human visitor into the customs office to visit any current permanent officer, optionally carrying food/coffee/flowers/a gift.",
            {
                "name": {"type": "string", "minLength": 1, "maxLength": 28},
                "target": {"type": "string", "enum": _AGENT_ENUM},
                "gift": {"type": "string", "maxLength": 40},
                "staySeconds": {"type": "integer", "minimum": 8, "maximum": 90},
            },
            ["name", "target", "staySeconds"],
        ))


def install_shift_runtime():
    _ensure_tools()
    previous_validate = _base._validate_actions
    previous_apply = _base._apply_persistent_actions
    previous_clean = _base._clean_world

    def validate_actions(raw_actions):
        if not isinstance(raw_actions, list):
            return []
        valid_ids = _current_ids()
        output = []
        for index, item in enumerate(raw_actions[:32]):
            if not isinstance(item, dict):
                continue
            kind = str(item.get("type") or "")
            if kind == "agent_shift":
                agent = str(item.get("agent") or "").upper()
                mode = str(item.get("mode") or item.get("shift") or "").lower()
                if agent in valid_ids and mode in {"off", "on"}:
                    output.append({"type": "agent_shift", "agent": agent, "mode": mode})
            elif kind == "visitor_visit":
                name = str(item.get("name") or item.get("visitor") or "").strip()[:28]
                target = str(item.get("target") or item.get("to") or "").upper()
                gift = str(item.get("gift") or item.get("bring") or "").strip()[:40]
                try:
                    stay = int(item.get("staySeconds") or item.get("stay_seconds") or 18)
                except Exception:
                    stay = 18
                stay = max(8, min(90, stay))
                if name and target in valid_ids:
                    output.append({
                        "type": "visitor_visit",
                        "id": str(item.get("id") or item.get("action_id") or f"visitor-{int(time.time()*1000)}-{index}")[:80],
                        "name": name,
                        "target": target,
                        "gift": gift,
                        "staySeconds": stay,
                    })
            else:
                output.extend(previous_validate([item]))
        return output[:32]

    def clean_world(world):
        cleaned = previous_clean(world)
        source = world if isinstance(world, dict) else {}
        valid_ids = _current_ids()
        now_ms = int(time.time() * 1000)
        visitors = []
        raw_visitors = source.get("visitors") if isinstance(source.get("visitors"), list) else []
        for item in raw_visitors[-24:]:
            if not isinstance(item, dict):
                continue
            target = str(item.get("target") or "").upper()
            name = str(item.get("name") or "").strip()[:28]
            if not name or target not in valid_ids:
                continue
            created_at = int(item.get("createdAt") or item.get("created_at") or now_ms)
            stay = max(8, min(90, int(item.get("staySeconds") or 18)))
            expires_at = int(item.get("expiresAt") or (created_at + (stay + 10) * 1000))
            if expires_at < now_ms - 5000:
                continue
            visitors.append({
                "id": str(item.get("id") or "")[:80],
                "name": name,
                "target": target,
                "gift": str(item.get("gift") or "")[:40],
                "staySeconds": stay,
                "createdAt": created_at,
                "expiresAt": expires_at,
            })
        cleaned["visitors"] = visitors[-16:]
        return cleaned

    def apply_persistent_actions(world, actions):
        actions = actions or []
        people_actions = [a for a in actions if a.get("type") in {"agent_shift", "visitor_visit"}]
        evolved = previous_apply(world, [a for a in actions if a.get("type") not in {"agent_shift", "visitor_visit"}])
        agents = [dict(a) for a in evolved.get("agents", []) if isinstance(a, dict)]
        visitors = [dict(v) for v in evolved.get("visitors", []) if isinstance(v, dict)]
        now_ms = int(time.time() * 1000)
        for action in people_actions:
            if action.get("type") == "agent_shift":
                for agent in agents:
                    if str(agent.get("name") or agent.get("slot") or "").upper() != action.get("agent"):
                        continue
                    agent["manualOffDuty"] = action.get("mode") == "off"
                    agent["dutyState"] = "off" if action.get("mode") == "off" else "on"
                    break
            elif action.get("type") == "visitor_visit":
                visitor_id = str(action.get("id") or "")[:80]
                if visitor_id and not any(str(v.get("id")) == visitor_id for v in visitors):
                    stay = max(8, min(90, int(action.get("staySeconds") or 18)))
                    visitors.append({
                        "id": visitor_id,
                        "name": str(action.get("name") or "訪客")[:28],
                        "target": str(action.get("target") or "").upper(),
                        "gift": str(action.get("gift") or "")[:40],
                        "staySeconds": stay,
                        "createdAt": now_ms,
                        "expiresAt": now_ms + (stay + 10) * 1000,
                    })
        evolved["agents"] = agents
        evolved["visitors"] = visitors[-16:]
        return clean_world(evolved)

    _base._validate_actions = validate_actions
    _base._apply_persistent_actions = apply_persistent_actions
    _base._clean_world = clean_world
