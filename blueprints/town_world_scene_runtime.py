"""Generic multi-actor scene compiler for CUSTOMS AGENT TOWN.

DeepSeek receives one high-level world_scene tool capable of expressing many
actors, scenery objects, dialogue and ordered actions in one response.  The
runtime only compiles that semantic scene into the already-existing validated
world verbs.  No story names or scenario keywords live here.
"""

from __future__ import annotations

from . import town_ai_bp as _base
from .town_ai_director_runtime import DIRECTOR_TOOLS, _fn

_ZONES = ["office", "office_door", "harbor_walkway", "pier", "sea"]


def _tool_name(tool):
    return str((tool.get("function") or {}).get("name") or "")


def _ensure_world_scene_tool():
    if any(_tool_name(tool) == "world_scene" for tool in DIRECTOR_TOOLS):
        return

    actor_step = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["move", "say", "give", "wait", "leave"]},
            "target": {"type": "string", "maxLength": 64},
            "zone": {"type": "string", "enum": _ZONES},
            "x": {"type": "number", "minimum": 12, "maximum": 628},
            "y": {"type": "number", "minimum": 60, "maximum": 390},
            "speed": {"type": "number", "minimum": 12, "maximum": 80},
            "text": {"type": "string", "maxLength": 160},
            "text_zh": {"type": "string", "maxLength": 160},
            "item": {"type": "string", "maxLength": 24},
            "seconds": {"type": "number", "minimum": 0.5, "maximum": 120},
        },
        "required": ["type"],
        "additionalProperties": False,
    }

    DIRECTOR_TOOLS.append(_fn(
        "world_scene",
        (
            "Direct one complete visible scene containing MULTIPLE new actors and/or world objects. "
            "Use this for any administrator concept that needs more than one actor or a broader event. "
            "Do not reject a concept because there is no bespoke story function: decompose it into actors, objects, "
            "movement, speech, waiting and leaving using the available pixel-world vocabulary. Represent large-scale "
            "ideas at the scale of the current town/map with several coherent visible signs rather than merely narrating them. "
            "Every requested new actor must appear as its own entry in actors with a distinct id."
        ),
        {
            "intentSummary": {"type": "string", "minLength": 1, "maxLength": 180},
            "directorNote": {"type": "string", "maxLength": 220},
            "actors": {
                "type": "array", "maxItems": 16,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "minLength": 1, "maxLength": 64},
                        "name": {"type": "string", "minLength": 1, "maxLength": 40},
                        "entityType": {"type": "string", "minLength": 1, "maxLength": 32},
                        "zone": {"type": "string", "enum": _ZONES},
                        "x": {"type": "number", "minimum": 12, "maximum": 628},
                        "y": {"type": "number", "minimum": 60, "maximum": 390},
                        "bodyColor": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
                        "accentColor": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
                        "carrying": {"type": "array", "maxItems": 8, "items": {"type": "string", "maxLength": 24}},
                        "steps": {"type": "array", "maxItems": 16, "items": actor_step},
                    },
                    "required": ["id", "name", "entityType", "zone"],
                    "additionalProperties": False,
                },
            },
            "objects": {
                "type": "array", "maxItems": 16,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "minLength": 1, "maxLength": 64},
                        "label": {"type": "string", "minLength": 1, "maxLength": 40},
                        "zone": {"type": "string", "enum": _ZONES},
                        "x": {"type": "number", "minimum": 12, "maximum": 628},
                        "y": {"type": "number", "minimum": 60, "maximum": 390},
                        "behavior": {"type": "string", "maxLength": 32},
                        "parts": {
                            "type": "array", "maxItems": 24,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "shape": {"type": "string", "enum": ["rect"]},
                                    "x": {"type": "number", "minimum": -64, "maximum": 64},
                                    "y": {"type": "number", "minimum": -64, "maximum": 64},
                                    "w": {"type": "number", "minimum": 2, "maximum": 96},
                                    "h": {"type": "number", "minimum": 2, "maximum": 96},
                                    "color": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
                                },
                                "required": ["shape", "x", "y", "w", "h", "color"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["id", "label", "zone", "parts"],
                    "additionalProperties": False,
                },
            },
        },
        ["intentSummary", "actors", "objects"],
    ))


def install_world_scene_runtime():
    _ensure_world_scene_tool()
    previous_validate = _base._validate_actions

    def validate(raw_actions):
        if not isinstance(raw_actions, list):
            return []
        expanded = []
        for raw in raw_actions[:32]:
            if not isinstance(raw, dict) or str(raw.get("type") or "") != "world_scene":
                expanded.append(raw)
                continue

            for actor in raw.get("actors") if isinstance(raw.get("actors"), list) else []:
                if not isinstance(actor, dict):
                    continue
                aid = str(actor.get("id") or "").strip()[:64]
                if not aid:
                    continue
                spawn = {
                    "type": "spawn_entity",
                    "id": aid,
                    "name": actor.get("name") or aid,
                    "entityType": actor.get("entityType") or "creature",
                    "zone": actor.get("zone") or "harbor_walkway",
                    "bodyColor": actor.get("bodyColor"),
                    "accentColor": actor.get("accentColor"),
                    "carrying": actor.get("carrying") if isinstance(actor.get("carrying"), list) else [],
                }
                if actor.get("x") is not None:
                    spawn["x"] = actor.get("x")
                if actor.get("y") is not None:
                    spawn["y"] = actor.get("y")
                expanded.append(spawn)

                for step in actor.get("steps") if isinstance(actor.get("steps"), list) else []:
                    if not isinstance(step, dict):
                        continue
                    kind = str(step.get("type") or "").strip().lower()
                    if kind == "move":
                        expanded.append({
                            "type": "move_entity", "entity": aid,
                            "target": step.get("target"), "zone": step.get("zone"),
                            "x": step.get("x"), "y": step.get("y"), "speed": step.get("speed"),
                        })
                    elif kind == "say":
                        expanded.append({
                            "type": "say", "entity": aid,
                            "text": step.get("text"), "text_zh": step.get("text_zh"),
                        })
                    elif kind == "give":
                        expanded.append({
                            "type": "give", "entity": aid,
                            "target": step.get("target"), "item": step.get("item"),
                        })
                    elif kind == "wait":
                        expanded.append({"type": "wait", "entity": aid, "seconds": step.get("seconds")})
                    elif kind == "leave":
                        expanded.append({"type": "leave", "entity": aid})
                    if len(expanded) >= 96:
                        break
                if len(expanded) >= 96:
                    break

            if len(expanded) < 96:
                for obj in raw.get("objects") if isinstance(raw.get("objects"), list) else []:
                    if not isinstance(obj, dict):
                        continue
                    expanded.append({
                        "type": "world_object_spawn",
                        "id": obj.get("id"),
                        "label": obj.get("label"),
                        "zone": obj.get("zone"),
                        "x": obj.get("x"),
                        "y": obj.get("y"),
                        "behavior": obj.get("behavior") or "static",
                        "parts": obj.get("parts") if isinstance(obj.get("parts"), list) else [],
                    })
                    if len(expanded) >= 96:
                        break
        return previous_validate(expanded[:96])

    _base._validate_actions = validate
