"""Remove historical three-officer roster caps from the native browser engine.

Only expressions that clearly encode the old three-person roster are rewritten.
Four-worker expressions are audited but intentionally left untouched: a ship may
legitimately have four physical work slots even when the TiDB roster has five or
more colleagues. Worker *eligibility* must be fixed at the allocator, not by
blindly increasing a job-capacity constant.
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

    rewrite_patterns = (
        ("agents_slice_3", r"agents\.slice\(\s*0\s*,\s*3\s*\)", "agents.slice()"),
        ("agents_min_3_left", r"Math\.min\(\s*3\s*,\s*agents\.length\s*\)", "agents.length"),
        ("agents_min_3_right", r"Math\.min\(\s*agents\.length\s*,\s*3\s*\)", "agents.length"),
    )

    before_counts = {name: len(re.findall(pattern, source)) for name, pattern, _replacement in rewrite_patterns}
    # Four-person expressions are diagnostic only. They may be true ship/job
    # capacity rather than an employee-roster cap, so do not rewrite them here.
    before_counts.update({
        "agents_slice_4_audit": len(re.findall(r"agents\.slice\(\s*0\s*,\s*4\s*\)", source)),
        "agents_min_4_left_audit": len(re.findall(r"Math\.min\(\s*4\s*,\s*agents\.length\s*\)", source)),
        "agents_min_4_right_audit": len(re.findall(r"Math\.min\(\s*agents\.length\s*,\s*4\s*\)", source)),
        "agents_index_0": len(re.findall(r"agents\s*\[\s*0\s*\]", source)),
        "agents_index_1": len(re.findall(r"agents\s*\[\s*1\s*\]", source)),
        "agents_index_2": len(re.findall(r"agents\s*\[\s*2\s*\]", source)),
        "agents_index_3": len(re.findall(r"agents\s*\[\s*3\s*\]", source)),
        "agents_index_4": len(re.findall(r"agents\s*\[\s*4\s*\]", source)),
        "working_ship_mentions": len(re.findall(r"workingShip", source)),
        "inspect_mentions": len(re.findall(r"\binspect\b", source)),
    })

    for _name, pattern, replacement in rewrite_patterns:
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
