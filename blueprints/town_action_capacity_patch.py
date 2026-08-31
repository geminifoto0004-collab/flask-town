"""Expand town action throughput without adding story-specific rules.

The underlying validators intentionally use small per-call caps.  That is useful
for a single model call, but it can silently drop later actors in a larger admin
scene.  This adapter validates in small chunks and combines the results so an
explicit request for several visible actors is not reduced to the first few.
"""

from . import town_ai_bp as _base


def install_action_capacity_patch():
    previous_validate = _base._validate_actions

    def validate_actions(raw_actions):
        if not isinstance(raw_actions, list):
            return []

        validated = []
        # Keep a generous technical ceiling to protect the Render process, but
        # do not impose a small story/actor limit.  Chunking avoids the older
        # validator's per-call truncation while preserving all of its safety
        # checks and schemas.
        source = raw_actions[:96]
        for start in range(0, len(source), 10):
            chunk = source[start:start + 10]
            result = previous_validate(chunk)
            if isinstance(result, list):
                validated.extend(result)
            if len(validated) >= 96:
                break
        return validated[:96]

    _base._validate_actions = validate_actions
