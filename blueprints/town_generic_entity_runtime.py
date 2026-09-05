"""Generic entity/action engine for CUSTOMS AGENT TOWN.

DeepSeek composes a small set of world verbs instead of needing one bespoke
function per story. The server validates and persists entity scripts in the
shared world; browsers animate the same semantic script independently.
"""

import math
import re
import time

from . import town_ai_bp as _base
from .town_ai_director_runtime import DIRECTOR_TOOLS, _fn
from .town_world_map_runtime import zone_by_id
from .town_world_object_runtime import _guess_preset

_ENTITY_TYPES = {"human", "vehicle", "animal", "item", "decoration"}
_ZONES = {"office", "office_door", "harbor_walkway", "pier", "sea"}
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_MOBILITY = {"walk", "run", "roll", "drive", "swim", "float", "static"}
_PART_SHAPES = {"rect", "ellipse"}


def inline_visual_schema(max_parts=36):
    """Schema for a safe inline pixel blueprint authored by the director."""
    return {
        "type": "object",
        "description": (
            "Original pixel silhouette for this exact actor. Distinctive creatures must use "
            "purposeful parts instead of relying only on bodyColor/accentColor. Coordinates are "
            "center offsets from the ground anchor; negative y is above the feet. Aim for a readable "
            "roughly 24–54 pixel tall silhouette with visible face/anatomy/accessory details."
        ),
        "properties": {
            "scale": {"type": "number", "minimum": 0.35, "maximum": 3.0},
            "facing": {"type": "string", "enum": ["down", "up", "left", "right"]},
            "parts": {
                "type": "array", "minItems": 6, "maxItems": max_parts,
                "items": {
                    "type": "object",
                    "properties": {
                        "shape": {"type": "string", "enum": sorted(_PART_SHAPES)},
                        "x": {"type": "number", "minimum": -64, "maximum": 64},
                        "y": {"type": "number", "minimum": -64, "maximum": 64},
                        "w": {"type": "number", "minimum": 2, "maximum": 96},
                        "h": {"type": "number", "minimum": 2, "maximum": 96},
                        "color": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
                        "layer": {"type": "integer", "minimum": -20, "maximum": 20},
                        "motion": {
                            "type": "object",
                            "properties": {
                                "on": {"type": "string", "enum": ["move", "idle", "interact", "always"]},
                                "dx": {"type": "number", "minimum": -20, "maximum": 20},
                                "dy": {"type": "number", "minimum": -20, "maximum": 20},
                                "period": {"type": "number", "minimum": 0.2, "maximum": 10},
                                "phase": {"type": "number", "minimum": -6.28, "maximum": 6.28},
                            },
                            "additionalProperties": False,
                        },
                    },
                    "required": ["shape", "x", "y", "w", "h", "color"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["parts"],
        "additionalProperties": False,
    }


def _finite_number(value, low, high, default=0.0, digits=2):
    try:
        value = float(value)
    except Exception:
        value = default
    if not math.isfinite(value):
        value = default
    return round(max(low, min(high, value)), digits)


def _clean_inline_visual(raw):
    raw = raw if isinstance(raw, dict) else {}
    parts = []
    for item in raw.get("parts") if isinstance(raw.get("parts"), list) else []:
        if not isinstance(item, dict):
            continue
        shape = _text(item.get("shape"), 16).lower()
        color = str(item.get("color") or "")
        if shape not in _PART_SHAPES or not _HEX.match(color):
            continue
        motion_raw = item.get("motion") if isinstance(item.get("motion"), dict) else {}
        on = _text(motion_raw.get("on") or "move", 16).lower()
        motion = {
            "on": on if on in {"move", "idle", "interact", "always"} else "move",
            "dx": _finite_number(motion_raw.get("dx"), -20, 20),
            "dy": _finite_number(motion_raw.get("dy"), -20, 20),
            "period": _finite_number(motion_raw.get("period"), 0.2, 10, 1),
            "phase": _finite_number(motion_raw.get("phase"), -6.28, 6.28),
        }
        parts.append({
            "shape": shape,
            "x": _finite_number(item.get("x"), -64, 64),
            "y": _finite_number(item.get("y"), -64, 64),
            "w": _finite_number(item.get("w"), 2, 96, 8),
            "h": _finite_number(item.get("h"), 2, 96, 8),
            "color": color,
            "layer": int(_finite_number(item.get("layer"), -20, 20, 0, 0)),
            "motion": motion,
        })
        if len(parts) >= 36:
            break
    if not parts:
        return None
    facing = _text(raw.get("facing") or "down", 12).lower()
    return {
        "scale": _finite_number(raw.get("scale"), 0.35, 3.0, 1),
        "facing": facing if facing in {"down", "up", "left", "right"} else "down",
        "parts": parts,
    }


def distinct_actor_visuals(raw_actions):
    """Reject same-geometry recolors for different actors in one AI response."""
    rows = []
    for action in raw_actions if isinstance(raw_actions, list) else []:
        if not isinstance(action, dict):
            continue
        kind = str(action.get("type") or "")
        candidates = action.get("actors") if kind == "world_scene" else ([action] if kind in {"spawn_entity", "entity_scene"} else [])
        for actor in candidates if isinstance(candidates, list) else []:
            if not isinstance(actor, dict):
                continue
            visual = _clean_inline_visual(actor.get("visual"))
            if not visual:
                continue
            identity = _text(actor.get("semanticType") or actor.get("entityType") or actor.get("name"), 64).lower()
            geometry = tuple(sorted(
                (
                    str(part.get("shape") or ""), float(part.get("x") or 0), float(part.get("y") or 0),
                    float(part.get("w") or 0), float(part.get("h") or 0), int(part.get("layer") or 0),
                )
                for part in visual.get("parts") or []
            ))
            if identity and geometry:
                rows.append((identity, geometry))
    for index, (identity, geometry) in enumerate(rows):
        if any(other_identity != identity and other_geometry == geometry for other_identity, other_geometry in rows[index + 1:]):
            return False
    return True


def _tool_names():
    return {(item.get("function") or {}).get("name") for item in DIRECTOR_TOOLS}


def _ensure_tools():
    names = _tool_names()
    if "spawn_entity" not in names:
        DIRECTOR_TOOLS.append(_fn(
            "spawn_entity",
            (
                "Create one visible actor such as a visitor, vehicle, creature, item or decoration. "
                "It is temporary by default; set persistent=true only when the administrator explicitly "
                "asks it to remain. For every distinctive or fictional actor, supply an original visual "
                "pixel blueprint whose silhouette and features identify the concept; changing two colors "
                "on the generic animal is not an acceptable visual."
            ),
            {
                "id": {"type": "string", "minLength": 1, "maxLength": 64},
                "name": {"type": "string", "minLength": 1, "maxLength": 28},
                "entityType": {"type": "string", "enum": sorted(_ENTITY_TYPES)},
                "semanticType": {"type": "string", "minLength": 1, "maxLength": 40},
                "zone": {"type": "string", "enum": sorted(_ZONES)},
                "x": {"type": "number", "minimum": 12, "maximum": 628},
                "y": {"type": "number", "minimum": 60, "maximum": 390},
                "bodyColor": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
                "accentColor": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
                "mobility": {"type": "string", "enum": sorted(_MOBILITY)},
                "visual": inline_visual_schema(),
                "persistent": {"type": "boolean"},
                "durationSeconds": {"type": "number", "minimum": 10, "maximum": 300},
                "carrying": {
                    "type": "array", "maxItems": 6,
                    "items": {"type": "string", "minLength": 1, "maxLength": 24},
                },
            },
            ["id", "name", "entityType", "semanticType", "zone", "visual"],
        ))
    if "move_entity" not in names:
        DIRECTOR_TOOLS.append(_fn(
            "move_entity",
            "Move a previously spawned generic entity toward another entity/officer or to a semantic zone/coordinate. The browser enforces the office door and safe movement path.",
            {
                "entity": {"type": "string", "minLength": 1, "maxLength": 64},
                "target": {"type": "string", "maxLength": 64},
                "zone": {"type": "string", "enum": sorted(_ZONES)},
                "x": {"type": "number", "minimum": 12, "maximum": 628},
                "y": {"type": "number", "minimum": 60, "maximum": 390},
                "speed": {"type": "number", "minimum": 12, "maximum": 80},
            },
            ["entity"],
        ))
    if "say" not in names:
        DIRECTOR_TOOLS.append(_fn(
            "say",
            "Make a spawned generic human/visitor say an exact sentence. Always provide BOTH text (natural Spanish) and text_zh (Simplified Chinese with the same meaning); neither field may be omitted.",
            {
                "entity": {"type": "string", "minLength": 1, "maxLength": 64},
                "text": {"type": "string", "minLength": 1, "maxLength": 160},
                "text_zh": {"type": "string", "maxLength": 160},
            },
            ["entity", "text", "text_zh"],
        ))
    if "give" not in names:
        DIRECTOR_TOOLS.append(_fn(
            "give",
            "Give an item carried by a spawned entity to another entity or an officer. Move near the recipient first when appropriate.",
            {
                "entity": {"type": "string", "minLength": 1, "maxLength": 64},
                "target": {"type": "string", "minLength": 1, "maxLength": 64},
                "item": {"type": "string", "minLength": 1, "maxLength": 24},
            },
            ["entity", "target", "item"],
        ))
    if "wait" not in names:
        DIRECTOR_TOOLS.append(_fn(
            "wait",
            "Keep a spawned entity in place for a short time before its next scripted action.",
            {
                "entity": {"type": "string", "minLength": 1, "maxLength": 64},
                "seconds": {"type": "number", "minimum": 0.5, "maximum": 120},
            },
            ["entity", "seconds"],
        ))
    if "leave" not in names:
        DIRECTOR_TOOLS.append(_fn(
            "leave",
            "Make a spawned entity leave the scene through the proper office door/walkway route. Use near the end of a visit/story.",
            {"entity": {"type": "string", "minLength": 1, "maxLength": 64}},
            ["entity"],
        ))
    if "remove_entity" not in names:
        DIRECTOR_TOOLS.append(_fn(
            "remove_entity",
            "Remove a generic entity from the persistent world immediately when it should no longer exist.",
            {"entity": {"type": "string", "minLength": 1, "maxLength": 64}},
            ["entity"],
        ))


def _text(value, limit=64):
    return str(value or "").strip()[:limit]


def _number(value, low, high, default=None):
    try:
        value = float(value)
    except Exception:
        return default
    return round(max(low, min(high, value)), 1)


def _safe_color(value, default):
    value = str(value or "")
    return value if _HEX.match(value) else default


def _zone_position(zone_id, x=None, y=None):
    if zone_id == "office_door":
        return 320.0, 278.0
    zone = zone_by_id(zone_id)
    if not zone:
        defaults = {
            "office": (320.0, 238.0), "harbor_walkway": (320.0, 292.0),
            "pier": (320.0, 306.0), "sea": (520.0, 350.0),
        }
        return defaults.get(zone_id)
    pad = 10.0
    x0 = float(zone.get("x") or 0) + pad
    y0 = float(zone.get("y") or 0) + pad
    x1 = float(zone.get("x") or 0) + max(pad, float(zone.get("w") or 0) - pad)
    y1 = float(zone.get("y") or 0) + max(pad, float(zone.get("h") or 0) - pad)
    return (
        _number(x, x0, x1, (x0 + x1) / 2),
        _number(y, y0, y1, (y0 + y1) / 2),
    )


def _clean_step(step):
    if not isinstance(step, dict):
        return None
    kind = _text(step.get("type"), 24)
    step_id = _text(step.get("stepId") or step.get("id"), 80)
    base = {"stepId": step_id, "type": kind}
    if kind == "move_entity":
        base.update({
            "target": _text(step.get("target"), 64),
            "zone": _text(step.get("zone"), 24),
            "x": _number(step.get("x"), 12, 628),
            "y": _number(step.get("y"), 60, 390),
            "speed": _number(step.get("speed"), 12, 80, 38),
        })
    elif kind == "say":
        base.update({"text": _text(step.get("text"), 160), "text_zh": _text(step.get("text_zh"), 160)})
    elif kind == "give":
        base.update({"target": _text(step.get("target"), 64), "item": _text(step.get("item"), 24)})
    elif kind == "wait":
        base["seconds"] = _number(step.get("seconds"), 0.5, 120, 1)
    elif kind == "leave":
        pass
    else:
        return None
    return base


def install_generic_entity_runtime():
    _ensure_tools()
    previous_validate = _base._validate_actions
    previous_clean = _base._clean_world
    previous_apply = _base._apply_persistent_actions

    generic_types = {"spawn_entity", "move_entity", "say", "give", "wait", "leave", "remove_entity"}

    def validate_actions(raw_actions):
        if not isinstance(raw_actions, list):
            return []
        output = []
        for index, item in enumerate(raw_actions[:18]):
            if not isinstance(item, dict):
                continue
            kind = _text(item.get("type"), 32)
            if kind not in generic_types:
                output.extend(previous_validate([item]))
                continue
            if kind == "spawn_entity":
                entity_id = _text(item.get("id"), 64)
                name = _text(item.get("name"), 28)
                entity_type = _text(item.get("entityType") or item.get("entity_type"), 24).lower()
                zone = _text(item.get("zone"), 24)
                pos = _zone_position(zone, item.get("x"), item.get("y")) if zone in _ZONES else None
                if not entity_id or not name or entity_type not in _ENTITY_TYPES or not pos:
                    continue
                carrying = []
                for value in item.get("carrying") if isinstance(item.get("carrying"), list) else []:
                    value = _text(value, 24)
                    if value and value not in carrying:
                        carrying.append(value)
                    if len(carrying) >= 6:
                        break
                semantic_type = _text(item.get("semanticType") or item.get("semantic_type") or entity_type, 40)
                mobility = _text(item.get("mobility"), 24).lower()
                if mobility not in _MOBILITY:
                    mobility = "swim" if zone == "sea" else ("drive" if entity_type == "vehicle" else "walk")
                visual = _clean_inline_visual(item.get("visual"))
                minimum_parts = 1 if item.get("templateId") else 6
                if not visual or len(visual.get("parts") or []) < minimum_parts:
                    # Accepting this would silently fall back to the same dog or
                    # person sprite—the exact failure this visual contract fixes.
                    continue
                output.append({
                    "type": kind, "id": entity_id, "name": name,
                    "entityType": entity_type, "zone": zone,
                    "x": pos[0], "y": pos[1],
                    "semanticType": semantic_type,
                    "preset": _guess_preset(f"{name} {semantic_type}"),
                    "bodyColor": _safe_color(item.get("bodyColor"), "#b7a58e"),
                    "accentColor": _safe_color(item.get("accentColor"), "#8670a0"),
                    "mobility": mobility,
                    "visual": visual,
                    "persistent": bool(item.get("persistent", False)),
                    "durationSeconds": _finite_number(item.get("durationSeconds"), 10, 300, 45, 1),
                    "carrying": carrying,
                })
            elif kind == "move_entity":
                entity = _text(item.get("entity") or item.get("id"), 64)
                if not entity:
                    continue
                zone = _text(item.get("zone"), 24)
                pos = _zone_position(zone, item.get("x"), item.get("y")) if zone in _ZONES else None
                if pos is None and item.get("x") is not None and item.get("y") is not None:
                    pos = (
                        _number(item.get("x"), 12, 628, 320),
                        _number(item.get("y"), 60, 390, 292),
                    )
                action = {"type": kind, "entity": entity, "target": _text(item.get("target"), 64), "speed": _number(item.get("speed"), 12, 80, 38)}
                if pos:
                    action.update({"zone": zone if zone in _ZONES else "", "x": pos[0], "y": pos[1]})
                output.append(action)
            elif kind == "say":
                entity = _text(item.get("entity") or item.get("id"), 64)
                text = _text(item.get("text"), 160)
                text_zh = _text(item.get("text_zh"), 160)
                if entity and text and text_zh:
                    output.append({"type": kind, "entity": entity, "text": text, "text_zh": text_zh})
            elif kind == "give":
                entity = _text(item.get("entity") or item.get("id"), 64)
                target = _text(item.get("target"), 64)
                item_name = _text(item.get("item"), 24)
                if entity and target and item_name:
                    output.append({"type": kind, "entity": entity, "target": target, "item": item_name})
            elif kind == "wait":
                entity = _text(item.get("entity") or item.get("id"), 64)
                if entity:
                    output.append({"type": kind, "entity": entity, "seconds": _number(item.get("seconds"), 0.5, 120, 1)})
            elif kind in {"leave", "remove_entity"}:
                entity = _text(item.get("entity") or item.get("id"), 64)
                if entity:
                    output.append({"type": kind, "entity": entity})
            if len(output) >= 16:
                break
        return output[:16]

    def clean_world(world):
        cleaned = previous_clean(world)
        source = world if isinstance(world, dict) else {}
        entities = []
        now_ms = int(time.time() * 1000)
        for raw in source.get("genericEntities") if isinstance(source.get("genericEntities"), list) else []:
            if not isinstance(raw, dict):
                continue
            entity_id = _text(raw.get("id"), 64)
            name = _text(raw.get("name"), 28)
            entity_type = _text(raw.get("entityType") or raw.get("entity_type"), 24).lower()
            zone = _text(raw.get("zone"), 24)
            pos = _zone_position(zone, raw.get("x"), raw.get("y")) if zone in _ZONES else None
            if not entity_id or not name or entity_type not in _ENTITY_TYPES or not pos:
                continue
            created_at = int(raw.get("createdAt") or raw.get("updatedAt") or now_ms)
            persistent = bool(raw.get("persistent", False))
            duration_seconds = _finite_number(raw.get("durationSeconds"), 10, 300, 45, 1)
            expires_at = 0 if persistent else int(raw.get("expiresAt") or (created_at + duration_seconds * 1000))
            if expires_at and expires_at <= now_ms:
                continue
            carrying = [_text(v, 24) for v in (raw.get("carrying") if isinstance(raw.get("carrying"), list) else []) if _text(v, 24)][:6]
            script = []
            for step in raw.get("script") if isinstance(raw.get("script"), list) else []:
                step = _clean_step(step)
                if step:
                    script.append(step)
                if len(script) >= 24:
                    break
            entities.append({
                "id": entity_id, "name": name, "entityType": entity_type,
                "zone": zone, "x": pos[0], "y": pos[1],
                "semanticType": _text(raw.get("semanticType") or raw.get("semantic_type") or entity_type, 40),
                "preset": _guess_preset(f"{name} {raw.get('semanticType', '')}"),
                "bodyColor": _safe_color(raw.get("bodyColor"), "#b7a58e"),
                "accentColor": _safe_color(raw.get("accentColor"), "#8670a0"),
                "mobility": _text(raw.get("mobility"), 24).lower() if _text(raw.get("mobility"), 24).lower() in _MOBILITY else ("swim" if zone == "sea" else "walk"),
                "visual": _clean_inline_visual(raw.get("visual")),
                "carrying": carrying, "script": script,
                "persistent": persistent,
                "durationSeconds": duration_seconds,
                "expiresAt": expires_at,
                "instanceVersion": int(raw.get("instanceVersion") or created_at),
                "createdAt": created_at,
                "updatedAt": int(raw.get("updatedAt") or 0),
            })
        cleaned["genericEntities"] = entities[-40:]

        # A broad world_scene response can otherwise represent the same named
        # creature twice: once as an actor and once as a world object. Keep the
        # interactive actor and discard only a recognized same-preset duplicate
        # in the same zone. This also cleans legacy octopus actor+object pairs.
        try:
            actor_presets = set()
            actor_identities = set()
            for row in entities:
                preset = _guess_preset(f"{row.get('name', '')} {row.get('semanticType', '')}")
                if preset:
                    actor_presets.add((preset, str(row.get("zone") or "")))
                identity = re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", str(row.get("name") or "").lower())[:80]
                if identity:
                    actor_identities.add((identity, str(row.get("zone") or "")))
            if (actor_presets or actor_identities) and isinstance(cleaned.get("worldObjects"), list):
                cleaned["worldObjects"] = [
                    obj for obj in cleaned["worldObjects"]
                    if not (
                        (
                            str(obj.get("preset") or _guess_preset(f"{obj.get('name', '')} {obj.get('label', '')}")),
                            str(obj.get("zone") or ""),
                        ) in actor_presets
                        or (
                            re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", str(obj.get("label") or obj.get("name") or "").lower())[:80],
                            str(obj.get("zone") or ""),
                        ) in actor_identities
                    )
                ]
        except Exception:
            pass
        return cleaned

    def apply_persistent_actions(world, actions):
        actions = actions or []
        generic_actions = [a for a in actions if str(a.get("type") or "") in generic_types]
        evolved = previous_apply(world, [a for a in actions if str(a.get("type") or "") not in generic_types])
        entities = [dict(e) for e in evolved.get("genericEntities", []) if isinstance(e, dict)]
        by_id = {str(e.get("id") or ""): e for e in entities}
        stamp = int(time.time() * 1000)
        sequence = 0
        touched = set()

        def append_step(entity, action):
            nonlocal sequence
            sequence += 1
            script = [dict(s) for s in entity.get("script", []) if isinstance(s, dict)][-20:]
            step = {"stepId": f"{stamp}-{sequence}", **action}
            script.append(step)
            entity["script"] = script[-24:]
            entity["updatedAt"] = stamp
            touched.add(str(entity.get("id") or ""))

        for action in generic_actions:
            kind = str(action.get("type") or "")
            if kind == "spawn_entity":
                entity_id = str(action.get("id") or "")[:64]
                if not entity_id:
                    continue
                entity = by_id.get(entity_id)
                if entity is None:
                    entity = {"id": entity_id}
                    entities.append(entity); by_id[entity_id] = entity
                # Reusing a semantic id in a later command means a new scene,
                # not a permanently hidden/replayed old instance.
                entity.update({
                    "name": action.get("name") or entity_id,
                    "entityType": action.get("entityType") or "human",
                    "semanticType": action.get("semanticType") or action.get("entityType") or "human",
                    "preset": action.get("preset") or _guess_preset(f"{action.get('name', '')} {action.get('semanticType', '')}"),
                    "zone": action.get("zone") or "harbor_walkway",
                    "x": action.get("x"), "y": action.get("y"),
                    "bodyColor": action.get("bodyColor") or "#b7a58e",
                    "accentColor": action.get("accentColor") or "#8670a0",
                    "mobility": action.get("mobility") or ("swim" if action.get("zone") == "sea" else "walk"),
                    "visual": action.get("visual"),
                    "carrying": list(action.get("carrying") or [])[:6],
                    "persistent": bool(action.get("persistent", False)),
                    "durationSeconds": action.get("durationSeconds") or 45,
                    "expiresAt": 0,
                    "instanceVersion": stamp,
                    "script": [], "createdAt": stamp, "updatedAt": stamp,
                })
                touched.add(entity_id)
                continue
            entity_id = str(action.get("entity") or "")[:64]
            entity = by_id.get(entity_id)
            if not entity:
                continue
            if kind == "remove_entity":
                entities = [e for e in entities if str(e.get("id")) != entity_id]
                by_id.pop(entity_id, None)
            elif kind == "move_entity":
                append_step(entity, {"type": kind, "target": action.get("target") or "", "zone": action.get("zone") or "", "x": action.get("x"), "y": action.get("y"), "speed": action.get("speed") or 38})
            elif kind == "say":
                append_step(entity, {"type": kind, "text": action.get("text") or "", "text_zh": action.get("text_zh") or ""})
            elif kind == "give":
                append_step(entity, {"type": kind, "target": action.get("target") or "", "item": action.get("item") or ""})
            elif kind == "wait":
                append_step(entity, {"type": kind, "seconds": action.get("seconds") or 1})
            elif kind == "leave":
                append_step(entity, {"type": kind})

        # Temporary is the safe story default. Give every script enough time to
        # play once, then let the authoritative world forget it. Explicitly
        # persistent actors remain until remove_entity is called.
        for entity_id in touched:
            entity = by_id.get(entity_id)
            if not entity or entity.get("persistent"):
                if entity:
                    entity["expiresAt"] = 0
                continue
            estimated = 8.0
            for step in entity.get("script") if isinstance(entity.get("script"), list) else []:
                kind = str(step.get("type") or "")
                if kind == "move_entity":
                    estimated += 8.0
                elif kind == "say":
                    length = max(len(str(step.get("text") or "")), len(str(step.get("text_zh") or "")))
                    estimated += max(4.0, min(12.0, 2.8 + length * 0.08))
                elif kind == "wait":
                    estimated += max(0.5, min(120.0, float(step.get("seconds") or 1)))
                elif kind == "give":
                    estimated += 1.5
                elif kind == "leave":
                    estimated += 9.0
            requested = _finite_number(entity.get("durationSeconds"), 10, 300, 45, 1)
            lifetime = min(300.0, max(requested, estimated))
            entity["durationSeconds"] = lifetime
            entity["expiresAt"] = stamp + int(lifetime * 1000)
        evolved["genericEntities"] = entities[-40:]
        return clean_world(evolved)

    _base._validate_actions = validate_actions
    _base._clean_world = clean_world
    _base._apply_persistent_actions = apply_persistent_actions
