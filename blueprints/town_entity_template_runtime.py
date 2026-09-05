"""TiDB-backed generic entity template language for CUSTOMS AGENT TOWN.

DeepSeek defines reusable visual/behavior data; the game engine persists it and
spawns instances.  Templates contain no story-specific names in source code.
"""

from __future__ import annotations

import json
import math
import re
import time

from flask import jsonify

from database import execute_sql, get_db_connection
from . import town_ai_bp as _base
from .town_ai_director_runtime import DIRECTOR_TOOLS, _fn

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
_ENTITY_KINDS = ["human", "animal", "creature", "vehicle", "item", "decoration", "furniture"]
_MOBILITY = ["walk", "run", "roll", "drive", "swim", "float", "static"]
_CAPABILITIES = [
    "move", "talk", "carry", "give", "receive", "follow", "react",
    "open", "close", "sit", "use", "pick_up", "drop", "enter", "exit",
]
_PRIMITIVES = ["rect", "ellipse"]
_ZONES = ["office", "office_door", "harbor_walkway", "pier", "sea"]
_CACHE = {"at": 0.0, "rows": []}
_CACHE_SECONDS = 20.0


def _text(value, limit=64):
    return str(value or "").strip()[:limit]


def _number(value, low, high, default=0.0):
    try:
        value = float(value)
    except Exception:
        value = default
    if not math.isfinite(value):
        value = default
    return round(max(low, min(high, value)), 2)


def _color(value, default="#808080"):
    value = str(value or "")
    return value if _HEX.match(value) else default


