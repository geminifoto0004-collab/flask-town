"""Generic spatial distribution for AI-created entities.

When several spawn actions target the same semantic zone without useful
coordinates, spread them around that zone so actors remain visible instead of
occupying the exact same pixel.  No story names or entity-specific cases.
"""

from collections import defaultdict

from . import town_ai_bp as _base

_OFFSETS = [
    (0, 0), (-26, 0), (26, 0), (-52, 0), (52, 0),
    (-13, 20), (13, 20), (-39, 20), (39, 20),
    (-13, -20), (13, -20), (-39, -20), (39, -20),
]


def _clamp(value, low, high):
    return max(low, min(high, float(value)))


def install_spawn_distribution_patch():
    previous_validate = _base._validate_actions

    def validate(raw_actions):
        actions = previous_validate(raw_actions)
        if not isinstance(actions, list):
            return actions

        groups = defaultdict(list)
        for action in actions:
            if not isinstance(action, dict):
                continue
            if str(action.get("type") or "") not in {"spawn_entity", "spawn_from_template"}:
                continue
            zone = str(action.get("zone") or "")
            if zone:
                groups[zone].append(action)

        for _zone, members in groups.items():
            if len(members) <= 1:
                continue
            # The legacy validator resolves omitted x/y to the same zone center.
            # Treat tightly clustered same-zone spawns as a group that needs
            # presentation spacing while preserving genuinely distinct coords.
            xs = [float(m.get("x")) for m in members if m.get("x") is not None]
            ys = [float(m.get("y")) for m in members if m.get("y") is not None]
            clustered = not xs or not ys or (max(xs) - min(xs) < 8 and max(ys) - min(ys) < 8)
            if not clustered:
                continue
            base_x = xs[0] if xs else 320.0
            base_y = ys[0] if ys else 292.0
            for index, action in enumerate(members):
                ring = index // len(_OFFSETS)
                dx, dy = _OFFSETS[index % len(_OFFSETS)]
                if ring:
                    dx *= ring + 1
                    dy *= ring + 1
                action["x"] = round(_clamp(base_x + dx, 12, 628), 1)
                action["y"] = round(_clamp(base_y + dy, 60, 390), 1)
        return actions

    _base._validate_actions = validate
