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


def timing_facts(transcript: list[dict[str, Any]], threshold_sec: int = 180) -> dict[str, Any]:
    # * Факты для модели: первая реакция оператора и долгие паузы клиент→оператор
    msgs = with_offsets(transcript)
    first_client = next((m for m in msgs if m["speaker"] == "client"), None)
    first_reply = None
    if first_client:
        first_reply = next((m for m in msgs if m["speaker"] == "operator" and m["index"] > first_client["index"]), None)

    first_delay = None
    if first_client and first_reply and None not in (first_client["offset_sec"], first_reply["offset_sec"]):
        first_delay = round(first_reply["offset_sec"] - first_client["offset_sec"], 1)

    # ** Пауза считается от самой ранней неотвеченной реплики клиента до следующего ответа оператора
    long_pauses = []
    pending = None
    for m in msgs:
        if m["speaker"] == "client" and pending is None:
            pending = m
        elif m["speaker"] == "operator" and pending is not None:
            if None not in (m["offset_sec"], pending["offset_sec"]):
                gap = round(m["offset_sec"] - pending["offset_sec"], 1)
                if gap > threshold_sec:
                    long_pauses.append({"client_index": pending["index"], "operator_index": m["index"], "seconds": gap})
            pending = None

    return {
        "threshold_sec": threshold_sec,
        "first_client_index": first_client["index"] if first_client else None,
        "first_operator_reply_index": first_reply["index"] if first_reply else None,
        "first_response_sec": first_delay,
        "first_response_exceeded": first_delay is not None and first_delay > threshold_sec,
        "long_pauses": long_pauses,
        "duration_sec": msgs[-1]["offset_sec"] if msgs else None,
    }
