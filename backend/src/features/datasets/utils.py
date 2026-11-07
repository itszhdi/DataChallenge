# * Нормализация реплик: любые типы и лишние поля (вложения) не роняют импорт и оценку
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

KNOWN_SPEAKERS = {"client", "operator", "bot", "system"}
SPEAKER_ALIASES = {
    "agent": "operator", "оператор": "operator", "customer": "client", "user": "client", "клиент": "client",
    "assistant": "bot", "бот": "bot", "система": "system",
}
BASE_FIELDS = {"timestamp", "speaker", "text"}
MAX_TEXT_CHARS = 4000
MAX_MARKER_CHARS = 120


def _short(value: Any) -> str:
    if isinstance(value, dict):
        # * У вложения обычно есть тип и имя/ссылка — берём их, остальное не нужно модели
        parts = [str(value[k]) for k in ("type", "name", "filename", "file_name", "title", "url") if value.get(k)]
        text = " ".join(parts) or json.dumps(value, ensure_ascii=False)
    elif isinstance(value, list):
        text = "; ".join(_short(v) for v in value)
    else:
        text = str(value)
    return text[:MAX_MARKER_CHARS]


def _text(value: Any) -> tuple[str, list[str]]:
    if value is None:
        return "", []
    if isinstance(value, str):
        return value, []
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value), []
    return "", [_short(value)]


def _timestamp(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # * Число трактуем как секунды от начала диалога
        m, s = divmod(int(value), 60)
        return f"{m:02d}:{s:02d}"
    return None


def normalize_message(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {"speaker": "unknown", "text": raw}
    speaker_raw = str(raw.get("speaker") or "").strip()
    speaker = SPEAKER_ALIASES.get(speaker_raw.lower(), speaker_raw.lower())
    text, attachments = _text(raw.get("text"))
    attachments += [f"{k}: {_short(v)}" for k, v in raw.items() if k not in BASE_FIELDS and v not in (None, "", [], {})]

    text = text.strip()
    if len(text) > MAX_TEXT_CHARS:
        logger.warning("Message text truncated from %d to %d chars", len(text), MAX_TEXT_CHARS)
        text = text[:MAX_TEXT_CHARS] + " […]"
    if attachments:
        text = (text + " " if text else "") + " ".join(f"[вложение: {a}]" for a in attachments)

    msg: dict[str, Any] = {"timestamp": _timestamp(raw.get("timestamp")), "speaker": speaker, "text": text}
    if speaker not in KNOWN_SPEAKERS:
        msg["speaker"] = "unknown"
        msg["speaker_raw"] = speaker_raw or "?"
    if not text:
        msg["empty"] = True
    if attachments:
        msg["attachments"] = attachments
    return msg


def normalize_transcript(raw: list[Any]) -> list[dict[str, Any]]:
    return [normalize_message(m) for m in raw]
