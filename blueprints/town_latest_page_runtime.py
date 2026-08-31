"""Exact current CUSTOMS AGENT TOWN browser snapshot.

The App Block changes quickly during visual development. To keep Render serving
that exact build without a fragile chain of legacy HTML patches, the compressed
HTML payload is stored in small repository chunks and reconstructed at request
time. Tiny current-version hotfixes can be applied after reconstruction.
"""

import base64
import gzip
import re
from pathlib import Path


_CHUNK_DIR = Path(__file__).with_name("town_latest_chunks")
_CHUNK_COUNT = 9
_LEGACY_CHARACTER_SLOTS = ("MIA", "ANA", "LIA")


def _apply_tidb_character_slots(html: str) -> str:
    """Map the three legacy browser sprite slots to current TiDB characters.

    The compressed browser snapshot predates TiDB-owned character identity and
    still refers to its original three sprite slots internally. Keep those
    slots as a presentation compatibility detail only: runtime character names
    and display names come from town_characters, not from this file.
    """
    try:
        from .town_character_tidb_runtime import character_context
        rows = character_context()
    except Exception:
        rows = []
    if not rows:
        return html

    for index, legacy_id in enumerate(_LEGACY_CHARACTER_SLOTS):
        if index >= len(rows):
            break
        row = rows[index] if isinstance(rows[index], dict) else {}
        current_id = str(row.get("id") or "").strip().upper()
        if not current_id:
            continue
        # Use word boundaries so text such as "familia" is never damaged by
        # replacing the legacy LIA slot token.
        html = re.sub(rf"\b{re.escape(legacy_id)}\b", current_id, html)
    return html


def latest_town_html():
    payload = "".join(
        (_CHUNK_DIR / f"{index:02d}.txt").read_text(encoding="utf-8").strip()
        for index in range(1, _CHUNK_COUNT + 1)
    )
    html = gzip.decompress(base64.b64decode(payload)).decode("utf-8")
    # v119: execute the returned ephemeral actions (movement/chat/dogs/etc.) even
    # when the server-authoritative world endpoint is available, then reconcile
    # persistent state from /api/town/world.
    html = html.replace(
        "      const synced=await pullTownWorld();\n      if(!synced)applyAiTownActions(data?.actions||[]);",
        "      applyAiTownActions(data?.actions||[]);\n      await pullTownWorld();",
    )
    # Character identity is owned by TiDB. The legacy snapshot keeps only three
    # drawing slots; their visible/runtime IDs are rebound on every page build.
    html = _apply_tidb_character_slots(html)
    return html