def ensure_template_table():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        execute_sql(cur, """
            CREATE TABLE IF NOT EXISTS town_entity_templates (
                template_id VARCHAR(80) PRIMARY KEY,
                display_name VARCHAR(80) NOT NULL,
                entity_kind VARCHAR(32) NOT NULL,
                mobility VARCHAR(24) NOT NULL DEFAULT 'static',
                capabilities_json JSON NULL,
                visual_json JSON NOT NULL,
                collision_json JSON NULL,
                metadata_json JSON NULL,
                active TINYINT(1) NOT NULL DEFAULT 1,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()


def _json(value, default):
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return default
    try:
        parsed = json.loads(value)
        return parsed
    except Exception:
        return default


def _clean_parts(parts):
    out = []
    for raw in parts if isinstance(parts, list) else []:
        if not isinstance(raw, dict):
            continue
        shape = _text(raw.get("shape"), 16).lower()
        if shape not in _PRIMITIVES:
            continue
        out.append({
            "shape": shape,
            "x": _number(raw.get("x"), -64, 64),
            "y": _number(raw.get("y"), -64, 64),
            "w": _number(raw.get("w"), 2, 96, 12),
            "h": _number(raw.get("h"), 2, 96, 12),
            "color": _color(raw.get("color")),
            "layer": int(_number(raw.get("layer"), -20, 20, 0)),
            "anchor": _text(raw.get("anchor") or "body", 24),
            "motion": _clean_motion(raw.get("motion")),
        })
        if len(out) >= 48:
            break
    return out


def _clean_motion(raw):
    raw=raw if isinstance(raw,dict) else {}
    on=_text(raw.get('on') or 'move',24)
    return {
        'on':on if on in {'move','idle','interact','always'} else 'move',
        'dx':_number(raw.get('dx'),-20,20),
        'dy':_number(raw.get('dy'),-20,20),
        'period':_number(raw.get('period'),0.2,10,1),
        'phase':_number(raw.get('phase'),-6.28,6.28),
    }


def _clean_visual(raw):
    raw = raw if isinstance(raw, dict) else {}
    palette = {}
    for key, value in (raw.get("palette") if isinstance(raw.get("palette"), dict) else {}).items():
        key = _text(key, 24)
        if key:
            palette[key] = _color(value)
        if len(palette) >= 12:
            break
    return {
        "scale": _number(raw.get("scale"), 0.35, 3.0, 1.0),
        "facing": _text(raw.get("facing") or "down", 12),
        "palette": palette,
        "parts": _clean_parts(raw.get("parts")),
    }


def _clean_capabilities(values):
    out = []
    for value in values if isinstance(values, list) else []:
        value = _text(value, 24).lower()
        if value in _CAPABILITIES and value not in out:
            out.append(value)
    return out


def _clean_collision(raw):
    raw = raw if isinstance(raw, dict) else {}
    return {
        "w": _number(raw.get("w"), 4, 96, 18),
        "h": _number(raw.get("h"), 4, 96, 14),
        "solid": bool(raw.get("solid", True)),
    }


def load_templates(force=False):
    now = time.time()
    if not force and _CACHE["rows"] and now - float(_CACHE["at"] or 0) < _CACHE_SECONDS:
        return [dict(v) for v in _CACHE["rows"]]
    ensure_template_table()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        execute_sql(cur, """
            SELECT template_id, display_name, entity_kind, mobility,
                   capabilities_json, visual_json, collision_json, metadata_json
            FROM town_entity_templates WHERE active=1 ORDER BY template_id
        """)
        rows = cur.fetchall() or []
    finally:
        conn.close()
    out = []
    for row in rows:
        tid = _text(row.get("template_id"), 80)
        kind = _text(row.get("entity_kind"), 32).lower()
        if not tid or kind not in _ENTITY_KINDS:
            continue
        out.append({
            "templateId": tid,
            "name": _text(row.get("display_name") or tid, 80),
            "entityKind": kind,
            "mobility": _text(row.get("mobility") or "static", 24),
            "capabilities": _clean_capabilities(_json(row.get("capabilities_json"), [])),
            "visual": _clean_visual(_json(row.get("visual_json"), {})),
            "collision": _clean_collision(_json(row.get("collision_json"), {})),
            "metadata": _json(row.get("metadata_json"), {}),
        })
    _CACHE["at"] = now
    _CACHE["rows"] = out
    return [dict(v) for v in out]


def template_catalog():
    return load_templates()


def template_by_id(template_id):
    key = _text(template_id, 80)
    return next((v for v in load_templates() if v.get("templateId") == key), None)


def _ensure_tools():
    names = {(tool.get("function") or {}).get("name") for tool in DIRECTOR_TOOLS}
    if "define_entity_template" not in names:
        DIRECTOR_TOOLS.append(_fn(
            "define_entity_template",
            "Define or update a reusable TiDB entity template. Use this when the world needs a visual actor/object that is not already represented by an existing template. Define semantic capability and a compact original pixel composition; do not copy third-party game assets.",
            {
                "templateId": {"type": "string", "minLength": 1, "maxLength": 80},
                "name": {"type": "string", "minLength": 1, "maxLength": 80},
                "entityKind": {"type": "string", "enum": _ENTITY_KINDS},
                "mobility": {"type": "string", "enum": _MOBILITY},
                "capabilities": {"type": "array", "maxItems": 12, "items": {"type": "string", "enum": _CAPABILITIES}},
                "visual": {
                    "type": "object",
                    "properties": {
                        "scale": {"type": "number", "minimum": 0.35, "maximum": 3.0},
                        "facing": {"type": "string", "enum": ["down", "up", "left", "right"]},
                        "palette": {"type": "object", "additionalProperties": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"}},
                        "parts": {
                            "type": "array", "maxItems": 48,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "shape": {"type": "string", "enum": _PRIMITIVES},
                                    "x": {"type": "number", "minimum": -64, "maximum": 64},
                                    "y": {"type": "number", "minimum": -64, "maximum": 64},
                                    "w": {"type": "number", "minimum": 2, "maximum": 96},
                                    "h": {"type": "number", "minimum": 2, "maximum": 96},
                                    "color": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
                                    "layer": {"type": "integer", "minimum": -20, "maximum": 20},
                                    "anchor": {"type": "string", "maxLength": 24},
                                    "motion": {"type":"object", "description":"Optional local part animation, driven by actor state; phase is radians.", "properties": {
                                        "on":{"type":"string","enum":["move","idle","interact","always"]},
                                        "dx":{"type":"number","minimum":-20,"maximum":20},
                                        "dy":{"type":"number","minimum":-20,"maximum":20},
                                        "period":{"type":"number","minimum":0.2,"maximum":10},
                                        "phase":{"type":"number","minimum":-6.28,"maximum":6.28}
                                    }},
                                },
                                "required": ["shape", "x", "y", "w", "h", "color"],
                            },
                        },
                    },
                    "required": ["parts"],
                },
                "collision": {
                    "type": "object",
                    "properties": {
                        "w": {"type": "number", "minimum": 4, "maximum": 96},
                        "h": {"type": "number", "minimum": 4, "maximum": 96},
                        "solid": {"type": "boolean"},
                    },
                },
            },
            ["templateId", "name", "entityKind", "mobility", "capabilities", "visual", "collision"],
        ))
    if "spawn_from_template" not in names:
        DIRECTOR_TOOLS.append(_fn(
            "spawn_from_template",
            "Spawn one world instance from a reusable TiDB template. The instance can then use generic move/say/give/wait/leave tools according to its capabilities.",
            {
                "templateId": {"type": "string", "minLength": 1, "maxLength": 80},
                "id": {"type": "string", "minLength": 1, "maxLength": 64},
                "name": {"type": "string", "maxLength": 80},
                "zone": {"type": "string", "enum": _ZONES},
                "x": {"type": "number", "minimum": 12, "maximum": 628},
                "y": {"type": "number", "minimum": 60, "maximum": 390},
                "carrying": {"type": "array", "maxItems": 8, "items": {"type": "string", "maxLength": 24}},
            },
            ["templateId", "id", "zone"],
        ))
    if "inspect_entity_templates" not in names:
        DIRECTOR_TOOLS.append(_fn(
            "inspect_entity_templates",
            "Request no visual change; use when you need to reason about currently stored reusable entity templates before choosing whether to define a new one.",
            {}, [],
        ))


def _save_template(action):
    ensure_template_table()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        execute_sql(cur, """
            INSERT INTO town_entity_templates
            (template_id, display_name, entity_kind, mobility, capabilities_json,
             visual_json, collision_json, metadata_json, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON DUPLICATE KEY UPDATE
              display_name=VALUES(display_name), entity_kind=VALUES(entity_kind),
              mobility=VALUES(mobility), capabilities_json=VALUES(capabilities_json),
              visual_json=VALUES(visual_json), collision_json=VALUES(collision_json),
              metadata_json=VALUES(metadata_json), active=1
        """, (
            action["templateId"], action["name"], action["entityKind"], action["mobility"],
            json.dumps(action["capabilities"], ensure_ascii=False),
            json.dumps(action["visual"], ensure_ascii=False),
            json.dumps(action["collision"], ensure_ascii=False),
            json.dumps(action.get("metadata") or {}, ensure_ascii=False),
        ))
        conn.commit()
    finally:
        conn.close()
    _CACHE["at"] = 0.0
    _CACHE["rows"] = []


def install_entity_template_runtime():
    ensure_template_table()
    _ensure_tools()
    previous_validate = _base._validate_actions
    previous_apply = _base._apply_persistent_actions
    previous_clean = _base._clean_world

    def validate(raw_actions):
        if not isinstance(raw_actions, list):
            return []
        output = []
        for item in raw_actions:
            if not isinstance(item, dict):
                continue
            kind = _text(item.get("type"), 40)
            if kind == "define_entity_template":
                tid = _text(item.get("templateId") or item.get("template_id"), 80)
                name = _text(item.get("name") or tid, 80)
                entity_kind = _text(item.get("entityKind") or item.get("entity_kind"), 32).lower()
                mobility = _text(item.get("mobility") or "static", 24).lower()
                visual = _clean_visual(item.get("visual"))
                if tid and name and entity_kind in _ENTITY_KINDS and mobility in _MOBILITY and visual["parts"]:
                    output.append({
                        "type": kind, "templateId": tid, "name": name,
                        "entityKind": entity_kind, "mobility": mobility,
                        "capabilities": _clean_capabilities(item.get("capabilities")),
                        "visual": visual, "collision": _clean_collision(item.get("collision")),
                        "metadata": item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
                    })
                continue
            if kind == "spawn_from_template":
                tid = _text(item.get("templateId") or item.get("template_id"), 80)
                entity_id = _text(item.get("id"), 64)
                zone = _text(item.get("zone"), 24)
                if tid and entity_id and zone in _ZONES:
                    output.append({
                        "type": kind, "templateId": tid, "id": entity_id,
                        "name": _text(item.get("name"), 80), "zone": zone,
                        "x": item.get("x"), "y": item.get("y"),
                        "carrying": [_text(v, 24) for v in (item.get("carrying") if isinstance(item.get("carrying"), list) else []) if _text(v, 24)][:8],
                    })
                continue
            if kind == "inspect_entity_templates":
                output.append({"type": kind})
                continue
            output.extend(previous_validate([item]))
            if len(output) >= 64:
                break
        return output[:64]

    def clean_world(world):
        cleaned = previous_clean(world)
        source = world if isinstance(world, dict) else {}
        source_by_id = {
            str(e.get("id") or ""): e
            for e in (source.get("genericEntities") if isinstance(source.get("genericEntities"), list) else [])
            if isinstance(e, dict)
        }
        entities = []
        for entity in cleaned.get("genericEntities", []) if isinstance(cleaned.get("genericEntities"), list) else []:
            row = dict(entity)
            source_row = source_by_id.get(str(row.get("id") or ""), {})
            tid = _text(source_row.get("templateId") or row.get("templateId"), 80)
            template = template_by_id(tid) if tid else None
            if template:
                row["templateId"] = tid
                row["entityKind"] = template["entityKind"]
                row["mobility"] = template["mobility"]
                row["capabilities"] = template["capabilities"]
                row["visual"] = template["visual"]
                row["collision"] = template["collision"]
            entities.append(row)
        if entities:
            cleaned["genericEntities"] = entities
        cleaned["entityTemplates"] = template_catalog()[:80]
        return cleaned

    def apply(world, actions):
        actions = actions or []
        template_actions = [a for a in actions if a.get("type") in {"define_entity_template", "spawn_from_template", "inspect_entity_templates"}]
        passthrough = [a for a in actions if a.get("type") not in {"define_entity_template", "spawn_from_template", "inspect_entity_templates"}]

        # Definitions are data mutations. Once stored, subsequent calls can spawn them.
        for action in template_actions:
            if action.get("type") == "define_entity_template":
                _save_template(action)

        spawn_actions = []
        for action in template_actions:
            if action.get("type") != "spawn_from_template":
                continue
            template = template_by_id(action.get("templateId"))
            if not template:
                continue
            palette = template.get("visual", {}).get("palette") or {}
            body = palette.get("body") or palette.get("primary") or "#7d8b95"
            accent = palette.get("accent") or palette.get("secondary") or "#d2a85e"
            spawn = {
                "type": "spawn_entity", "id": action["id"],
                "name": action.get("name") or template.get("name") or action["id"],
                "entityType": "animal" if template["entityKind"] in {"animal", "creature"} else (template["entityKind"] if template["entityKind"] in {"human", "vehicle", "item", "decoration"} else "decoration"),
                "zone": action["zone"], "bodyColor": body, "accentColor": accent,
                "carrying": action.get("carrying") or [],
            }
            if action.get("x") is not None:
                spawn["x"] = action.get("x")
            if action.get("y") is not None:
                spawn["y"] = action.get("y")
            spawn_actions.extend(previous_validate([spawn]))

        # Instances must exist before move/say/give scripts target their IDs.
        evolved = previous_apply(world, spawn_actions + passthrough)
        if spawn_actions:
            entities = [dict(e) for e in evolved.get("genericEntities", []) if isinstance(e, dict)]
            action_by_id = {a["id"]: a for a in template_actions if a.get("type") == "spawn_from_template"}
            for entity in entities:
                action = action_by_id.get(str(entity.get("id") or ""))
                if action:
                    entity["templateId"] = action["templateId"]
            evolved["genericEntities"] = entities
        return clean_world(evolved)

    _base._validate_actions = validate
    _base._apply_persistent_actions = apply
    _base._clean_world = clean_world

    @_base.town_ai_bp.get("/entity-templates")
    def entity_templates_get():
        return jsonify({"ok": True, "templates": template_catalog()})
