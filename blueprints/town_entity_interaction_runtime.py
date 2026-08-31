"""Capability-driven interactions for generic/template entities.

The AI specifies semantic intent; the browser handles animation.  The verbs are
engine vocabulary rather than story-specific functions.
"""

from __future__ import annotations

import time

from . import town_ai_bp as _base
from .town_ai_director_runtime import DIRECTOR_TOOLS, _fn
from .town_entity_template_runtime import _CAPABILITIES, template_by_id

_VERBS = sorted(set(_CAPABILITIES) | {"inspect", "greet", "work", "rest"})


def _text(value, limit=64):
    return str(value or "").strip()[:limit]


def _ensure_tool():
    names = {(v.get("function") or {}).get("name") for v in DIRECTOR_TOOLS}
    if "interact_entity" in names:
        return
    DIRECTOR_TOOLS.append(_fn(
        "interact_entity",
        "Perform a semantic interaction between an existing entity and a target/object. The game engine owns movement/animation/state details. Use only a capability that makes sense for the actor/template; move near the target first when physical proximity is required.",
        {
            "entity": {"type": "string", "minLength": 1, "maxLength": 64},
            "verb": {"type": "string", "enum": _VERBS},
            "target": {"type": "string", "maxLength": 64},
            "item": {"type": "string", "maxLength": 32},
            "text": {"type": "string", "maxLength": 160},
            "text_zh": {"type": "string", "maxLength": 160},
            "duration": {"type": "number", "minimum": 0.2, "maximum": 30},
        },
        ["entity", "verb"],
    ))


def install_entity_interaction_runtime():
    _ensure_tool()
    previous_validate = _base._validate_actions
    previous_apply = _base._apply_persistent_actions
    previous_clean = _base._clean_world

    def validate(raw_actions):
        if not isinstance(raw_actions, list):
            return []
        out = []
        for item in raw_actions:
            if not isinstance(item, dict):
                continue
            if str(item.get("type") or "") != "interact_entity":
                out.extend(previous_validate([item]))
                continue
            entity = _text(item.get("entity") or item.get("id"), 64)
            verb = _text(item.get("verb"), 24).lower()
            if not entity or verb not in _VERBS:
                continue
            try:
                duration = max(0.2, min(30.0, float(item.get("duration") or 1.2)))
            except Exception:
                duration = 1.2
            out.append({
                "type": "interact_entity", "entity": entity, "verb": verb,
                "target": _text(item.get("target"), 64), "item": _text(item.get("item"), 32),
                "text": _text(item.get("text"), 160), "text_zh": _text(item.get("text_zh"), 160),
                "duration": round(duration, 2),
            })
            if len(out) >= 64:
                break
        return out[:64]

    def clean(world):
        cleaned = previous_clean(world)
        source = world if isinstance(world, dict) else {}
        source_entities = {
            str(e.get("id") or ""): e
            for e in (source.get("genericEntities") if isinstance(source.get("genericEntities"), list) else [])
            if isinstance(e, dict)
        }
        entities = []
        for row in cleaned.get("genericEntities", []) if isinstance(cleaned.get("genericEntities"), list) else []:
            entity = dict(row)
            source_row = source_entities.get(str(entity.get("id") or ""), {})
            existing = [dict(s) for s in entity.get("script", []) if isinstance(s, dict)]
            known = {str(s.get("stepId") or "") for s in existing}
            for step in source_row.get("script") if isinstance(source_row.get("script"), list) else []:
                if not isinstance(step, dict) or str(step.get("type") or "") != "interact_entity":
                    continue
                sid = _text(step.get("stepId"), 80)
                if sid and sid not in known:
                    existing.append({
                        "stepId": sid, "type": "interact_entity", "verb": _text(step.get("verb"), 24),
                        "target": _text(step.get("target"), 64), "item": _text(step.get("item"), 32),
                        "text": _text(step.get("text"), 160), "text_zh": _text(step.get("text_zh"), 160),
                        "duration": step.get("duration") or 1.2,
                    })
                    known.add(sid)
            entity["script"] = existing[-40:]
            entities.append(entity)
        if entities:
            cleaned["genericEntities"] = entities
        return cleaned

    def apply(world, actions):
        actions = actions or []
        interactions = [a for a in actions if a.get("type") == "interact_entity"]
        evolved = previous_apply(world, [a for a in actions if a.get("type") != "interact_entity"])
        entities = [dict(e) for e in evolved.get("genericEntities", []) if isinstance(e, dict)]
        by_id = {str(e.get("id") or ""): e for e in entities}
        stamp = int(time.time() * 1000)
        sequence = 0
        for action in interactions:
            entity = by_id.get(str(action.get("entity") or ""))
            if not entity:
                continue
            template = template_by_id(entity.get("templateId")) if entity.get("templateId") else None
            allowed = set((template or {}).get("capabilities") or [])
            verb = str(action.get("verb") or "")
            # Generic social/visual verbs are safe even without a template;
            # template capability data constrains physical verbs when present.
            if allowed and verb in _CAPABILITIES and verb not in allowed:
                continue
            sequence += 1
            script = [dict(s) for s in entity.get("script", []) if isinstance(s, dict)][-36:]
            script.append({"stepId": f"{stamp}-interaction-{sequence}", **action})
            entity["script"] = script[-40:]
            entity["updatedAt"] = stamp
        evolved["genericEntities"] = entities
        return clean(evolved)

    _base._validate_actions = validate
    _base._apply_persistent_actions = apply
    _base._clean_world = clean
