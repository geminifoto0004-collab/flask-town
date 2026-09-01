"""Autonomous cron heartbeat for CUSTOMS AGENT TOWN.

An external scheduler may call /api/town/tick every few minutes.  Each tick gives
DeepSeek the full validated director tool set and lets it decide whether the
world should chat, work, react, create a visitor/object, or remain quiet.  A
small TiDB-backed activity state only prevents the town from staying completely
inactive for too many consecutive ticks; it does not hard-code story content.
"""

from __future__ import annotations

import json
import os
import time

import requests
from flask import jsonify, request

from database import execute_sql, get_db_connection
from . import town_ai_bp as _base
from .town_ai_director_runtime import DIRECTOR_TOOLS, _tool_calls_to_actions
from .town_character_director_patch import _public_context_for_ai, _system_prompt, _world_context
from .town_character_tidb_runtime import character_context
from .town_current_context_runtime import recent_news_for_ai
from .town_dialogue_tidb_runtime import _recent_dialogues, _save_dialogue

_STATE_KEY = "main"
_SCHEMA_READY = False


def _close(conn):
    try:
        conn.close()
    except Exception:
        pass


def _ensure_state_table():
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        execute_sql(cur, """
            CREATE TABLE IF NOT EXISTS town_director_state (
                state_key VARCHAR(64) PRIMARY KEY,
                payload_json MEDIUMTEXT NOT NULL,
                updated_at_ms BIGINT NOT NULL
            )
        """)
        conn.commit()
        _SCHEMA_READY = True
    finally:
        _close(conn)


def _read_state():
    try:
        _ensure_state_table()
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            execute_sql(cur, "SELECT payload_json FROM town_director_state WHERE state_key = ?", (_STATE_KEY,))
            row = cur.fetchone()
            if not row:
                return {}
            raw = row.get("payload_json") if isinstance(row, dict) else row[0]
            data = json.loads(raw or "{}")
            return data if isinstance(data, dict) else {}
        finally:
            _close(conn)
    except Exception:
        return {}


def _write_state(state):
    _ensure_state_table()
    now_ms = int(time.time() * 1000)
    raw = json.dumps(state if isinstance(state, dict) else {}, ensure_ascii=False, separators=(",", ":"))
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        execute_sql(cur, """
            INSERT INTO town_director_state (state_key, payload_json, updated_at_ms)
            VALUES (?, ?, ?)
            ON DUPLICATE KEY UPDATE
              payload_json = VALUES(payload_json),
              updated_at_ms = VALUES(updated_at_ms)
        """, (_STATE_KEY, raw, now_ms))
        conn.commit()
    finally:
        _close(conn)


def _authorized():
    expected = (os.environ.get("TOWN_CRON_TOKEN") or "").strip()
    if not expected:
        return False
    auth = (request.headers.get("Authorization") or "").strip()
    supplied = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not supplied:
        supplied = (request.args.get("token") or "").strip()
    return supplied == expected


def _latest_dialogue_at():
    try:
        rows = _recent_dialogues(4)
    except Exception:
        rows = []
    latest = 0
    for item in rows or []:
        if isinstance(item, dict):
            try:
                latest = max(latest, int(item.get("at") or 0))
            except Exception:
                pass
    return latest


def _activity_pressure(state, now_ms, latest_chat_ms):
    idle_streak = int(state.get("idle_streak") or 0)
    last_visible = int(state.get("last_visible_at_ms") or 0)
    minutes_visible = 9999 if not last_visible else max(0.0, (now_ms - last_visible) / 60000.0)
    minutes_chat = 9999 if not latest_chat_ms else max(0.0, (now_ms - latest_chat_ms) / 60000.0)

    score = 0
    if idle_streak >= 2:
        score += 2
    elif idle_streak == 1:
        score += 1
    if minutes_visible >= 15:
        score += 2
    elif minutes_visible >= 10:
        score += 1
    if minutes_chat >= 20:
        score += 1
    return score, minutes_visible, minutes_chat


