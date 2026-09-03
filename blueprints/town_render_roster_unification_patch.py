"""Remove historical fixed-roster caps from the mature native browser engine.

This patch runs on the decompressed original game HTML BEFORE the TiDB colleague
extension is injected. It changes only expressions explicitly tied to `agents`
and the old fixed capacities of three/four. It does not alter unrelated numeric
limits, pair selection, UI caps or story behavior.
"""

import re

_LAST_REPLACEMENTS = 0
_LAST_AUDIT = {}


def roster_unification_stats():
    return {
        "replacements": int(_LAST_REPLACEMENTS),
        **dict(_LAST_AUDIT),
    }


def patch_render_roster_unification(html: str) -> str:
    global _LAST_REPLACEMENTS, _LAST_AUDIT
    if "town-native-roster-unification" in html:
        return html

    source = html
    replacements = 0

    patterns = (
        # Historical 3-person roster caps.
        ("agents_slice_3", r"agents\.slice\(\s*0\s*,\s*3\s*\)", "agents.slice()"),
        ("agents_min_3_left", r"Math\.min\(\s*3\s*,\s*agents\.length\s*\)", "agents.length"),
        ("agents_min_3_right", r"Math\.min\(\s*agents\.length\s*,\s*3\s*\)", "agents.length"),
        # A later native workflow used four worker slots. With five TiDB
        # colleagues this manifests exactly as #1-#4 working while #5 never gets
        # assigned. These patterns are still roster-capacity expressions, not a
        # story-specific rule, so they must also use the complete roster.
        ("agents_slice_4", r"agents\.slice\(\s*0\s*,\s*4\s*\)", "agents.slice()"),
        ("agents_min_4_left", r"Math\.min\(\s*4\s*,\s*agents\.length\s*\)", "agents.length"),
        ("agents_min_4_right", r"Math\.min\(\s*agents\.length\s*,\s*4\s*\)", "agents.length"),
    )

    before_counts = {name: len(re.findall(pattern, source)) for name, pattern, _replacement in patterns}
    before_counts.update({
        # Audit-only fixed-index references. We do not rewrite these blindly,
        # because an index can be semantically meaningful (e.g. choosing a lead
        # officer) even when roster capacity is dynamic.
        "agents_index_0": len(re.findall(r"agents\s*\[\s*0\s*\]", source)),
        "agents_index_1": len(re.findall(r"agents\s*\[\s*1\s*\]", source)),
        "agents_index_2": len(re.findall(r"agents\s*\[\s*2\s*\]", source)),
        "agents_index_3": len(re.findall(r"agents\s*\[\s*3\s*\]", source)),
        "agents_index_4": len(re.findall(r"agents\s*\[\s*4\s*\]", source)),
        "working_ship_mentions": len(re.findall(r"workingShip", source)),
        "inspect_mentions": len(re.findall(r"\binspect\b", source)),
    })

    for _name, pattern, replacement in patterns:
        source, count = re.subn(pattern, replacement, source)
        replacements += count

    _LAST_REPLACEMENTS = replacements
    _LAST_AUDIT = before_counts

    marker = (
        '<script id="town-native-roster-unification">'
        f'window.TOWN_NATIVE_ROSTER_UNIFICATION={{replacements:{replacements}}};'
        '</script>'
    )
    if "</body>" in source:
        source = source.replace("</body>", marker + "</body>", 1)
    else:
        source += marker
    return source
