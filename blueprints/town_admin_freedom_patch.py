"""Compact universal admin tool surface for CUSTOMS AGENT TOWN.

Freedom does not require sending every legacy/specialized tool schema on every
request. DeepSeek gets one universal multi-actor compositor (`world_scene`)
plus the small set of generic verbs needed to manipulate existing world state.
Permanent personnel configuration is also available when the administrator
explicitly asks to add or edit a real colleague.
"""

from . import town_admin_runtime as _admin
from .town_ai_director_runtime import DIRECTOR_TOOLS
from .town_colleague_admin_runtime import install_colleague_admin_runtime


# Story-agnostic, reusable capabilities only. No actor/story keyword routing.
# `upsert_colleague` is configuration, not a story shortcut: its own schema tells
# the model to use it only for explicit permanent employee/personnel requests.
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
    "upsert_colleague",
)


def _tool_name(tool):
    if not isinstance(tool, dict):
        return ""
    fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
    return str(fn.get("name") or "")


def install_admin_freedom_patch():
    # Character runtime is already installed before this patch in town_app.py.
    # Register the personnel validator/persistence wrapper here so the existing
    # startup chain does not need another bespoke branch.
    install_colleague_admin_runtime()

    def select_admin_tools(_prompt):
        by_name = {_tool_name(tool): tool for tool in DIRECTOR_TOOLS}
        selected = [by_name[name] for name in _UNIVERSAL_ADMIN_TOOL_NAMES if name in by_name]
        if selected:
            return selected
        return list(DIRECTOR_TOOLS[:12])

    _admin._select_admin_tools = select_admin_tools
