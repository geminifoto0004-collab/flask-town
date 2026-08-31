"""Permit zero active core characters without resurrecting source-code defaults.

This adapter is intentionally data-driven: an empty active set in TiDB means the
world currently has no core officers.  Runtime bindings and world projections
are cleared instead of raising or preserving stale agents.
"""

from . import town_ai_bp as _base
from . import town_character_tidb_runtime as _characters


def _clear_bindings():
    from . import town_ai_director_runtime as director
    from . import town_ai_action_runtime as action_runtime
    from . import town_ai_visibility_runtime as visibility_runtime
    from . import town_ai_shift_runtime as shift_runtime
    from . import town_officer_scene_runtime as officer_scene_runtime

    previous_ids = {str(v).upper() for v in director._AGENT_ENUM}
    for tool in director.DIRECTOR_TOOLS:
        _characters._replace_enum(tool, previous_ids, [])
    director._AGENT_ENUM[:] = []

    if hasattr(_base, "_ALLOWED_AGENTS"):
        _base._ALLOWED_AGENTS.clear()

    for module, attr in (
        (action_runtime, "_AGENT_IDS"),
        (visibility_runtime, "_AGENT_IDS"),
        (shift_runtime, "_AGENT_IDS"),
    ):
        value = getattr(module, attr, None)
        if isinstance(value, set):
            value.clear()
        else:
            setattr(module, attr, set())

    officers = getattr(officer_scene_runtime, "_OFFICERS", None)
    if isinstance(officers, list):
        officers[:] = []
    else:
        officer_scene_runtime._OFFICERS = []


def install_empty_character_support():
    original_refresh = _characters.refresh_runtime_character_bindings
    original_merge = _characters._merge_world_characters

    def refresh(force=False):
        ids = _characters.character_ids(force=force)
        if not ids:
            _clear_bindings()
            return []
        return original_refresh(force=force)

    def merge(world):
        rows = _characters.load_core_characters()
        if rows:
            return original_merge(world)
        world = dict(world or {})
        world["agents"] = []
        world["characterProfiles"] = []
        world["onDutyAgents"] = []
        world["nightShiftAgent"] = ""
        return world

    _characters.refresh_runtime_character_bindings = refresh
    _characters._merge_world_characters = merge
