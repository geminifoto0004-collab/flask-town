"""Persistent current-world context for CUSTOMS AGENT TOWN.

Fresh public information is collected independently from DeepSeek, persisted in
TiDB, and reused by every AI conversation/director call. The feed deliberately
covers local, national, Latin-American and world news so Iquique is the setting,
not the characters' entire conversational universe.
"""

from __future__ import annotations

import json
import os
import threading
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests
from flask import jsonify, request

from database import execute_sql, get_db_connection

_REFRESH_SECONDS = 15 * 60
_THREAD_STARTED = False
_THREAD_LOCK = threading.Lock()
_REFRESH_LOCK = threading.Lock()


def _close(conn):
    try:
        conn.close()
    except Exception:
        pass


def ensure_current_context_table():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        execute_sql(cur, """
            CREATE TABLE IF NOT EXISTS town_current_context (
                context_key VARCHAR(64) PRIMARY KEY,
                payload_json MEDIUMTEXT NOT NULL,
                updated_at_ms BIGINT NOT NULL
            )
        """)
        conn.commit()
    finally:
        _close(conn)


def _read_stored():
    ensure_current_context_table()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        execute_sql(cur, "SELECT payload_json, updated_at_ms FROM town_current_context WHERE context_key = ?", ("main",))
        row = cur.fetchone()
        if not row:
            return {}
        raw = row.get("payload_json") if isinstance(row, dict) else row[0]
        updated = row.get("updated_at_ms") if isinstance(row, dict) else row[1]
        data = json.loads(raw or "{}")
        if not isinstance(data, dict):
            data = {}
        data["updated_at_ms"] = int(updated or data.get("updated_at_ms") or 0)
        return data
    finally:
        _close(conn)


def _write_stored(payload):
    now_ms = int(time.time() * 1000)
    data = dict(payload or {})
    data["updated_at_ms"] = now_ms
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    ensure_current_context_table()
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        execute_sql(cur, """
            INSERT INTO town_current_context (context_key, payload_json, updated_at_ms)
            VALUES (?, ?, ?)
            ON DUPLICATE KEY UPDATE
              payload_json = VALUES(payload_json),
              updated_at_ms = VALUES(updated_at_ms)
        """, ("main", raw, now_ms))
        conn.commit()
    finally:
        _close(conn)
    return data


def _rss_query(query, category, limit=5):
    response = requests.get(
        "https://news.google.com/rss/search",
        params={"q": query, "hl": "es-419", "gl": "CL", "ceid": "CL:es-419"},
        headers={"User-Agent": "Mozilla/5.0 CUSTOMS-AGENT-TOWN/1.0"},
        timeout=(3.5, 7),
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)
    items = []
    for node in root.findall("./channel/item")[:limit]:
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        published = (node.findtext("pubDate") or "").strip()
        source_node = node.find("source")
        source = ((source_node.text if source_node is not None else "") or "").strip()
        if not title:
            continue
        published_ms = 0
        try:
            published_ms = int(parsedate_to_datetime(published).timestamp() * 1000)
        except Exception:
            pass
        items.append({
            "category": category,
            "title": title[:220],
            "source": source[:80],
            "published": published[:60],
            "published_at_ms": published_ms,
            "url": link[:700],
        })
    return items


def _weather():
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": -20.2307,
            "longitude": -70.1357,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
            "timezone": "America/Santiago",
        },
        timeout=(3.5, 7),
    )
    response.raise_for_status()
    current = (response.json() or {}).get("current") or {}
    return {
        "time": str(current.get("time") or "")[:40],
        "temperature_c": current.get("temperature_2m"),
        "apparent_temperature_c": current.get("apparent_temperature"),
        "humidity_pct": current.get("relative_humidity_2m"),
        "precipitation_mm": current.get("precipitation"),
        "weather_code": current.get("weather_code"),
        "wind_speed_kmh": current.get("wind_speed_10m"),
        "source": "Open-Meteo",
    }


