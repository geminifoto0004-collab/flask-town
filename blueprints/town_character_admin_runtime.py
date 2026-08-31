"""Admin API for TiDB-backed core character configuration."""

import json

from flask import jsonify, request

from database import execute_sql, get_db_connection
from . import town_ai_bp as _base
from . import town_admin_runtime as _admin
from .town_character_tidb_runtime import character_context, refresh_runtime_character_bindings


def _text(value, limit):
    return str(value or "").strip()[:limit]


def install_character_admin_runtime():
    @_base.town_ai_bp.route("/admin/characters", methods=["GET"])
    def admin_characters_get():
        denied = _admin._require_admin()
        if denied:
            return denied
        return jsonify({"ok": True, "characters": character_context(force=True)})

    @_base.town_ai_bp.route("/admin/characters", methods=["PUT", "POST"])
    def admin_characters_save():
        denied = _admin._require_admin()
        if denied:
            return denied
        body = request.get_json(silent=True) or {}
        rows = body.get("characters") if isinstance(body.get("characters"), list) else []
        if not rows:
            return jsonify({"ok": False, "error": "characters_required"}), 400

        conn = get_db_connection()
        try:
            cur = conn.cursor()
            for index, item in enumerate(rows):
                if not isinstance(item, dict):
                    continue
                character_id = _text(item.get("id") or item.get("character_id"), 64).upper()
                if not character_id:
                    continue
                display_name = _text(item.get("name") or item.get("display_name") or character_id, 64)
                try:
                    birth_year = int(item.get("birthYear") or item.get("birth_year")) if (item.get("birthYear") or item.get("birth_year")) else None
                except Exception:
                    birth_year = None
                try:
                    children_count = max(0, int(item.get("childrenCount", item.get("children_count", 0)) or 0))
                except Exception:
                    children_count = 0
                try:
                    display_order = int(item.get("displayOrder", item.get("display_order", index * 10)) or 0)
                except Exception:
                    display_order = index * 10
                traits = item.get("traits") if isinstance(item.get("traits"), dict) else {}
                execute_sql(cur, """
                    INSERT INTO town_characters
                    (character_id, display_name, gender, birth_year, marital_status,
                     partner_label, children_count, career_state, work_style,
                     personality_notes, family_notes, traits_json, is_core, active, display_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON DUPLICATE KEY UPDATE
                      display_name=VALUES(display_name), gender=VALUES(gender), birth_year=VALUES(birth_year),
                      marital_status=VALUES(marital_status), partner_label=VALUES(partner_label),
                      children_count=VALUES(children_count), career_state=VALUES(career_state),
                      work_style=VALUES(work_style), personality_notes=VALUES(personality_notes),
                      family_notes=VALUES(family_notes), traits_json=VALUES(traits_json),
                      is_core=VALUES(is_core), active=VALUES(active), display_order=VALUES(display_order)
                """, (
                    character_id, display_name, _text(item.get("gender"), 24), birth_year,
                    _text(item.get("maritalStatus") or item.get("marital_status"), 32),
                    _text(item.get("partnerLabel") or item.get("partner_label"), 128),
                    children_count, _text(item.get("careerState") or item.get("career_state") or "active", 32),
                    _text(item.get("workStyle") or item.get("work_style"), 32),
                    _text(item.get("personalityNotes") or item.get("personality_notes"), 500),
                    _text(item.get("familyNotes") or item.get("family_notes"), 500),
                    json.dumps(traits, ensure_ascii=False),
                    1 if item.get("isCore", item.get("is_core", True)) else 0,
                    1 if item.get("active", True) else 0,
                    display_order,
                ))
            conn.commit()
        finally:
            conn.close()

        refresh_runtime_character_bindings(force=True)
        return jsonify({"ok": True, "characters": character_context(force=True)})
