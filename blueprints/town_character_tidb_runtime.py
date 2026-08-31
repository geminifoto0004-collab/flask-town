"""TiDB-driven core character configuration for CUSTOMS AGENT TOWN.

Runtime character identity and personality come from town_characters.  No officer
name is authoritative in Python.  The module loads active core characters,
refreshes tool enums/validators, enriches world agents with TiDB profile data,
and exposes helpers used by the AI director prompts.
"""

from __future__ import annotations

import json
import os
import time

from database import execute_sql, get_db_connection
from . import town_ai_bp as _base

_CACHE = {"at": 0.0, "rows": []}
_CACHE_SECONDS = 30.0


def ensure_character_table():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        execute_sql(cur, """
            CREATE TABLE IF NOT EXISTS town_characters (
                character_id VARCHAR(64) PRIMARY KEY,
                display_name VARCHAR(64) NOT NULL,
                gender VARCHAR(24) NULL,
                birth_year INT NULL,
                marital_status VARCHAR(32) NULL,
                partner_label VARCHAR(128) NULL,
                children_count INT NOT NULL DEFAULT 0,
                career_state VARCHAR(32) NOT NULL DEFAULT 'active',
                work_style VARCHAR(32) NULL,
                personality_notes VARCHAR(500) NULL,
                family_notes VARCHAR(500) NULL,
                traits_json JSON NULL,
                is_core TINYINT(1) NOT NULL DEFAULT 1,
                active TINYINT(1) NOT NULL DEFAULT 1,
                display_order INT NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()


def _decode_json(value):
    if isinstance(value, dict):
        return dict(value)
    if value in (None, ""):
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def load_core_characters(force=False):
    now = time.time()
    if not force and _CACHE["rows"] and now - float(_CACHE["at"] or 0) < _CACHE_SECONDS:
        return [dict(row) for row in _CACHE["rows"]]

    ensure_character_table()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        execute_sql(cur, """
            SELECT character_id, display_name, gender, birth_year,
                   marital_status, partner_label, children_count, career_state,
                   work_style, personality_notes, family_notes, traits_json,
                   display_order
            FROM town_characters
            WHERE active = 1 AND is_core = 1
            ORDER BY display_order, character_id
        """)
        rows = cur.fetchall() or []
    finally:
        conn.close()

    cleaned = []
    for row in rows:
        character_id = str(row.get("character_id") or "").strip().upper()[:64]
        if not character_id:
            continue
        cleaned.append({
            "id": character_id,
            "name": str(row.get("display_name") or character_id).strip()[:64],
            "gender": str(row.get("gender") or "").strip()[:24],
            "birthYear": row.get("birth_year"),
            "maritalStatus": str(row.get("marital_status") or "").strip()[:32],
            "partnerLabel": str(row.get("partner_label") or "").strip()[:128],
            "childrenCount": int(row.get("children_count") or 0),
            "careerState": str(row.get("career_state") or "active").strip()[:32],
            "workStyle": str(row.get("work_style") or "").strip()[:32],
            "personalityNotes": str(row.get("personality_notes") or "").strip()[:500],
            "familyNotes": str(row.get("family_notes") or "").strip()[:500],
            "traits": _decode_json(row.get("traits_json")),
            "displayOrder": int(row.get("display_order") or 0),
        })

    _CACHE["at"] = now
    _CACHE["rows"] = cleaned
    return [dict(row) for row in cleaned]


def character_ids(force=False):
    return [row["id"] for row in load_core_characters(force=force)]


def character_id_set(force=False):
    return set(character_ids(force=force))


def character_context(force=False):
    return load_core_characters(force=force)


def _replace_enum(schema, ids):
    if isinstance(schema, dict):
        enum = schema.get("enum")
        if isinstance(enum, list) and enum:
            upper = {str(v).upper() for v in enum}
            # Only replace enums that are clearly officer-ID enums.  Semantic
            # enums such as action names, zones or relationship states remain.
            if any(v in upper for v in {"MIA", "ANA", "LIA"}):
                schema["enum"] = list(ids)
        for value in schema.values():
            _replace_enum(value, ids)
    elif isinstance(schema, list):
        for value in schema:
            _replace_enum(value, ids)


def refresh_runtime_character_bindings(force=False):
    ids = character_ids(force=force)
    if not ids:
        raise RuntimeError("town_characters has no active core characters")

    from . import town_ai_director_runtime as director
    from . import town_ai_action_runtime as action_runtime
    from . import town_ai_visibility_runtime as visibility_runtime
    from . import town_ai_shift_runtime as shift_runtime
    from . import town_officer_scene_runtime as officer_scene_runtime

    director._AGENT_ENUM[:] = ids
    if hasattr(_base, "_ALLOWED_AGENTS"):
        _base._ALLOWED_AGENTS.clear()
        _base._ALLOWED_AGENTS.update(ids)

    for module, attr in (
        (action_runtime, "_AGENT_IDS"),
        (visibility_runtime, "_AGENT_IDS"),
        (shift_runtime, "_AGENT_IDS"),
    ):
        value = getattr(module, attr, None)
        if isinstance(value, set):
            value.clear(); value.update(ids)
        else:
            setattr(module, attr, set(ids))

    officers = getattr(officer_scene_runtime, "_OFFICERS", None)
    if isinstance(officers, list):
        officers[:] = ids
    else:
        officer_scene_runtime._OFFICERS = list(ids)

    for tool in director.DIRECTOR_TOOLS:
        _replace_enum(tool, ids)
    return ids


def _profile_from_row(row):
    profile = {
        "gender": row.get("gender") or "",
        "birthYear": row.get("birthYear"),
        "maritalStatus": row.get("maritalStatus") or "",
        "partnerLabel": row.get("partnerLabel") or "",
        "childrenCount": row.get("childrenCount", 0),
        "careerState": row.get("careerState") or "active",
        "workStyle": row.get("workStyle") or "",
        "personalityNotes": row.get("personalityNotes") or "",
        "familyNotes": row.get("familyNotes") or "",
    }
    return {k: v for k, v in profile.items() if v not in (None, "") or k == "childrenCount"}


def _merge_world_characters(world):
    world = dict(world or {})
    rows = load_core_characters()
    if not rows:
        return world

    source_agents = [dict(a) for a in world.get("agents", []) if isinstance(a, dict)]
    by_id = {str(a.get("name") or a.get("slot") or "").upper(): a for a in source_agents}
    merged = []
    for index, row in enumerate(rows):
        agent = dict(by_id.get(row["id"]) or (source_agents[index] if index < len(source_agents) else {}))
        agent["name"] = row["id"]
        agent["slot"] = row["id"]
        agent["displayName"] = row.get("name") or row["id"]
        agent["profile"] = _profile_from_row(row)
        agent["careerState"] = row.get("careerState") or "active"
        agent["workStyle"] = row.get("workStyle") or ""
        for key, value in (row.get("traits") or {}).items():
            try:
                agent[key] = float(value)
            except Exception:
                continue
        merged.append(agent)

    world["agents"] = merged
    world["characterProfiles"] = [
        {"name": row["id"], "profile": _profile_from_row(row)} for row in rows
    ]

    valid = {row["id"] for row in rows}
    on_duty = [str(v or "").upper() for v in world.get("onDutyAgents", [])] if isinstance(world.get("onDutyAgents"), list) else []
    world["onDutyAgents"] = [v for v in on_duty if v in valid] or [row["id"] for row in rows]
    night = str(world.get("nightShiftAgent") or "").upper()
    if night not in valid:
        world["nightShiftAgent"] = rows[0]["id"]
    return world


def install_character_runtime():
    refresh_runtime_character_bindings(force=True)
    previous_clean = _base._clean_world
    previous_apply = _base._apply_persistent_actions

    def clean_world(world):
        return _merge_world_characters(previous_clean(_merge_world_characters(world)))

    def apply_persistent_actions(world, actions):
        refresh_runtime_character_bindings()
        return _merge_world_characters(previous_apply(_merge_world_characters(world), actions))

    _base._clean_world = clean_world
    _base._apply_persistent_actions = apply_persistent_actions


def run_sql_migration_file(path):
    """Execute a one-time SQL data migration, then leave runtime ownership to TiDB."""
    if not os.path.exists(path):
        return False
    text = open(path, "r", encoding="utf-8").read()
    statements = [part.strip() for part in text.split(";") if part.strip()]
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        for statement in statements:
            execute_sql(cur, statement)
        conn.commit()
        _CACHE["at"] = 0.0
        _CACHE["rows"] = []
        return True
    finally:
        conn.close()
