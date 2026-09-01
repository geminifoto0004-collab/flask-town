"""Reliability guard for manual/admin town directing.

Keep manual commands fast by reading already-persisted public context instead of
blocking on external news/weather refreshes, and prevent arrival/appearance
instructions from succeeding as prose without executable spawn actions.
"""

from __future__ import annotations

from . import town_admin_runtime as _admin
from . import town_character_director_patch as _director
from .town_current_context_runtime import current_context


def _stored_public_context_for_ai():
    data = current_context(refresh_if_stale=False)
    if not isinstance(data, dict):
        return {}
    return {
        "location": data.get("location") or "Iquique, Chile",
        "fetched_at_ms": int(data.get("fetched_at_ms") or data.get("updated_at_ms") or 0),
        "weather": dict(data.get("weather") or {}),
        "sources": list(data.get("sources") or []),
    }


def _stored_recent_news(limit=10):
    data = current_context(refresh_if_stale=False)
    rows = data.get("news") if isinstance(data, dict) else []
    result = []
    for item in (rows or [])[: max(1, int(limit or 10))]:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        result.append({
            "title": str(item.get("title") or "")[:220],
            "source": str(item.get("source") or "")[:80],
            "published": str(item.get("published") or "")[:60],
            "category": str(item.get("category") or "")[:40],
        })
    return result


def _looks_like_new_entity_request(prompt):
    text = str(prompt or "").lower()
    # Generic arrival/appearance semantics only; no story- or actor-specific names.
    markers = (
        "來了", "来了", "來一", "来一", "出現", "出现", "進來", "进来", "到訪", "到访",
        "arrive", "arrived", "comes", "come in", "appear", "appears", "visit", "visits",
        "llega", "llegan", "aparece", "aparecen", "visita", "visitan",
    )
    return any(marker in text for marker in markers)


def _has_spawn(actions):
    spawn_types = {"spawn_entity", "spawn_from_template", "world_object_spawn", "sea_creature_spawn", "dog_visit", "former_visit"}
    return any(isinstance(action, dict) and str(action.get("type") or "") in spawn_types for action in (actions or []))


def install_admin_reliability_patch():
    # Manual commands use the already-persisted snapshot. Background refresh/cron
    # remains responsible for network I/O, keeping the request comfortably below
    # the Render/gunicorn timeout budget.
    _director._public_context_for_ai = _stored_public_context_for_ai
    _director.recent_news_for_ai = _stored_recent_news

    previous_system_prompt = _director._system_prompt

    def system_prompt(mode):
        return previous_system_prompt(mode) + """

EXECUTABLE REPRESENTATION AUDIT — HARD RULES:
- One spawn_entity, spawn_from_template, or entity_scene represents exactly ONE newly created actor/entity.
- If the administrator explicitly requests N new actors/entities, emit N distinct creation calls with distinct stable ids. Never satisfy quantity only in intentSummary, directorNote, prose, or dialogue.
- A sentence saying somebody arrived/appeared/entered is NOT execution. Every newly appearing person, animal, vehicle, item or decoration must have a corresponding executable creation tool.
- entity_scene is one actor's complete scene. For multiple new actors, use multiple entity_scene calls or multiple spawn calls.
- Before finishing, compare every explicit requested new entity against your tool calls and add any missing creation calls.
"""

    _director._system_prompt = system_prompt

    previous_command = _admin._admin_model_command

    def reliable_admin_model_command(prompt, world):
        result = previous_command(prompt, world)
        actions = result.get("actions") if isinstance(result, dict) else []
        if not (_looks_like_new_entity_request(prompt) and not _has_spawn(actions)):
            return result

        audit_prompt = (
            str(prompt).strip()
            + "\n\nEXECUTABLE AUDIT: Your prior attempt described an arrival/appearance but produced no creation action. "
              "Rebuild the scene using executable tools. Every explicitly requested new actor/entity must get its own distinct "
              "spawn_entity, spawn_from_template, or entity_scene call. One entity_scene creates exactly one actor. "
              "Do not count prose, intentSummary, directorNote, movement, or an existing core-officer action as creating the requested entity."
        )
        retry = previous_command(audit_prompt, world)
        retry_actions = retry.get("actions") if isinstance(retry, dict) else []
        if _has_spawn(retry_actions):
            return retry

        # Never claim a visible scene succeeded when no entity was actually created.
        return {
            "ok": False,
            "actions": [],
            "model": (retry or {}).get("model") if isinstance(retry, dict) else "",
            "context": (retry or {}).get("context") if isinstance(retry, dict) else {},
            "thought": "AI 沒有產生可執行的實體生成指令，因此本輪不宣告場景成功。",
            "error": "missing_executable_spawn",
        }

    _admin._admin_model_command = reliable_admin_model_command