def refresh_current_context(force=False):
    """Refresh public context and persist it. Stale stored data survives failures."""
    with _REFRESH_LOCK:
        stored = {}
        try:
            stored = _read_stored()
        except Exception:
            stored = {}
        age = int(time.time() * 1000) - int(stored.get("updated_at_ms") or 0)
        if not force and stored and age < _REFRESH_SECONDS * 1000:
            return stored

        news = []
        errors = []
        queries = (
            ("Iquique OR Tarapacá", "iquique_tarapaça"),
            ("Chile noticias", "chile"),
            ("América Latina noticias", "latin_america"),
            ("mundo noticias internacionales", "world"),
            ("Iquique puerto OR ZOFRI OR aduana OR comercio exterior", "puerto_zofri_aduana"),
        )
        for query, category in queries:
            try:
                news.extend(_rss_query(query, category, limit=5))
            except Exception as exc:
                errors.append(f"news:{category}:{str(exc)[:100]}")

        # De-duplicate the same headline returned by several queries while
        # keeping a wider pool for category-balanced selection later.
        deduped = []
        seen = set()
        for item in sorted(news, key=lambda x: int(x.get("published_at_ms") or 0), reverse=True):
            key = str(item.get("title") or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= 24:
                break

        weather = {}
        try:
            weather = _weather()
        except Exception as exc:
            errors.append("weather:" + str(exc)[:100])

        if not deduped and not weather:
            if stored:
                return stored
            raise RuntimeError("current context refresh failed: " + "; ".join(errors)[:300])

        payload = {
            "fetched_at_ms": int(time.time() * 1000),
            "location": "Iquique, Chile",
            "news": deduped if deduped else list(stored.get("news") or []),
            "weather": weather if weather else dict(stored.get("weather") or {}),
            "sources": ["Google News RSS", "Open-Meteo"],
            "errors": errors[-6:],
        }
        return _write_stored(payload)


def current_context(refresh_if_stale=True):
    try:
        stored = _read_stored()
    except Exception:
        stored = {}
    if refresh_if_stale:
        age = int(time.time() * 1000) - int(stored.get("updated_at_ms") or 0)
        if not stored or age >= _REFRESH_SECONDS * 1000:
            try:
                return refresh_current_context(force=True)
            except Exception:
                pass
    return stored


def recent_news_for_ai(limit=10):
    """Return recent headlines balanced across categories, not just top-N local."""
    ctx = current_context(refresh_if_stale=True)
    rows = [item for item in (ctx.get("news") or []) if isinstance(item, dict) and item.get("title")]
    if not rows:
        return []

    categories = []
    buckets = {}
    for item in rows:
        category = str(item.get("category") or "other")[:40]
        if category not in buckets:
            buckets[category] = []
            categories.append(category)
        buckets[category].append(item)

    picked = []
    target = max(1, int(limit))
    cursor = 0
    while len(picked) < target and categories:
        category = categories[cursor % len(categories)]
        bucket = buckets.get(category) or []
        if bucket:
            item = bucket.pop(0)
            picked.append({
                "title": str(item.get("title") or "")[:220],
                "source": str(item.get("source") or "")[:80],
                "published": str(item.get("published") or "")[:60],
                "category": category,
            })
        if not bucket:
            categories = [c for c in categories if buckets.get(c)]
            cursor = 0
        else:
            cursor += 1
        if not categories:
            break
    return picked[:target]


def _background_loop():
    time.sleep(3)
    while True:
        try:
            refresh_current_context(force=False)
        except Exception:
            pass
        time.sleep(_REFRESH_SECONDS)


def start_current_context_background_refresh():
    global _THREAD_STARTED
    with _THREAD_LOCK:
        if _THREAD_STARTED:
            return
        _THREAD_STARTED = True
        threading.Thread(target=_background_loop, name="town-current-context", daemon=True).start()


def install_current_context_runtime(town_ai_bp):
    start_current_context_background_refresh()

    @town_ai_bp.route("/current-context", methods=["GET"])
    def get_current_context_api():
        data = current_context(refresh_if_stale=False)
        return jsonify({"ok": True, "context": data})

    @town_ai_bp.route("/current-context/refresh", methods=["POST"])
    def refresh_current_context_api():
        expected = (os.environ.get("TOWN_CRON_TOKEN") or "").strip()
        auth = (request.headers.get("Authorization") or "").strip()
        supplied = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        if not supplied:
            supplied = (request.args.get("token") or "").strip()
        if not expected or supplied != expected:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        try:
            data = refresh_current_context(force=True)
            return jsonify({"ok": True, "context": data})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)[:300]}), 500
