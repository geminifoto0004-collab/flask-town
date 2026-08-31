"""Persistent dynamic character life-profile support for CUSTOMS AGENT TOWN.

Profiles follow the current runtime character IDs.  There is no fixed officer
count; TiDB decides how many active core characters exist.
"""

from . import town_ai_bp as _base
from .town_ai_director_runtime import DIRECTOR_TOOLS, _AGENT_ENUM, _fn

_ZODIAC = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]


def _ensure_tool():
    if any((item.get("function") or {}).get("name") == "agent_profile" for item in DIRECTOR_TOOLS):
        return
    DIRECTOR_TOOLS.insert(4, _fn(
        "agent_profile",
        "Create or update persistent life context for one current core character. Facts provide context for AI choices but never force stereotypes.",
        {
            "agent": {"type": "string", "enum": _AGENT_ENUM},
            "age": {"type": "integer", "minimum": 18, "maximum": 100},
            "gender": {"type": "string", "maxLength": 24},
            "zodiac": {"type": "string", "enum": _ZODIAC},
            "maritalStatus": {"type": "string", "enum": ["single", "partnered", "married", "divorced", "widowed"]},
            "hasChildren": {"type": "boolean"},
            "childrenCount": {"type": "integer", "minimum": 0, "maximum": 20},
            "likes": {"type": "array", "maxItems": 20, "items": {"type": "string", "maxLength": 40}},
            "dislikes": {"type": "array", "maxItems": 20, "items": {"type": "string", "maxLength": 40}},
            "interests": {"type": "array", "maxItems": 20, "items": {"type": "string", "maxLength": 40}},
        },
        ["agent"],
    ))


def _current_ids():
    return {str(v or "").upper() for v in _AGENT_ENUM if str(v or "").strip()}


def _clean_text_list(value):
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        text = str(item or "").strip()[:40]
        if text and text not in out:
            out.append(text)
        if len(out) >= 20:
            break
    return out


def _clean_profile(profile):
    if not isinstance(profile, dict):
        return {}
    cleaned = {}
    try:
        if profile.get("age") is not None:
            cleaned["age"] = max(18, min(100, int(profile.get("age"))))
    except Exception:
        pass
    for key, limit in (("gender", 24), ("zodiac", 18), ("maritalStatus", 24)):
        if profile.get(key) is not None:
            cleaned[key] = str(profile.get(key) or "")[:limit]
    if profile.get("hasChildren") is not None:
        cleaned["hasChildren"] = bool(profile.get("hasChildren"))
    try:
        if profile.get("childrenCount") is not None:
            cleaned["childrenCount"] = max(0, min(20, int(profile.get("childrenCount"))))
    except Exception:
        pass
    for key in ("likes", "dislikes", "interests"):
        cleaned[key] = _clean_text_list(profile.get(key))
    return cleaned


def install_profile_runtime():
    _ensure_tool()
    previous_clean = _base._clean_world
    previous_validate = _base._validate_actions
    previous_apply = _base._apply_persistent_actions

    def clean_world(world):
        cleaned = previous_clean(world)
        if not isinstance(world, dict):
            return cleaned

        valid_ids = _current_ids()
        source_agents = [a for a in world.get("agents", []) if isinstance(a, dict)] if isinstance(world.get("agents"), list) else []
        cleaned_agents = [dict(a) for a in cleaned.get("agents", []) if isinstance(a, dict)]
        for clean_agent in cleaned_agents:
            name = str(clean_agent.get("name") or clean_agent.get("slot") or "").upper()
            source = next((a for a in source_agents if str(a.get("name") or a.get("slot") or "").upper() == name), None)
            if source:
                profile = _clean_profile(source.get("profile"))
                if profile:
                    clean_agent["profile"] = profile
        if cleaned_agents:
            cleaned["agents"] = cleaned_agents

        profiles = []
        supplied_profiles = world.get("characterProfiles") if isinstance(world.get("characterProfiles"), list) else []
        for item in supplied_profiles:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").upper()
            if name not in valid_ids:
                continue
            profiles.append({"name": name, "profile": _clean_profile(item.get("profile"))})

        if not profiles:
            for agent in cleaned.get("agents", []):
                if not isinstance(agent, dict):
                    continue
                name = str(agent.get("name") or agent.get("slot") or "").upper()
                if name in valid_ids:
                    profiles.append({"name": name, "profile": _clean_profile(agent.get("profile"))})
        if profiles:
            cleaned["characterProfiles"] = profiles

        recent_dialogue = []
        for item in world.get("recentDialogue") if isinstance(world.get("recentDialogue"), list) else []:
            if not isinstance(item, dict):
                continue
            members = [str(v or "").upper() for v in (item.get("members") or []) if str(v or "").upper() in valid_ids]
            text = str(item.get("text") or "")[:520]
            recent_dialogue.append({"at": item.get("at"), "members": members, "text": text})
        if recent_dialogue:
            cleaned["recentDialogue"] = recent_dialogue[-24:]

        if world.get("profileGuidance"):
            cleaned["profileGuidance"] = str(world.get("profileGuidance"))[:1200]
        return cleaned

    def validate_actions(raw_actions):
        if not isinstance(raw_actions, list):
            return []
        valid_ids = _current_ids()
        output = []
        for item in raw_actions:
            if not isinstance(item, dict) or str(item.get("type") or "") != "agent_profile":
                output.extend(previous_validate([item]))
            else:
                agent = str(item.get("agent") or "").upper()
                if agent in valid_ids:
                    profile = _clean_profile(item)
                    if profile:
                        output.append({"type": "agent_profile", "agent": agent, **profile})
            if len(output) >= 64:
                break
        return output[:64]

    def apply_persistent_actions(world, actions):
        actions = actions or []
        profile_actions = [a for a in actions if a.get("type") == "agent_profile"]
        evolved = previous_apply(world, [a for a in actions if a.get("type") != "agent_profile"])
        agents = [dict(a) for a in evolved.get("agents", []) if isinstance(a, dict)]
        for action in profile_actions:
            for agent in agents:
                if str(agent.get("name") or agent.get("slot") or "").upper() == action.get("agent"):
                    current = _clean_profile(agent.get("profile"))
                    current.update(_clean_profile(action))
                    agent["profile"] = current
                    break
        valid_ids = _current_ids()
        evolved["agents"] = agents
        evolved["characterProfiles"] = [
            {"name": str(agent.get("name") or agent.get("slot") or "").upper(), "profile": _clean_profile(agent.get("profile"))}
            for agent in agents
            if str(agent.get("name") or agent.get("slot") or "").upper() in valid_ids
        ]
        return evolved

    _base._clean_world = clean_world
    _base._validate_actions = validate_actions
    _base._apply_persistent_actions = apply_persistent_actions
