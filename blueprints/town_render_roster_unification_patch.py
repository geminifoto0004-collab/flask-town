"""Remove historical three-officer caps from the mature native browser engine.

This patch runs on the decompressed original game HTML BEFORE the TiDB colleague
extension is injected. It changes only expressions explicitly tied to `agents`
and a literal capacity of three. It does not alter unrelated three-item UI or
story limits.
"""

import re


def patch_render_roster_unification(html: str) -> str:
    if "town-native-roster-unification" in html:
        return html

    source = html
    replacements = 0

    patterns = (
        # Any old `agents.slice(0,3)` participant pool becomes the complete
        # current roster. `slice()` keeps a defensive copy when the caller
        # expected one.
        (r"agents\.slice\(\s*0\s*,\s*3\s*\)", "agents.slice()"),
        # Typical loops/capacity calculations from the original three-slot game.
        (r"Math\.min\(\s*3\s*,\s*agents\.length\s*\)", "agents.length"),
        (r"Math\.min\(\s*agents\.length\s*,\s*3\s*\)", "agents.length"),
    )

    for pattern, replacement in patterns:
        source, count = re.subn(pattern, replacement, source)
        replacements += count

    # Keep a tiny browser diagnostic so a screenshot/console can tell whether
    # this build actually removed any legacy roster caps.
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
