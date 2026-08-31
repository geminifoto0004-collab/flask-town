"""Final officer validation using the current TiDB-defined character IDs."""

from . import town_ai_bp as _base
from .town_character_tidb_runtime import character_id_set, refresh_runtime_character_bindings


def install_character_validation_patch():
    previous = _base._validate_actions

    def validate(raw_actions):
        refresh_runtime_character_bindings()
        ids = character_id_set()
        if not isinstance(raw_actions, list):
            return []
        output = []
        for item in raw_actions:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("type") or "")
            if kind == "agent_chat":
                a = str(item.get("from") or item.get("agent") or "").upper()
                b = str(item.get("to") or item.get("target") or "").upper()
                if a not in ids or b not in ids or a == b:
                    continue
                turns = []
                for index, turn in enumerate(item.get("turns") if isinstance(item.get("turns"), list) else []):
                    if not isinstance(turn, dict):
                        continue
                    speaker = str(turn.get("speaker") or turn.get("from") or (a if index % 2 == 0 else b)).upper()
                    text = str(turn.get("text") or turn.get("message") or "").strip()[:160]
                    text_zh = str(turn.get("text_zh") or turn.get("textZh") or turn.get("translation_zh") or "").strip()[:160]
                    if speaker in {a, b} and text:
                        row = {"speaker": speaker, "text": text}
                        if text_zh:
                            row["text_zh"] = text_zh
                        turns.append(row)
                    if len(turns) >= 12:
                        break
                if turns:
                    output.append({"type": "agent_chat", "from": a, "to": b, "turns": turns})
                continue
            if kind == "agent_say":
                agent = str(item.get("agent") or "").upper()
                text = str(item.get("text") or item.get("message") or "").strip()[:160]
                text_zh = str(item.get("text_zh") or item.get("textZh") or item.get("translation_zh") or "").strip()[:160]
                if agent in ids and text:
                    row = {"type": "agent_say", "agent": agent, "text": text}
                    if text_zh:
                        row["text_zh"] = text_zh
                    output.append(row)
                continue
            output.extend(previous([item]))
            if len(output) >= 32:
                break
        return output[:32]

    _base._validate_actions = validate
