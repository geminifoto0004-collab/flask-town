"""Authoritative TiDB world storage for CUSTOMS AGENT TOWN.

The shared world has exactly one source of truth: TiDB. Local JSON remains
available for unrelated runtime files, but the world snapshot never falls back
to local disk. A very short in-process read cache coalesces duplicate browser
polls without changing TiDB authority.
"""

import copy
import json
import time

from flask import jsonify

from database import execute_sql, get_db_connection
from . import town_ai_bp as _base

_ORIGINAL_READ_JSON = _base._read_json
_ORIGINAL_WRITE_JSON = _base._write_json
_SCHEMA_READY = False
_SCHEMA_RETRY_AT = 0.0
_LAST_ERROR = ""
_READ_CACHE_SECONDS = 1.5
_READ_CACHE = {"at": 0.0, "data": None}


def _close(conn):
    try:
        conn.close()
    except Exception:
        pass


def _set_error(exc):
    global _LAST_ERROR
    _LAST_ERROR = str(exc or "database unavailable")[:300]


def _ensure_schema(force=False):
    global _SCHEMA_READY, _SCHEMA_RETRY_AT, _LAST_ERROR
    now = time.time()
    if _SCHEMA_READY:
        return True
    if not force and now < _SCHEMA_RETRY_AT:
        return False
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        execute_sql(cur, """
            CREATE TABLE IF NOT EXISTS town_world_state (
                state_key VARCHAR(64) PRIMARY KEY,
                payload_json TEXT NOT NULL,
                updated_at_ms BIGINT NOT NULL
            )
        """)
        conn.commit()
        _SCHEMA_READY = True
        _LAST_ERROR = ""
        return True
    except Exception as exc:
        _set_error(exc)
        _SCHEMA_RETRY_AT = now + 30
        return False
    finally:
        if conn is not None:
            _close(conn)


def _db_read_world(default=None):
    """Return (ok, data). ok=False means DB failure; empty row is still ok."""
    global _LAST_ERROR
    fallback = default if isinstance(default, dict) else {}
    if not _ensure_schema():
        return False, dict(fallback)
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        execute_sql(cur, "SELECT payload_json FROM town_world_state WHERE state_key = ?", ("main",))
        row = cur.fetchone()
        if not row:
            _LAST_ERROR = ""
            return True, dict(fallback)
        raw = row.get("payload_json") if isinstance(row, dict) else row[0]
        data = json.loads(raw or "{}")
        _LAST_ERROR = ""
        return True, data if isinstance(data, dict) else dict(fallback)
    except Exception as exc:
        _set_error(exc)
        return False, dict(fallback)
    finally:
        if conn is not None:
            _close(conn)


def _db_write_world(data):
    """Atomically upsert the current snapshot. Never write a local fallback."""
    global _LAST_ERROR
    if not _ensure_schema():
        return False
    payload = json.dumps(data if isinstance(data, dict) else {}, ensure_ascii=False, separators=(",", ":"))
    now_ms = int(time.time() * 1000)
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        execute_sql(cur, """
            INSERT INTO town_world_state (state_key, payload_json, updated_at_ms)
            VALUES (?, ?, ?)
            ON DUPLICATE KEY UPDATE
              payload_json = VALUES(payload_json),
              updated_at_ms = VALUES(updated_at_ms)
        """, ("main", payload, now_ms))
        conn.commit()
        _LAST_ERROR = ""
        return True
    except Exception as exc:
        _set_error(exc)
        try:
            if conn is not None:
                conn.rollback()
        except Exception:
            pass
        return False
    finally:
        if conn is not None:
            _close(conn)


def _world_profiles(payload):
    world = payload.get("world") if isinstance(payload, dict) and isinstance(payload.get("world"), dict) else {}
    profiles = world.get("characterProfiles") if isinstance(world.get("characterProfiles"), list) else []
    result = []
    for item in profiles:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").upper()
        profile = item.get("profile") if isinstance(item.get("profile"), dict) else {}
        if name:
            result.append({"name": name, "profile": profile})
    return result


def install_tidb_world_runtime():
    _ensure_schema()

    def read_json(path, default=None):
        if path == _base._WORLD_PATH:
            now = time.monotonic()
            cached = _READ_CACHE.get("data")
            if cached is not None and now - float(_READ_CACHE.get("at") or 0.0) < _READ_CACHE_SECONDS:
                return copy.deepcopy(cached)
            _ok, data = _db_read_world(default)
            if isinstance(data, dict):
                _READ_CACHE["data"] = copy.deepcopy(data)
                _READ_CACHE["at"] = now
            return data
        return _ORIGINAL_READ_JSON(path, default)

    def write_json(path, data):
        if path == _base._WORLD_PATH:
            if not _db_write_world(data):
                raise RuntimeError("TiDB world write failed: " + (_LAST_ERROR or "database unavailable"))
            _READ_CACHE["data"] = copy.deepcopy(data) if isinstance(data, dict) else {}
            _READ_CACHE["at"] = time.monotonic()
            return
        return _ORIGINAL_WRITE_JSON(path, data)

    _base._read_json = read_json
    _base._write_json = write_json

    @_base.town_ai_bp.route("/storage-status", methods=["GET"])
    def town_storage_status():
        ok, stored = _db_read_world({})
        profiles = _world_profiles(stored)
        saved_at = int(stored.get("saved_at") or 0) if isinstance(stored, dict) else 0
        return jsonify({
            "ok": ok,
            "world_storage": "database" if ok else "database_unavailable",
            "world_initialized": bool(stored),
            "world_saved_at": saved_at,
            "profiles": profiles,
            "profile_count": len(profiles),
            "error": "" if ok else _LAST_ERROR,
        }), (200 if ok else 503)
