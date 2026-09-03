"""One-call AI conversations for the town life engine.

A whole multi-turn conversation costs one DeepSeek request. The request uses the
same TiDB character configuration, recent dialogue memory and persisted current
public context as the main director. Conversation topic modes rotate so news is
an occasional source of texture rather than the default subject of every chat.
"""

from __future__ import annotations

import copy
import json
import os
import threading
import time

import requests
from flask import jsonify, request

from . import town_ai_bp as _base
from .town_ai_director_runtime import DIRECTOR_TOOLS, _tool_calls_to_actions
from .town_character_tidb_runtime import character_context, character_id_set
from .town_current_context_runtime import current_context, recent_news_for_ai

_INSTALLED = False
_RATE_LOCK = threading.Lock()
_LAST_PAIR_CALL = {}
_TOPIC_LOCK = threading.Lock()
_PAIR_LAST_TOPIC = {}
_TOPIC_CURSOR = 0

# This is conversational variety plumbing, not character/story hardcoding. The
# model still invents the actual subject from TiDB profiles and current world.
_TOPIC_MODES = (
    "personal_life",
    "work_small_talk",
    "food_break",
    "family_and_plans",
    "hobbies_and_memories",
    "coworker_social",
    "everyday_chile",
    "current_news",
)

_TOPIC_GUIDANCE = {
    "personal_life": "Talk about ordinary personal life, mood, routines, errands, sleep, purchases, home, or something small that happened recently. Do NOT turn it into news commentary.",
    "work_small_talk": "Talk about a small concrete work annoyance, funny routine, paperwork habit, customer/coworker behavior, break-time observation, or workplace plan. Avoid major news unless one speaker explicitly connects it.",
    "food_break": "Talk naturally about lunch, coffee, snacks, cooking, restaurants, what to eat later, or tastes/preferences grounded in the characters. No news topic unless unavoidable.",
    "family_and_plans": "Use TiDB family/personal context to discuss family, partner, children, weekend plans, errands, celebrations, travel ideas, or future plans without inventing unsupported sensitive facts.",
    "hobbies_and_memories": "Discuss hobbies, music, TV, sports, shopping, memories, habits, preferences, or something they would plausibly do after work. Keep it casual and specific.",
    "coworker_social": "Talk about coworkers, office habits, light teasing, who is diligent/lazy, recent shared events in the town, or a harmless interpersonal observation. Do not recycle the last gossip topic.",
    "everyday_chile": "Talk about wider everyday life in Chile or Latin America: prices, transport, weather changes, holidays, football, entertainment, routines, travel, or culture. This is broader than Iquique/ZOFRI and does not require a news headline.",
    "current_news": "Discuss ONE supplied current headline or current public fact, preferably from a category not used recently. It may be Iquique, Chile, Latin America, or world news. Do not discuss more than one headline in this conversation and do not reuse a recently discussed headline.",
}


def _chat_tool():
    """Return an isolated bilingual agent_chat schema for this endpoint."""
    for original in DIRECTOR_TOOLS:
        fn = original.get("function") if isinstance(original, dict) else None
        if not isinstance(fn, dict) or fn.get("name") != "agent_chat":
            continue
        tool = copy.deepcopy(original)
        try:
            item_props = tool["function"]["parameters"]["properties"]["turns"]["items"]["properties"]
            item_props["text_zh"] = {"type": "string", "minLength": 1, "maxLength": 160}
        except Exception:
            pass
        return tool
    return None


def _world_slice(world):
    source = world if isinstance(world, dict) else {}
    keep = (
        "agents", "onDutyAgents", "stats", "characterProfiles", "recentDialogue",
        "relationships", "recentDirectorActions", "worldObjects", "genericEntities",
    )
    return {key: source.get(key) for key in keep if key in source}


def _pair_allowed(a, b):
    ids = character_id_set()
    return bool(a and b and a != b and a in ids and b in ids)


def _recent_dialogue_text(world, limit=6):
    rows = world.get("recentDialogue") if isinstance(world, dict) else []
    if not isinstance(rows, list):
        return []
    output = []
    for chat in rows[-max(1, int(limit)):]:
        if not isinstance(chat, dict):
            continue
        turns = chat.get("turns") if isinstance(chat.get("turns"), list) else []
        text = " ".join(
            str(turn.get("text") or turn.get("text_zh") or "").strip()
            for turn in turns if isinstance(turn, dict)
        ).strip()
        if not text:
            text = str(chat.get("text") or "").strip()
        if text:
            output.append(text[:700])
    return output[-limit:]


def _choose_topic_mode(pair_key):
    global _TOPIC_CURSOR
    with _TOPIC_LOCK:
        previous = _PAIR_LAST_TOPIC.get(pair_key)
        for _ in range(len(_TOPIC_MODES)):
            mode = _TOPIC_MODES[_TOPIC_CURSOR % len(_TOPIC_MODES)]
            _TOPIC_CURSOR += 1
            if mode != previous:
                _PAIR_LAST_TOPIC[pair_key] = mode
                return mode
        mode = _TOPIC_MODES[_TOPIC_CURSOR % len(_TOPIC_MODES)]
        _TOPIC_CURSOR += 1
        _PAIR_LAST_TOPIC[pair_key] = mode
        return mode


