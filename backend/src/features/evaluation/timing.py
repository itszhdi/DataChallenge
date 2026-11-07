# * Время в диалогах: у чатов MM:SS, у звонков ISO 8601. Исходные метки не трогаем, считаем смещения
from datetime import datetime
from typing import Any

SPEAKER_RU = {"operator": "оператор", "client": "клиент", "bot": "бот", "system": "система", "unknown": "неизвестная роль"}


def parse_timestamp(value: str | None) -> float | None:
    # * Возвращает секунды: для MM:SS / HH:MM:SS — от начала, для ISO — epoch
    if not value:
        return None
    value = value.strip()
    if "T" in value or value.count("-") >= 2:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    parts = value.split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    seconds = 0.0
    for n in nums:
        seconds = seconds * 60 + n
    return seconds


def with_offsets(transcript: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # * Добавляет index (1..N, как в промпте) и offset_sec от первой реплики с валидным временем
    raw = [parse_timestamp(m.get("timestamp")) for m in transcript]
    base = next((t for t in raw if t is not None), None)
    out = []
    for i, (msg, t) in enumerate(zip(transcript, raw), start=1):
        offset = round(t - base, 1) if t is not None and base is not None else None
        out.append({**msg, "index": i, "offset_sec": offset})
    return out


def format_offset(seconds: float | None) -> str:
    if seconds is None:
        return "??:??"
    seconds = int(max(seconds, 0))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# * Системные события «диалог передан оператору» на RU/KZ/EN (из реальных данных DEV + типовые формулировки)
JOIN_PATTERNS = (
    "эскалация на оператора", "переведен на оператора", "переведён на оператора", "оператор подключ", "агент присоедин",
    "присоединился к разговору", "операторға жіберілді", "операторға қосылды", "transferred to an agent",
    "transferred to an operator", "agent joined", "operator joined",
)


def is_join_event(msg: dict[str, Any]) -> bool:
    text = (msg.get("text") or "").lower()
    return msg.get("speaker") == "system" and any(p in text for p in JOIN_PATTERNS)


def _gap(later: dict[str, Any], earlier: dict[str, Any]) -> float | None:
    if later["offset_sec"] is None or earlier["offset_sec"] is None:
        return None
    return round(later["offset_sec"] - earlier["offset_sec"], 1)


def timing_facts(transcript: list[dict[str, Any]], threshold_sec: int = 180) -> dict[str, Any]:
    # ** Ожидание оператора считается от его подключения: время общения клиента с ботом — не вина оператора
    msgs = with_offsets(transcript)
    is_op = lambda m: m.get("speaker") == "operator" and (m.get("text") or "").strip()  # noqa: E731
    first_reply = next((m for m in msgs if is_op(m)), None)
    before = msgs[: first_reply["index"] - 1] if first_reply else msgs

    join = next((m for m in before if is_join_event(m)), None)
    anchor, anchor_kind = join, "join"
    if join is None:
        # * Нет события передачи — берём первую реплику клиента после последней реплики бота
        last_bot = max((m["index"] for m in before if m.get("speaker") == "bot"), default=0)
        anchor = next((m for m in before if m.get("speaker") == "client" and m["index"] > last_bot), None)
        anchor_kind = "client"

    first_delay = _gap(first_reply, anchor) if first_reply and anchor else None
    if first_delay is not None and first_delay < 0:
        first_delay = None
    start_index = anchor["index"] if anchor else (first_reply["index"] if first_reply else 1)

    # ** Пауза — от самой ранней неотвеченной реплики клиента до следующего ответа оператора, только после подключения
    long_pauses = []
    pending = None
    for m in msgs:
        if m["index"] < start_index:
            continue
        if m.get("speaker") == "client" and pending is None:
            pending = m
        elif is_op(m) and pending is not None:
            gap = _gap(m, pending)
            if gap is not None and gap > threshold_sec:
                long_pauses.append({"client_index": pending["index"], "operator_index": m["index"], "seconds": gap})
            pending = None

    missing_time = sum(1 for m in msgs if m["offset_sec"] is None)
    return {
        "threshold_sec": threshold_sec,
        "operator_joined_index": join["index"] if join else None,
        "anchor_index": anchor["index"] if anchor else None,
        "anchor_kind": anchor_kind if anchor else None,
        "first_client_index": anchor["index"] if anchor else None,
        "first_operator_reply_index": first_reply["index"] if first_reply else None,
        "first_response_sec": first_delay,
        "first_response_exceeded": first_delay is not None and first_delay > threshold_sec,
        "long_pauses": long_pauses,
        "missing_time": missing_time,
        "duration_sec": next((m["offset_sec"] for m in reversed(msgs) if m["offset_sec"] is not None), None),
    }
