"""Compact universal admin tool surface for CUSTOMS AGENT TOWN.

Freedom does not require sending every legacy/specialized tool schema on every
request.  DeepSeek gets one universal multi-actor compositor (`world_scene`)
plus the small set of generic verbs needed to manipulate existing world state.
This keeps arbitrary-story capability while avoiding the very large tool
payload that made manual requests slow enough to collide with Render/Gunicorn
request timeouts.
"""

from . import town_admin_runtime as _admin
from .town_ai_director_runtime import DIRECTOR_TOOLS


# Story-agnostic, reusable capabilities only.  No actor/story keyword routing.
# world_scene can create many actors and pixel objects with ordered movement,
# speech, giving, waiting and leaving in one tool call.
_UNIVERSAL_ADMIN_TOOL_NAMES = (
    "world_scene",
    "spawn_entity",
    "move_entity",
    "remove_entity",
    "interact_entity",
    "define_entity_template",
    "spawn_from_template",
    "world_object_move",
    "world_object_remove",
    "agent_action",
    "agent_say",
    "agent_chat",
    "agent_shift",
    "set_relationship",
)


def _tool_name(tool):
    if not isinstance(tool, dict):
        return ""
    fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
    return str(fn.get("name") or "")


def install_admin_freedom_patch():
    def select_admin_tools(_prompt):
        by_name = {_tool_name(tool): tool for tool in DIRECTOR_TOOLS}
        selected = [by_name[name] for name in _UNIVERSAL_ADMIN_TOOL_NAMES if name in by_name]
        # world_scene should normally make this branch unnecessary.  If a future
        # installation is missing the universal tools, retain a small generic
        # fallback instead of sending the entire registry.
        if selected:
            return selected
        return list(DIRECTOR_TOOLS[:12])

    _admin._select_admin_tools = select_admin_tools
