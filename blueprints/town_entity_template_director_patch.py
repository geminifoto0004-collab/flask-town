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
- If no existing template can express a requested visible thing, the fastest path is to put an ORIGINAL compact visual directly in spawn_entity, entity_scene or each world_scene actor. Define a TiDB template first only when the appearance is genuinely reusable.
- Template visual parts are generic rect/ellipse primitives with offsets, size, color and layer. Keep compositions compact and readable rather than producing excessive parts.
- For every distinctive fictional creature, character, robot, monster or animal, visual.parts is mandatory. Design its recognizable silhouette and distinctive features yourself, not a generic dog/human sprite with a new label. Use 12–36 purposeful parts where needed; never substitute only bodyColor/accentColor for a requested new appearance.
- Preserve semanticType (for example dragon, electric_mouse, robot or ghost) independently from the renderer base class. Never reduce two visibly different concepts to the same generic animal blueprint.
- All part x/y coordinates are CENTER offsets from the actor's ground anchor (0,0), y grows downward. Feet meet y=0; head/body normally have negative y. Rectangles and ellipses BOTH use center offsets. Layer sorts back to front. Explicitly design the silhouette, face/features, clothing/accessories and contrasting colors appropriate to the requested concept.
- Keep ordinary actors roughly 24–54 canvas pixels tall and 18–52 pixels wide after scale so they are readable without covering the room.
- Parts may include motion {{on:move|idle|interact|always, dx,dy,period,phase}}. These animate offsets with a sine wave. Design motion appropriate to anatomy and intended interaction; no code or named-character special cases.
- Use collision w/h for the ground footprint, not the full visible height. Keep actor destinations on walkable floor, approach people/furniture from a free adjacent point, and never place a foot anchor on a monitor or desk.
- Dialogue and exclamations must include text in natural Chilean Spanish and text_zh in Simplified Chinese. Translate catchphrases by intention and tone, never by copying Chinese into Spanish.
- New story actors and moving world objects are temporary by default. Set persistent=true only when the administrator explicitly says they should remain permanently; otherwise end the scene naturally and let the entity expire.
- Templates describe appearance, mobility, collision and capabilities. Instances describe where a thing currently exists and what it is doing.
- After spawning, use generic movement/social/interaction tools. The browser handles pathfinding-like routing, facing, walk motion and interaction animation; do not emit per-frame coordinates.
- interact_entity is the generic semantic interaction tool. Choose verbs consistent with the template capabilities.
- Do not create a new near-duplicate template every tick. Reuse TiDB templates and only define new data when the world genuinely needs a new visual concept.
"""
        return previous_system_prompt(mode) + appendix

    _director._system_prompt = system_prompt
