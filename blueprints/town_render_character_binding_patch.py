"""Final browser character binding for CUSTOMS AGENT TOWN.

The historical browser build and a few compatibility overlays still refer to
three old sprite-slot identifiers.  Those identifiers are not character data;
this final render pass binds every legacy slot to the current active TiDB core
characters after all other HTML patches have been composed.
"""

import re

from .town_character_tidb_runtime import character_context


_LEGACY_SLOTS = ("MIA", "ANA", "LIA")


def patch_render_character_bindings(html: str) -> str:
    try:
        rows = character_context()
    except Exception:
        return html
    if not rows:
        return html

    for index, legacy in enumerate(_LEGACY_SLOTS):
        if index >= len(rows):
            break
        row = rows[index] if isinstance(rows[index], dict) else {}
        current_id = str(row.get("id") or "").strip().upper()
        if not current_id:
            continue
        html = re.sub(rf"\b{re.escape(legacy)}\b", current_id, html)
    return html