def _model_tick(world, state, now_ms, pressure, minutes_visible, minutes_chat):
    key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    model = (os.environ.get("TOWN_AI_MODEL") or "deepseek-chat").strip()
    force_activity = pressure >= 2
    mode = "This is the five-minute autonomous heartbeat of the persistent town."
    system = _system_prompt(mode) + f"""

HEARTBEAT RULES:
- You are deciding what should happen during this heartbeat. You have the full tool set; choose the most believable action(s), not a preset routine.
- You MAY return no tool call when the town has been recently active and a quiet moment makes sense.
- Do not make everyone talk every heartbeat. Work, movement, observation, visitors, small world reactions, relationships and silence are all valid.
- Avoid repeating the same action/topic/person pair just because it is easy.
- If people converse, use agent_chat and make it a genuine multi-turn conversation informed by recentDialogue, current news/weather and character profiles.
- If current information is relevant, use only the supplied facts; never invent news details.
- Activity pressure is {pressure}. Minutes since last visible director activity: {minutes_visible:.1f}. Minutes since last stored conversation: {minutes_chat:.1f}.
- When activity pressure is high, make at least one visible or socially meaningful thing happen so the town does not remain lifeless for too long; you still decide WHAT happens and WHO is involved.
- Prefer 1 to 3 coherent tools rather than noisy action spam.
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps({
                "heartbeat": {
                    "now_ms": now_ms,
                    "tick_count": int(state.get("tick_count") or 0) + 1,
                    "idle_streak": int(state.get("idle_streak") or 0),
                    "activity_pressure": pressure,
                },
                "current_public_context": _public_context_for_ai(),
                "recent_news": recent_news_for_ai(10),
                "characters": character_context(),
                "world": _world_context(world),
            }, ensure_ascii=False, separators=(",", ":"))},
        ],
        "tools": DIRECTOR_TOOLS,
        "tool_choice": "required" if force_activity else "auto",
        "temperature": 1.05,
        "max_tokens": 1800,
    }
    response = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=(4, 28),
    )
    if not response.ok:
        raise RuntimeError(f"DeepSeek HTTP {response.status_code}: {response.text[:220]}")
    message = (((response.json().get("choices") or [{}])[0]).get("message") or {})
    raw_actions = _tool_calls_to_actions(message)
    actions = _base._validate_actions(raw_actions)
    return actions, model


def _persist_dialogues(actions, now_ms):
    saved = 0
    for index, action in enumerate(actions or []):
        if not isinstance(action, dict) or str(action.get("type") or "") != "agent_chat":
            continue
        a = str(action.get("from") or "").upper()
        b = str(action.get("to") or "").upper()
        turns = action.get("turns") if isinstance(action.get("turns"), list) else []
        if not a or not b or not turns:
            continue
        ok, _detail = _save_dialogue({
            "id": f"cron-{now_ms}-{index}",
            "at": now_ms + index,
            "members": [a, b],
            "turns": turns,
            "source": "cron",
        })
        if ok:
            saved += 1
    return saved


def install_cron_tick_runtime():
    @_base.town_ai_bp.route("/tick", methods=["GET", "POST"])
    def town_tick():
        if not _authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 401

        now_ms = int(time.time() * 1000)
        state = _read_state()
        latest_chat_ms = max(int(state.get("last_chat_at_ms") or 0), _latest_dialogue_at())
        pressure, minutes_visible, minutes_chat = _activity_pressure(state, now_ms, latest_chat_ms)

        try:
            stored = _base._read_json(_base._WORLD_PATH, {})
            world = _base._clean_world(stored.get("world") if isinstance(stored, dict) else {})
            actions, model = _model_tick(world, state, now_ms, pressure, minutes_visible, minutes_chat)

            dialogue_count = _persist_dialogues(actions, now_ms)
            evolved_world = _base._apply_persistent_actions(world, actions)
            if isinstance(evolved_world, dict):
                history = evolved_world.get("recentDirectorActions")
                history = list(history) if isinstance(history, list) else []
                history.append({
                    "at": now_ms,
                    "source": "cron_tick",
                    "types": [str(a.get("type") or "") for a in actions if isinstance(a, dict)][:12],
                })
                evolved_world["recentDirectorActions"] = history[-24:]
            _base._write_json(_base._WORLD_PATH, {"saved_at": int(time.time()), "world": evolved_world})

            visible = bool(actions)
            chatted = any(isinstance(a, dict) and a.get("type") == "agent_chat" for a in actions)
            next_state = {
                "tick_count": int(state.get("tick_count") or 0) + 1,
                "idle_streak": 0 if visible else int(state.get("idle_streak") or 0) + 1,
                "last_tick_at_ms": now_ms,
                "last_visible_at_ms": now_ms if visible else int(state.get("last_visible_at_ms") or 0),
                "last_chat_at_ms": now_ms if chatted else latest_chat_ms,
                "last_action_types": [str(a.get("type") or "") for a in actions if isinstance(a, dict)][:12],
            }
            _write_state(next_state)
            return jsonify({
                "ok": True,
                "model": model,
                "actions": actions,
                "action_count": len(actions),
                "dialogues_saved": dialogue_count,
                "activity_pressure": pressure,
                "idle_streak": next_state["idle_streak"],
            })
        except requests.Timeout:
            return jsonify({"ok": False, "error": "DeepSeek request timed out"}), 504
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)[:300]}), 500
