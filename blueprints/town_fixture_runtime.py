"""Validated world state for native fixtures drawn by the base town renderer."""

from __future__ import annotations

from . import town_ai_bp as _base
from .town_ai_director_runtime import DIRECTOR_TOOLS, _fn


_FIXTURE_LIMITS = {"computer": (0, 3)}


def _tool_name(tool):
    fn = tool.get("function") if isinstance(tool, dict) else None
    return str((fn or {}).get("name") or "")


def _ensure_tool():
    if any(_tool_name(tool) == "set_fixture_count" for tool in DIRECTOR_TOOLS):
        return
    DIRECTOR_TOOLS.append(_fn(
        "set_fixture_count",
        (
            "Set the exact visible count of a built-in office fixture. Use this for explicit quantity "
            "instructions such as leaving exactly one computer; dialogue about moving equipment does not "
            "change the drawing. This is persistent world configuration until another instruction changes it."
        ),
        {
            "fixture": {"type": "string", "enum": sorted(_FIXTURE_LIMITS)},
            "count": {"type": "integer", "minimum": 0, "maximum": 3},
        },
        ["fixture", "count"],
    ))


def _clean_counts(raw):
    raw = raw if isinstance(raw, dict) else {}
    cleaned = {}
    for fixture, (low, high) in _FIXTURE_LIMITS.items():
        try:
            value = int(raw.get(fixture, high))
        except Exception:
            value = high
        cleaned[fixture] = max(low, min(high, value))
    return cleaned


def install_fixture_runtime():
    _ensure_tool()
    previous_validate = _base._validate_actions
    previous_clean = _base._clean_world
    previous_apply = _base._apply_persistent_actions

    def validate(raw_actions):
        if not isinstance(raw_actions, list):
            return []
        output = []
        for item in raw_actions:
            if not isinstance(item, dict) or str(item.get("type") or "") != "set_fixture_count":
                output.extend(previous_validate([item]))
                continue
            fixture = str(item.get("fixture") or "").strip().lower()
            if fixture not in _FIXTURE_LIMITS:
                continue
            low, high = _FIXTURE_LIMITS[fixture]
            try:
                count = int(item.get("count"))
            except Exception:
                continue
            output.append({"type": "set_fixture_count", "fixture": fixture, "count": max(low, min(high, count))})
        return output[:96]

    def clean_world(world):
        cleaned = previous_clean(world)
        source = world if isinstance(world, dict) else {}
        cleaned["fixtureCounts"] = _clean_counts(source.get("fixtureCounts"))
        return cleaned

    def apply(world, actions):
        actions = actions or []
        fixture_actions = [a for a in actions if str(a.get("type") or "") == "set_fixture_count"]
        evolved = previous_apply(world, [a for a in actions if str(a.get("type") or "") != "set_fixture_count"])
        counts = _clean_counts(evolved.get("fixtureCounts"))
        for action in fixture_actions:
            fixture = str(action.get("fixture") or "")
            if fixture in _FIXTURE_LIMITS:
                low, high = _FIXTURE_LIMITS[fixture]
                counts[fixture] = max(low, min(high, int(action.get("count") or 0)))
        evolved["fixtureCounts"] = counts
        return clean_world(evolved)

    _base._validate_actions = validate
    _base._clean_world = clean_world
    _base._apply_persistent_actions = apply

