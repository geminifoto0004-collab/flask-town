"""Make automatic/admin directing use TiDB character configuration only."""

from __future__ import annotations

import json
import os
import time

import requests

from . import town_ai_bp as _base
from . import town_admin_runtime as _admin
from . import town_ai_grounded_director as _grounded
from . import town_ai_language_runtime as _language
from .town_ai_director_runtime import DIRECTOR_TOOLS, _recent_news, _tool_calls_to_actions
from .town_character_tidb_runtime import character_context, character_id_set, character_ids, refresh_runtime_character_bindings


def _world_context(world):
    source = world if isinstance(world, dict) else {}
    keep = (
        "worldMap", "agents", "onDutyAgents", "nightShiftAgent", "stats",
        "worldObjects", "genericEntities", "seaCreatures", "visitors", "characterProfiles",
        "recentDialogue", "dialoguePolicy", "relationships", "furniture", "plants", "dogs",
        "recentDirectorActions",
    )
    return {key: source.get(key) for key in keep if key in source}


def _system_prompt(mode):
    ids = character_ids()
    characters = character_context()
    return f"""You are the WORLD DIRECTOR of a persistent pixel-art customs office in Iquique, Chile.
{mode}

CORE CHARACTER CONFIGURATION IS DATABASE DATA, NOT SOURCE-CODE LORE.
- The current core officer IDs are exactly: {json.dumps(ids, ensure_ascii=False)}.
- Their authoritative life/personality/work configuration is: {json.dumps(characters, ensure_ascii=False)}.
- Never invent an additional permanent officer or rename a core officer unless a supported personnel/config action explicitly changes database state.
- Treat birth year, family notes, partner/marriage facts, children, career state, work style, personality notes and traits as persistent facts.
- Work style influences behavior naturally: a diligent person tends to work/focus more; a slacker may chat, wander, rest or procrastinate more, but neither is mechanically forced every tick.
- Family facts can naturally affect conversation and visits. Do not repeat them every conversation.

WORLD DIRECTION:
- Every visible physical/social event must be represented by a provided tool call. Do not narrate events that the engine cannot execute.
- Existing core officers use officer tools. New temporary people/animals/vehicles/items use the generic entity tools.
- For multi-step temporary scenes, use entity_scene when useful; otherwise compose spawn_entity, move_entity, say/give/wait and leave/remove_entity.
- Respect current onDutyAgents and nightShiftAgent. Do not make an off-duty core officer physically act in the office.
- Ship/customs work has priority when active work exists.
- Read recentDialogue and recentDirectorActions to avoid repetitive loops.
- Dialogue should be natural everyday Chilean Spanish; when translation fields exist, also provide natural Traditional Chinese.
- Relationships and reactions are not forced merely by gender, age, family state or attraction.
- Use world state and the database character configuration rather than hard-coded character assumptions.
- Never output JavaScript, SQL, shell commands, URLs, secrets or executable code.
"""


def dynamic_call_model(world, evolution, retry_note=""):
    refresh_runtime_character_bindings()
    key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    model = (os.environ.get("TOWN_AI_MODEL") or "deepseek-chat").strip()
    context = _base._iquique_context()
    news = _recent_news()
    mode = "This is an autonomous world-director tick." if evolution else "This is a manual test tick; choose at least one executable tool."
    retry = "\nPrevious output produced no executable action. Use only current database-defined officer IDs and valid tools." if retry_note else ""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _system_prompt(mode) + retry},
            {"role": "user", "content": json.dumps({
                "server_context": context,
                "recent_news": news,
                "characters": character_context(),
                "world": _world_context(world),
            }, ensure_ascii=False, separators=(",", ":"))},
        ],
        "tools": DIRECTOR_TOOLS,
        "tool_choice": "auto" if evolution else "required",
        "temperature": 1.12,
        "max_tokens": 1900,
    }
    response = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=35,
    )
    if not response.ok:
        raise RuntimeError(f"DeepSeek HTTP {response.status_code}: {response.text[:260]}")
    message = (((response.json().get("choices") or [{}])[0]).get("message") or {})
    actions = _tool_calls_to_actions(message)
    return json.dumps({"thought": "", "actions": actions}, ensure_ascii=False), model, context, news


def dynamic_admin_model_command(prompt, world):
    refresh_runtime_character_bindings()
    key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    model = (os.environ.get("TOWN_AI_MODEL") or "deepseek-chat").strip()
    context = _base._iquique_context()
    tools = _admin._select_admin_tools(prompt)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _system_prompt(
                "The administrator is giving a story seed. Explicit requested facts/quantities are binding when physically representable; staging, dialogue and reactions remain your creative responsibility."
            )},
            {"role": "user", "content": json.dumps({
                "admin_instruction": prompt,
                "server_context": context,
                "characters": character_context(),
                "world": _world_context(world),
            }, ensure_ascii=False, separators=(",", ":"))},
        ],
        "tools": tools,
        "tool_choice": "required",
        "temperature": 0.70,
        "max_tokens": 2100,
    }
    response = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=(4, 25),
    )
    if not response.ok:
        raise RuntimeError(f"DeepSeek HTTP {response.status_code}: {response.text[:220]}")
    message = (((response.json().get("choices") or [{}])[0]).get("message") or {})
    raw_actions = _tool_calls_to_actions(message)
    metadata = _admin._scene_metadata(raw_actions)
    actions = _base._validate_actions(raw_actions)
    intent = metadata.get("intent_summary") or str(prompt)[:110]
    note = metadata.get("director_note") or "保留管理員明確指定內容，其餘依 TiDB 人物設定與目前世界狀態導演。"
    return {
        "ok": True,
        "actions": actions,
        "model": model,
        "context": context,
        "thought": f"你要的：{intent}；AI 改編：{note}"[:300],
        **metadata,
    }


def _dynamic_rotating_night_agent(context):
    ids = character_ids()
    if not ids:
        return ""
    try:
        local_time = str((context or {}).get("local_time") or "")
        day_key = int("".join(ch for ch in local_time[:10] if ch.isdigit()) or int(time.time() // 86400))
    except Exception:
        day_key = int(time.time() // 86400)
    return ids[abs(day_key) % len(ids)]


def _dynamic_on_duty_agents(world, context):
    world = world if isinstance(world, dict) else {}
    ids = character_id_set()
    if not ids:
        return set()
    named = world.get("onDutyAgents")
    if isinstance(named, list):
        result = {str(v or "").upper() for v in named if str(v or "").upper() in ids}
        if result:
            return result
    agents = world.get("agents") if isinstance(world.get("agents"), list) else []
    explicit = {
        str(a.get("name") or a.get("slot") or "").upper()
        for a in agents if isinstance(a, dict) and a.get("onDuty") is True
    } & ids
    if explicit:
        return explicit
    hour = int((context or {}).get("hour") or 0)
    if hour >= 20 or hour < 7:
        night = str(world.get("nightShiftAgent") or "").upper()
        if night not in ids:
            night = _dynamic_rotating_night_agent(context)
        return {night} if night else set()
    result = {
        str(a.get("name") or a.get("slot") or "").upper()
        for a in agents
        if isinstance(a, dict) and not bool(a.get("manualOffDuty")) and str(a.get("name") or a.get("slot") or "").upper() in ids
    }
    return result or ids


def install_character_director_patch():
    refresh_runtime_character_bindings(force=True)
    _language._call_model = dynamic_call_model
    _grounded._call_model = dynamic_call_model
    _grounded._rotating_night_agent = _dynamic_rotating_night_agent
    _grounded._on_duty_agents = _dynamic_on_duty_agents
    _admin._admin_model_command = dynamic_admin_model_command
