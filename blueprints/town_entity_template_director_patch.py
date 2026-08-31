"""Expose the TiDB entity-template vocabulary to automatic/admin directing."""

from __future__ import annotations

import json

from . import town_character_director_patch as _director
from .town_entity_template_runtime import template_catalog


def install_entity_template_director_patch():
    previous_system_prompt = _director._system_prompt

    def system_prompt(mode):
        templates = template_catalog()
        appendix = f"""

GENERIC ENTITY TEMPLATE SYSTEM:
- Reusable visual/behavior templates currently stored in TiDB are: {json.dumps(templates, ensure_ascii=False)}.
- Reuse an existing template when it represents the needed actor/object.
- If no existing template can express a requested visible thing, call define_entity_template first with an ORIGINAL compact pixel composition, then spawn_from_template.
- Template visual parts are generic rect/ellipse primitives with offsets, size, color and layer. Keep compositions compact and readable rather than producing excessive parts.
- Templates describe appearance, mobility, collision and capabilities. Instances describe where a thing currently exists and what it is doing.
- After spawning, use generic movement/social/interaction tools. The browser handles pathfinding-like routing, facing, walk motion and interaction animation; do not emit per-frame coordinates.
- interact_entity is the generic semantic interaction tool. Choose verbs consistent with the template capabilities.
- Do not create a new near-duplicate template every tick. Reuse TiDB templates and only define new data when the world genuinely needs a new visual concept.
"""
        return previous_system_prompt(mode) + appendix

    _director._system_prompt = system_prompt
