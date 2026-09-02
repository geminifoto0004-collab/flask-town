"""Project permanent TiDB colleagues beyond the three native slots into /world.

The historical browser renderer owns exactly three native officer sprites. The
server-side character table can contain any number of active core colleagues.
For presentation only, every /api/town/world response gets synthetic generic
human entities for colleagues after the first three. Nothing is written back to
TiDB world state by this projection.
"""

from __future__ import annotations

import json

from flask import request

from .town_character_tidb_runtime import character_context


def _entity_for(row, index):
    colleague_id = str(row.get("id") or "").strip().upper()[:64]
    if not colleague_id:
        return None
    col = index % 4
    line = index // 4
    return {
        "id": colleague_id,
        "name": str(row.get("name") or colleague_id).strip()[:64],
        "entityType": "human",
        "zone": "office",
        "x": float(135 + col * 115),
        "y": float(220 + line * 42),
        "bodyColor": "#536f86",
        "accentColor": "#d4a74a",
        "carrying": [],
        "script": [],
        "permanentColleague": True,
        "characterProfile": {
            "gender": row.get("gender") or "",
            "birthYear": row.get("birthYear"),
            "careerState": row.get("careerState") or "active",
            "workStyle": row.get("workStyle") or "",
        },
    }


def install_colleague_world_projection(app):
    if getattr(app, "_town_colleague_world_projection", False):
        return True

    @app.after_request
    def project_colleagues(response):
        if request.path != "/api/town/world" or response.status_code >= 400 or not response.is_json:
            return response
        try:
            data = response.get_json(silent=True)
            if not isinstance(data, dict):
                return response
            world = data.get("world")
            if not isinstance(world, dict):
                return response

            rows = character_context()
            extras = []
            for index, row in enumerate(rows[3:]):
                if not isinstance(row, dict):
                    continue
                entity = _entity_for(row, index)
                if entity:
                    extras.append(entity)

            existing = [dict(v) for v in world.get("genericEntities", []) if isinstance(v, dict)] if isinstance(world.get("genericEntities"), list) else []
            existing_ids = {str(v.get("id") or "").upper() for v in existing}
            for entity in extras:
                if str(entity.get("id") or "").upper() not in existing_ids:
                    existing.append(entity)
                    existing_ids.add(str(entity.get("id") or "").upper())

            world["genericEntities"] = existing
            data["world"] = world
            data["colleague_projection_count"] = len(extras)
            data["colleague_projection_ids"] = [v["id"] for v in extras]
            response.set_data(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
            response.content_type = "application/json; charset=utf-8"
        except Exception as exc:
            response.headers["X-Town-Colleague-Projection-Error"] = str(exc)[:120]
        return response

    app._town_colleague_world_projection = True
    return True
