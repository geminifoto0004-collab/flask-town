"""Compatibility layer between AI semantic entity kinds and the legacy renderer.

The director may naturally describe actors with semantic kinds such as creature,
ghost, spirit, monster, robot, police or worker.  The renderer/runtime currently
stores a smaller set of base classes.  This patch normalizes semantic kinds at
the validator boundary so representable ideas are not silently discarded.
"""

from __future__ import annotations

from . import town_ai_bp as _base
from .town_ai_director_runtime import DIRECTOR_TOOLS


_BASE_TYPES = {"human", "vehicle", "animal", "item", "decoration"}

_HUMAN_ALIASES = {
    "person", "people", "visitor", "officer", "police", "policeman", "policewoman",
    "worker", "employee", "guard", "customs_officer", "customs-officer", "civilian",
    "wizard", "witch", "zombie", "vampire", "alien_humanoid", "humanoid", "robot_humanoid",
}
_ANIMAL_ALIASES = {
    "creature", "ghost", "spirit", "monster", "dinosaur", "dragon", "beast", "pet",
    "robot_creature", "alien_creature", "supernatural", "entity", "lifeform",
}
_VEHICLE_ALIASES = {"car", "truck", "van", "bus", "boat", "ship", "motorcycle", "bike", "forklift"}
_ITEM_ALIASES = {"object", "prop", "package", "box", "parcel", "tool"}
_DECOR_ALIASES = {"furniture", "scenery", "structure", "building", "decoration_object", "fixture"}


def _normalize_entity_type(value):
    kind = str(value or "").strip().lower().replace(" ", "_")
    if kind in _BASE_TYPES:
        return kind
    if kind in _HUMAN_ALIASES:
        return "human"
    if kind in _ANIMAL_ALIASES:
        return "animal"
    if kind in _VEHICLE_ALIASES:
        return "vehicle"
    if kind in _ITEM_ALIASES:
        return "item"
    if kind in _DECOR_ALIASES:
        return "decoration"
    # Unknown semantic actors are still visually representable as a generic
    # creature.  Do not silently delete an otherwise valid spawn just because
    # the model invented a new category label.
    return "animal" if kind else ""


def _relax_tool_schemas():
    # Tool schemas should guide the model, not reject representable concepts.
    # Keep a compact semantic vocabulary while the validator remains tolerant
    # of future labels not listed here.
    semantic_types = [
        "human", "vehicle", "animal", "item", "decoration", "creature",
        "ghost", "spirit", "monster", "dinosaur", "robot", "alien", "furniture",
    ]
    for tool in DIRECTOR_TOOLS:
        fn = tool.get("function") if isinstance(tool, dict) else None
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "")
        if name not in {"spawn_entity", "entity_scene"}:
            continue
        params = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {}
        props = params.get("properties") if isinstance(params.get("properties"), dict) else {}
        key = "entityType"
        spec = props.get(key) if isinstance(props.get(key), dict) else None
        if spec is not None:
            spec.pop("enum", None)
            spec["type"] = "string"
            spec["minLength"] = 1
            spec["maxLength"] = 32
            spec["description"] = (
                "Semantic entity kind. Common values include " + ", ".join(semantic_types) +
                ". The runtime maps representable semantic kinds to renderer base types."
            )


def install_entity_type_compat_patch():
    _relax_tool_schemas()
    previous_validate = _base._validate_actions

    def validate(raw_actions):
        if not isinstance(raw_actions, list):
            return previous_validate(raw_actions)
        normalized = []
        for raw in raw_actions:
            if not isinstance(raw, dict):
                normalized.append(raw)
                continue
            item = dict(raw)
            if str(item.get("type") or "") in {"spawn_entity", "entity_scene"}:
                original = item.get("entityType") or item.get("entity_type") or item.get("entityKind")
                mapped = _normalize_entity_type(original)
                if mapped:
                    item["entityType"] = mapped
                # Preserve semantic intent as metadata when possible; render type
                # remains compatible with the mature five-class renderer.
                if original and str(original).strip().lower() != mapped:
                    item.setdefault("semanticType", str(original).strip()[:32])
            normalized.append(item)
        return previous_validate(normalized)

    _base._validate_actions = validate