def install_auto_chat_runtime():
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    @_base.town_ai_bp.route("/auto-chat", methods=["POST"])
    def town_auto_chat():
        body = request.get_json(silent=True) or {}
        a = str(body.get("from") or "").strip().upper()
        b = str(body.get("to") or "").strip().upper()
        if not _pair_allowed(a, b):
            return jsonify({"ok": False, "error": "invalid character pair"}), 400

        pair_key = "|".join(sorted((a, b)))
        now = time.monotonic()
        with _RATE_LOCK:
            previous = float(_LAST_PAIR_CALL.get(pair_key) or 0.0)
            if now - previous < 45:
                return jsonify({"ok": False, "error": "pair is still on conversation cooldown"}), 429
            _LAST_PAIR_CALL[pair_key] = now

        key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
        if not key:
            return jsonify({"ok": False, "error": "DEEPSEEK_API_KEY is not configured"}), 503

        # Do not block a conversation on public-data refresh; the background
        # context daemon owns refresh. A stale snapshot is still better than a
        # repeated/slow chat request.
        public_context = current_context(refresh_if_stale=False)
        characters = character_context()
        world = _world_slice(body.get("world"))
        recent_dialogue = _recent_dialogue_text(world, 6)
        topic_mode = _choose_topic_mode(pair_key)
        news = recent_news_for_ai(12) if topic_mode == "current_news" else []
        tool = _chat_tool()
        if not tool:
            return jsonify({"ok": False, "error": "agent_chat tool is unavailable"}), 500

        system = f"""You write one believable conversation inside CUSTOMS AGENT TOWN.
The participants are exactly {a} and {b}; do not substitute another permanent character.
Use the supplied TiDB character profiles, recent dialogue and world state so the conversation feels continuous.
Produce 4 to 8 turns and alternate naturally between the two speakers.
For EVERY turn, text must be natural everyday Chilean Spanish and text_zh must be a natural Traditional Chinese translation of the same line.

CURRENT TOPIC MODE: {topic_mode}
{_TOPIC_GUIDANCE.get(topic_mode, '')}

DIVERSITY RULES:
- The last conversations are supplied under recent_dialogue_to_avoid. Do not repeat their main event, headline, joke, complaint, or distinctive nouns unless this is clearly an intentional continuation.
- Do not make ZOFRI, customs, port incidents, fires, crime, inspections, or local headlines the default topic merely because the characters work in Iquique.
- These people have lives beyond work. Prefer concrete everyday details and different subjects across conversations.
- Iquique is their location, not the boundary of their interests. They may naturally talk about Chile, Latin America, world events, entertainment, sport, food, family, hobbies, prices, travel or personal plans when appropriate.
- Current news is allowed ONLY when topic_mode is current_news. In all other modes, do not introduce a headline just because public context exists.
- When topic_mode is current_news, discuss at most ONE supplied headline and never invent article details, quotes, numbers, causes or outcomes not supplied.
- Keep personalities distinct. Let TiDB workStyle/personality/family notes shape how each person reacts instead of making everyone sound like the same news commentator.

Use ONLY the agent_chat tool. Do not narrate outside the tool call."""

        payload = {
            "model": (os.environ.get("TOWN_AI_MODEL") or "deepseek-chat").strip(),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps({
                    "participants": [a, b],
                    "topic_mode": topic_mode,
                    "characters": characters,
                    "recent_dialogue_to_avoid": recent_dialogue,
                    "current_public_context": {
                        "location": public_context.get("location"),
                        "fetched_at_ms": public_context.get("fetched_at_ms") or public_context.get("updated_at_ms"),
                        "weather": public_context.get("weather") or {},
                    },
                    "recent_news": news,
                    "world": world,
                }, ensure_ascii=False, separators=(",", ":"))},
            ],
            "tools": [tool],
            "tool_choice": "required",
            "temperature": 1.12,
            "max_tokens": 1400,
        }
        try:
            response = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
                timeout=(4, 22),
            )
            if not response.ok:
                raise RuntimeError(f"DeepSeek HTTP {response.status_code}: {response.text[:180]}")
            message = (((response.json().get("choices") or [{}])[0]).get("message") or {})
            raw = _tool_calls_to_actions(message)
            candidate = []
            for action in raw:
                if str(action.get("type") or "") != "agent_chat":
                    continue
                x = str(action.get("from") or "").upper()
                y = str(action.get("to") or "").upper()
                if {x, y} == {a, b}:
                    candidate.append(action)
                    break
            actions = _base._validate_actions(candidate)
            if not actions:
                raise RuntimeError("DeepSeek returned no valid conversation")
            return jsonify({
                "ok": True,
                "actions": actions,
                "source": "deepseek",
                "topic_mode": topic_mode,
                "news_count": len(news),
            })
        except requests.Timeout:
            return jsonify({"ok": False, "error": "DeepSeek request timed out"}), 504
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)[:240]}), 500
