"""Remove historical three-officer caps from the mature native browser engine.

This patch runs on the decompressed original game HTML BEFORE the TiDB colleague
extension is injected. It changes only expressions explicitly tied to `agents`
and a literal capacity of three. It does not alter unrelated three-item UI or
story limits.
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
        (r"agents\.slice\(\s*0\s*,\s*3\s*\)", "agents.slice()"),
        (r"Math\.min\(\s*3\s*,\s*agents\.length\s*\)", "agents.length"),
        (r"Math\.min\(\s*agents\.length\s*,\s*3\s*\)", "agents.length"),
    )

    before_counts = {
        "agents_slice_3": len(re.findall(patterns[0][0], source)),
        "agents_min_3_left": len(re.findall(patterns[1][0], source)),
        "agents_min_3_right": len(re.findall(patterns[2][0], source)),
        # Audit-only hints for other fixed-index patterns. These are not blindly
        # rewritten because an individual index may be semantically meaningful.
        "agents_index_0": len(re.findall(r"agents\s*\[\s*0\s*\]", source)),
        "agents_index_1": len(re.findall(r"agents\s*\[\s*1\s*\]", source)),
        "agents_index_2": len(re.findall(r"agents\s*\[\s*2\s*\]", source)),
    }

    for pattern, replacement in patterns:
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
