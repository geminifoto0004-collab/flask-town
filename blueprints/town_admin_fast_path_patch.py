"""Fast, bounded DeepSeek path for manual/admin town commands.

The original stable TOWN admin call had a 12-second DeepSeek read timeout and a
small tool payload.  Later director layers added synchronous context work and a
much larger tool registry; on a default Gunicorn worker that could push a
single Render request close to the worker timeout and surface as HTTP 502.

This patch changes ONLY the manual/admin model call. Autonomous ticks keep their
own pacing. Manual commands use TiDB-persisted public context, local Iquique
clock calculation, the compact universal admin tool surface, and the original
12-second DeepSeek read bound.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
import time
from zoneinfo import ZoneInfo

import requests

from . import town_admin_runtime as _admin
from . import town_ai_bp as _base
from . import town_character_director_patch as _director
from .town_ai_director_runtime import _tool_calls_to_actions
from .town_character_tidb_runtime import character_context, refresh_runtime_character_bindings
from .town_current_context_runtime import current_context


_TZ = ZoneInfo("America/Santiago")


def _stored_context_snapshot():
    data = current_context(refresh_if_stale=False)
    return data if isinstance(data, dict) else {}


def _public_context(data):
    return {
        "location": data.get("location") or "Iquique, Chile",
        "fetched_at_ms": int(data.get("fetched_at_ms") or data.get("updated_at_ms") or 0),
        "weather": dict(data.get("weather") or {}),
        "sources": list(data.get("sources") or [])[:8],
    }


def _recent_news(data, limit=6):
    rows = data.get("news") if isinstance(data.get("news"), list) else []
    result = []
    for item in rows[: max(1, int(limit or 6))]:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        result.append({
            "title": str(item.get("title") or "")[:220],
            "source": str(item.get("source") or "")[:80],
            "published": str(item.get("published") or "")[:60],
            "category": str(item.get("category") or "")[:40],
        })
    return result


def _server_context(public):
    now = datetime.now(_TZ)
    return {
        "city": "IQUIQUE",
        "timezone": "America/Santiago",
        "local_time": now.isoformat(timespec="seconds"),
        "hour": now.hour,
        "minute": now.minute,
        "weather": dict(public.get("weather") or {}),
    }


def install_admin_fast_path_patch():
    def fast_admin_model_command(prompt, world):
        started = time.monotonic()
        refresh_runtime_character_bindings()

        key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
        if not key:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")

        model = (os.environ.get("TOWN_AI_MODEL") or "deepseek-chat").strip()
        stored = _stored_context_snapshot()
        public = _public_context(stored)
        context = _server_context(public)
        news = _recent_news(stored, 6)
        tools = _admin._select_admin_tools(prompt)

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": _director._system_prompt(
                        "The administrator is giving a story seed. Explicit requested facts/quantities are binding when physically representable; staging, dialogue and reactions remain your creative responsibility."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "admin_instruction": prompt,
                            "server_context": context,
                            "current_public_context": public,
                            "recent_news": news,
                            "characters": character_context(),
                            "world": _director._world_context(world),
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ],
            "tools": tools,
            "tool_choice": "required",
            "temperature": 0.66,
            # A composed visual plus spawn/actions cannot fit in 1500 tokens.
            "max_tokens": 4500,
        }

        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=(4, 30),
        )
        if not response.ok:
            raise RuntimeError(f"DeepSeek HTTP {response.status_code}: {response.text[:220]}")

        choice = (response.json().get("choices") or [{}])[0]
        if choice.get('finish_reason') == 'length':
            raise RuntimeError('AI blueprint was truncated; no partial scene was applied')
        message = choice.get("message") or {}
        raw_actions = _tool_calls_to_actions(message)
        metadata = _admin._scene_metadata(raw_actions)
        actions = _base._validate_actions(raw_actions)
        intent = metadata.get("intent_summary") or str(prompt)[:110]
        note = metadata.get("director_note") or "保留管理員明確指定內容，其餘依 TiDB 人物設定與目前世界自行導演。"

        return {
            "ok": True,
            "actions": actions,
            "model": model,
            "context": context,
            "thought": f"你要的：{intent}；AI 改編：{note}"[:300],
            "admin_ai_ms": int((time.monotonic() - started) * 1000),
            "admin_tool_count": len(tools),
            "admin_context_mode": "tidb_stored_only",
            **metadata,
        }

    _admin._admin_model_command = fast_admin_model_command
