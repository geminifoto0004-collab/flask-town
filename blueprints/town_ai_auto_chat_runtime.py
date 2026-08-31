"""One-call AI conversations for the town life engine.

A whole multi-turn conversation costs one DeepSeek request. The request uses the
same TiDB character configuration, recent dialogue memory and persisted current
public context as the main director. The browser may call this occasionally when
two on-duty characters naturally decide to chat. Ordinary movement remains
local and free; a local scripted chat is only a network/API fallback.
"""

from __future__ import annotations

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


def _chat_tool():
    for tool in DIRECTOR_TOOLS:
        fn = tool.get("function") if isinstance(tool, dict) else None
        if isinstance(fn, dict) and fn.get("name") == "agent_chat":
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

        public_context = current_context(refresh_if_stale=True)
        news = recent_news_for_ai(10)
        characters = character_context()
        world = _world_slice(body.get("world"))
        tool = _chat_tool()
        if not tool:
            return jsonify({"ok": False, "error": "agent_chat tool is unavailable"}), 500

        system = f"""You write one believable conversation inside CUSTOMS AGENT TOWN in Iquique, Chile.
The participants are exactly {a} and {b}; do not substitute another permanent character.
Use the supplied TiDB character profiles, recent dialogue and world state so the conversation feels continuous.
Use natural everyday Chilean Spanish. Produce 4 to 8 turns and alternate naturally between the two speakers.
Current public information is supplied separately from the language model and is authoritative only to the extent shown.
You MAY discuss a current headline, Iquique/Tarapaca, Chile, port/ZOFRI/customs work or the current weather when it fits naturally.
A headline is only a headline fact: never invent article details, quotes, numbers, causes or outcomes that are not supplied.
Do not force current events into every chat. If nothing current fits, talk naturally about work, personal context or a recent shared event.
Avoid repeating topics visible in recentDialogue.
Use ONLY the agent_chat tool. Do not narrate outside the tool call."""

        payload = {
            "model": (os.environ.get("TOWN_AI_MODEL") or "deepseek-chat").strip(),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps({
                    "participants": [a, b],
                    "characters": characters,
                    "current_public_context": {
                        "location": public_context.get("location"),
                        "fetched_at_ms": public_context.get("fetched_at_ms") or public_context.get("updated_at_ms"),
                        "weather": public_context.get("weather") or {},
                        "sources": public_context.get("sources") or [],
                    },
                    "recent_news": news,
                    "world": world,
                }, ensure_ascii=False, separators=(",", ":"))},
            ],
            "tools": [tool],
            "tool_choice": "required",
            "temperature": 1.0,
            "max_tokens": 1100,
        }
        try:
            response = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
                timeout=(4, 25),
            )
            if not response.ok:
                raise RuntimeError(f"DeepSeek HTTP {response.status_code}: {response.text[:180]}")
            message = (((response.json().get("choices") or [{}])[0]).get("message") or {})
            raw = _tool_calls_to_actions(message)
            # Keep only the requested pair and let the final server validator
            # normalize/validate all dialogue turn fields.
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
            return jsonify({"ok": True, "actions": actions, "source": "deepseek", "news_count": len(news)})
        except requests.Timeout:
            return jsonify({"ok": False, "error": "DeepSeek request timed out"}), 504
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)[:240]}), 500
