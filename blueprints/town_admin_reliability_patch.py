"""Reliability guard for manual/admin town directing.

Keep manual commands fast by reading already-persisted public context instead of
blocking on external news/weather refreshes, and prevent arrival/appearance
instructions from succeeding as prose without executable spawn actions.

IMPORTANT: this guard never performs a second DeepSeek call inside the same HTTP
request. If the model fails the executable audit, fail fast so Render/gunicorn
cannot be held open by two back-to-back model calls.
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
    markers = (
        "來了", "来了", "來一", "来一", "出現", "出现", "進來", "进来", "到訪", "到访",
        "arrive", "arrived", "comes", "come in", "appear", "appears", "visit", "visits",
        "llega", "llegan", "aparece", "aparecen", "visita", "visitan",
    )
    return any(marker in text for marker in markers)


def _has_spawn(actions):
    spawn_types = {
        "spawn_entity", "spawn_from_template", "world_object_spawn",
        "sea_creature_spawn", "dog_visit", "former_visit",
    }
    return any(
        isinstance(action, dict) and str(action.get("type") or "") in spawn_types
        for action in (actions or [])
    )


def install_admin_reliability_patch():
    # Manual commands use the already-persisted snapshot. Background refresh/cron
    # remains responsible for network I/O.
    _director._public_context_for_ai = _stored_public_context_for_ai
    _director.recent_news_for_ai = _stored_recent_news

    previous_system_prompt = _director._system_prompt

    def system_prompt(mode):
        return previous_system_prompt(mode) + """

ARBITRARY WORLD DIRECTION — CORE DESIGN RULE:
- The administrator is allowed to give ANY fictional or realistic world concept. Do not wait for or expect a bespoke Python function for that story.
- You already have a visual/function vocabulary. Decompose the concept yourself into executable actors, objects, movement, speech, interactions and persistent world changes.
- Use world_scene whenever a concept needs multiple new actors and/or several visible environmental objects in one coherent event.
- A large concept is NOT a reason to answer with prose only. Stage the parts that can be represented inside the current town/map. Scale a city/world-level event down to visible local consequences in this Iquique customs-office world while preserving the administrator's requested core idea.
- If an exact visual form is unavailable, approximate it with the available generic entity/template/pixel-object primitives rather than silently dropping the event.
- Do not require the administrator to know tool names. Inferring the best executable representation is YOUR job as director.

EXECUTABLE REPRESENTATION AUDIT — HARD RULES:
- One spawn_entity, spawn_from_template, or entity_scene represents exactly ONE newly created actor/entity. world_scene may contain many actors, but every actor entry still compiles to its own creation action.
- If the administrator explicitly requests N new actors/entities, emit N distinct actor/creation entries with distinct stable ids. Never satisfy quantity only in intentSummary, directorNote, prose, or dialogue.
- A sentence saying somebody arrived/appeared/entered is NOT execution. Every newly appearing person, animal, creature, vehicle, item or decoration must have a corresponding executable creation representation.
- entity_scene is one actor's complete scene. For multiple actors or a broad event, prefer world_scene.
- Before finishing, compare the requested visible facts against your tool calls and add any missing representation IN THIS SAME RESPONSE.
- There will be no second model retry for a missing spawn. The first response must be executable and complete.
"""

    _director._system_prompt = system_prompt

    previous_command = _admin._admin_model_command

    def reliable_admin_model_command(prompt, world):
        result = previous_command(prompt, world)
        actions = result.get("actions") if isinstance(result, dict) else []
        if not (_looks_like_new_entity_request(prompt) and not _has_spawn(actions)):
            return result

        # Fail fast. Do NOT call DeepSeek again in this same request; a second long
        # model call is exactly what caused Render/gunicorn 502s on manual scenes.
        return {
            "ok": False,
            "actions": [],
            "model": (result or {}).get("model") if isinstance(result, dict) else "",
            "context": (result or {}).get("context") if isinstance(result, dict) else {},
            "thought": "AI 沒有產生可執行的實體生成指令，因此本輪不宣告場景成功。",
            "error": "missing_executable_spawn",
        }

    _admin._admin_model_command = reliable_admin_model_command
