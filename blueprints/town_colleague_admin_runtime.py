"""Admin-only permanent colleague configuration for CUSTOMS AGENT TOWN.

The administrator may describe a new or updated permanent colleague in natural
language. DeepSeek converts that request into this structured tool; the server
owns validation and the TiDB write. Story visitors must continue to use generic
entity tools and are never silently promoted to employees.
"""

from __future__ import annotations

import json

from database import execute_sql, get_db_connection
from . import town_ai_bp as _base
from .town_ai_director_runtime import DIRECTOR_TOOLS, _fn
from .town_character_tidb_runtime import (
    _merge_world_characters,
    character_context,
    refresh_runtime_character_bindings,
)


def _text(value, limit):
    return str(value or "").strip()[:limit]


def _ensure_tool():
    names = {
        str((tool.get("function") or {}).get("name") or "")
        for tool in DIRECTOR_TOOLS if isinstance(tool, dict)
    }
    if "upsert_colleague" in names:
        return
    DIRECTOR_TOOLS.append(_fn(
        "upsert_colleague",
        (
            "Create or update one PERMANENT customs-office colleague in TiDB. "
            "Use ONLY when the administrator explicitly asks to add, hire, create, or edit a permanent colleague/employee. "
            "Never use this for a visitor, celebrity, police visit, creature, customer, temporary actor, or ordinary story event."
        ),
        {
            "id": {"type": "string", "minLength": 1, "maxLength": 64},
            "displayName": {"type": "string", "minLength": 1, "maxLength": 64},
            "gender": {"type": "string", "maxLength": 24},
            "birthYear": {"type": "integer", "minimum": 1940, "maximum": 2010},
            "maritalStatus": {"type": "string", "maxLength": 32},
            "partnerLabel": {"type": "string", "maxLength": 128},
            "childrenCount": {"type": "integer", "minimum": 0, "maximum": 20},
            "careerState": {"type": "string", "maxLength": 32},
            "workStyle": {"type": "string", "maxLength": 32},
            "personalityNotes": {"type": "string", "maxLength": 500},
            "familyNotes": {"type": "string", "maxLength": 500},
            "traits": {"type": "object", "additionalProperties": {"type": "number"}},
            "displayOrder": {"type": "integer", "minimum": 0, "maximum": 9999},
        },
        ["id", "displayName"],
    ))


def _clean_action(item):
    colleague_id = _text(item.get("id") or item.get("character_id"), 64).upper()
    display_name = _text(item.get("displayName") or item.get("display_name") or colleague_id, 64)
    if not colleague_id or not display_name:
        return None
    try:
        birth_year = int(item.get("birthYear")) if item.get("birthYear") not in (None, "") else None
    except Exception:
        birth_year = None
    if birth_year is not None:
        birth_year = max(1940, min(2010, birth_year))
    try:
        children = max(0, min(20, int(item.get("childrenCount") or 0)))
    except Exception:
        children = 0
    try:
        order = max(0, min(9999, int(item.get("displayOrder") or 999)))
    except Exception:
        order = 999
    traits = {}
    for key, value in (item.get("traits") if isinstance(item.get("traits"), dict) else {}).items():
        key = _text(key, 40)
        if not key:
            continue
        try:
            traits[key] = round(max(0.0, min(1.0, float(value))), 3)
        except Exception:
            continue
        if len(traits) >= 24:
            break
    return {
        "type": "upsert_colleague",
        "id": colleague_id,
        "displayName": display_name,
        "gender": _text(item.get("gender"), 24),
        "birthYear": birth_year,
        "maritalStatus": _text(item.get("maritalStatus"), 32),
        "partnerLabel": _text(item.get("partnerLabel"), 128),
        "childrenCount": children,
        "careerState": _text(item.get("careerState") or "active", 32),
        "workStyle": _text(item.get("workStyle"), 32),
        "personalityNotes": _text(item.get("personalityNotes"), 500),
        "familyNotes": _text(item.get("familyNotes"), 500),
        "traits": traits,
        "displayOrder": order,
    }


def _save_colleague(action):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        execute_sql(cur, """
            INSERT INTO town_characters
            (character_id, display_name, gender, birth_year, marital_status,
             partner_label, children_count, career_state, work_style,
             personality_notes, family_notes, traits_json, is_core, active, display_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?)
            ON DUPLICATE KEY UPDATE
              display_name=VALUES(display_name), gender=VALUES(gender), birth_year=VALUES(birth_year),
              marital_status=VALUES(marital_status), partner_label=VALUES(partner_label),
              children_count=VALUES(children_count), career_state=VALUES(career_state),
              work_style=VALUES(work_style), personality_notes=VALUES(personality_notes),
              family_notes=VALUES(family_notes), traits_json=VALUES(traits_json),
              is_core=1, active=1, display_order=VALUES(display_order)
        """, (
            action["id"], action["displayName"], action["gender"], action["birthYear"],
            action["maritalStatus"], action["partnerLabel"], action["childrenCount"],
            action["careerState"], action["workStyle"], action["personalityNotes"],
            action["familyNotes"], json.dumps(action["traits"], ensure_ascii=False),
            action["displayOrder"],
        ))
        conn.commit()
    finally:
        conn.close()


def install_colleague_admin_runtime():
    _ensure_tool()
    previous_validate = _base._validate_actions
    previous_apply = _base._apply_persistent_actions

    def validate(raw_actions):
        if not isinstance(raw_actions, list):
            return []
        out = []
        for item in raw_actions:
            if not isinstance(item, dict) or str(item.get("type") or "") != "upsert_colleague":
                out.extend(previous_validate([item]))
                continue
            cleaned = _clean_action(item)
            if cleaned:
                out.append(cleaned)
            if len(out) >= 96:
                break
        return out[:96]

    def apply(world, actions):
        actions = actions or []
        personnel = [a for a in actions if isinstance(a, dict) and a.get("type") == "upsert_colleague"]
        evolved = previous_apply(world, [a for a in actions if not (isinstance(a, dict) and a.get("type") == "upsert_colleague")])
        if not personnel:
            return evolved

        for action in personnel:
            _save_colleague(action)
        refresh_runtime_character_bindings(force=True)
        evolved = _merge_world_characters(evolved)
        evolved["characterProfiles"] = [
            {"name": row.get("id"), "profile": {
                "gender": row.get("gender") or "",
                "birthYear": row.get("birthYear"),
                "maritalStatus": row.get("maritalStatus") or "",
                "partnerLabel": row.get("partnerLabel") or "",
                "childrenCount": row.get("childrenCount", 0),
                "careerState": row.get("careerState") or "active",
                "workStyle": row.get("workStyle") or "",
                "personalityNotes": row.get("personalityNotes") or "",
                "familyNotes": row.get("familyNotes") or "",
            }} for row in character_context(force=True)
        ]
        return evolved

    _base._validate_actions = validate
    _base._apply_persistent_actions = apply
