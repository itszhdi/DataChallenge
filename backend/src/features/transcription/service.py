# ** Свой транскрипт звонка: аудио по audio_url → Gemini → реплики с ролями и временем; оригинал датасета не трогаем
import asyncio
import base64
import logging
import time
from datetime import datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException, status

from src import db
from src.config.settings import get_settings
from src.features.audio.service import AudioError, forget, resolve_media_url
from src.features.evaluation.timing import parse_timestamp
from src.llm.client import LLMClient, LLMError

logger = logging.getLogger(__name__)

SPEAKERS = ["operator", "client", "bot"]
TRANSCRIBE_PROMPT = """Ты — система распознавания речи контакт-центра брокерской компании Freedom (Казахстан).
Транскрибируй запись телефонного звонка ДОСЛОВНО на языке оригинала (русский, казахский, английский или их смесь). Не переводи, не пересказывай, не исправляй речь, только расставь пунктуацию.
Раздели речь на реплики при каждой смене говорящего. Роли:
- bot — автоответчик, голосовое меню (IVR), записанные сообщения («нажмите 1», «ваш звонок важен для нас»);
- operator — сотрудник компании (представляется, консультирует, просит подождать);
- client — клиент, который позвонил.
start — время начала реплики от начала записи в формате MM:SS (или H:MM:SS для длинных записей).
Неразборчивый фрагмент пиши как [неразборчиво]. Музыку, тишину и гудки не записывай. Ничего не додумывай.
Персональные данные маскируй так же, как в датасете банка: ФИО клиента, ИИН, номера документов, счетов, карт и телефонов, адрес, дата рождения — заменяй на [Персональные данные скрыты]; имя сотрудника — на [Имя скрыто]. Сам факт запроса или называния данных сохраняй («Назовите, пожалуйста, ИИН» — оставить, ответ клиента — замаскировать)."""

SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "string"},
                    "speaker": {"type": "string", "enum": SPEAKERS},
                    "text": {"type": "string"},
                },
                "required": ["start", "speaker", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["segments"],
    "additionalProperties": False,
}

AUDIO_FORMATS = {"audio/mpeg": "mp3", "audio/mp3": "mp3", "audio/wav": "wav", "audio/x-wav": "wav", "audio/ogg": "ogg"}


_transcriber: LLMClient | None = None


def configure(client: LLMClient) -> None:
    global _transcriber
    _transcriber = client


def has_dialogue(transcript: list[dict[str, Any]]) -> bool:
    return any(m.get("speaker") != "system" and (m.get("text") or "").strip() for m in transcript or [])


def wants_asr(conversation: dict[str, Any], call_transcript: str) -> bool:
    # * Свой транскрипт — если есть запись и так выбрано в настройках, или если в датасете транскрипта нет вовсе
    if not conversation.get("audio_url"):
        return False
    return call_transcript == "asr" or not has_dialogue(conversation.get("transcript") or [])


async def prepare_transcript(conversation: dict[str, Any], call_transcript: str) -> tuple[list[dict[str, Any]], str]:
    # ** Распознавание выключено (TRANSCRIBE_ENABLED=false): звонок без текста в датасете будет пропущен как неоцениваемый
    if not get_settings().transcribe_enabled or not wants_asr(conversation, call_transcript):
        return conversation.get("transcript") or [], "original"
    if conversation.get("transcript_asr"):
        return conversation["transcript_asr"], "asr"
    if _transcriber is None:
        raise TranscriptionFailed("клиент распознавания не настроен")
    return await transcribe(_transcriber, conversation), "asr"


class TranscriptionDisabled(HTTPException):
    code = "transcription_disabled"

    def __init__(self) -> None:
        super().__init__(status.HTTP_409_CONFLICT, "Распознавание звонков отключено (TRANSCRIBE_ENABLED=false)")


class TranscriptionFailed(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status.HTTP_502_BAD_GATEWAY, f"Не удалось распознать звонок: {detail}")


async def fetch_audio(audio_url: str) -> tuple[bytes, str]:
    # * Подпись ссылки Dynamics живёт ~1 час: при 401/403 один раз берём свежую ссылку со страницы записи
    limit = int(get_settings().transcribe_max_audio_mb * 1024 * 1024)
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        for attempt in (1, 2):
            media = await resolve_media_url(client, audio_url)
            resp = await client.get(media)
            if resp.status_code in (401, 403) and attempt == 1:
                forget(audio_url)
                continue
            resp.raise_for_status()
            if len(resp.content) > limit:
                raise AudioError(f"запись больше {get_settings().transcribe_max_audio_mb:.0f} МБ")
            ctype = resp.headers.get("content-type", "audio/mpeg").split(";")[0].strip()
            return resp.content, AUDIO_FORMATS.get(ctype, "mp3")
    raise AudioError("ссылка на запись не открывается")


# * События записи в Dynamics: аудиофайл начинается с «запущены», паузы вырезаны из файла
RECORD_START = ("запись и транскрибирование запущены", "recording and transcription started", "recording started", "жазба басталды")
RECORD_PAUSE = ("запись и транскрибирование приостановлены", "recording paused", "recording and transcription paused")
RECORD_RESUME = ("запись и транскрибирование возобновлены", "recording resumed", "recording and transcription resumed")


def _has(msg: dict[str, Any], patterns: tuple[str, ...]) -> bool:
    text = (msg.get("text") or "").lower()
    return msg.get("speaker") == "system" and any(p in text for p in patterns)


def _iso_base(original: list[dict[str, Any]]) -> datetime | None:
    ts = next((m.get("timestamp") for m in original if parse_timestamp(m.get("timestamp")) is not None), None) or ""
    if "T" not in ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def to_transcript(segments: list[dict[str, Any]], original: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # ** Время аудио → время звонка: 0 аудио = событие «запись запущена», паузы записи сдвигают всё, что после них
    timed = [(parse_timestamp(m.get("timestamp")), m) for m in original]
    known = [t for t, _ in timed if t is not None]
    t0 = known[0] if known else 0.0
    rec_start = next((t for t, m in timed if t is not None and _has(m, RECORD_START)), t0)
    pauses, paused_at = [], None
    for t, m in timed:
        if t is None or t < rec_start:
            continue
        if _has(m, RECORD_PAUSE) and paused_at is None:
            paused_at = t
        elif _has(m, RECORD_RESUME) and paused_at is not None:
            pauses.append((paused_at, t))
            paused_at = None

    def real(offset: float) -> float:
        t = rec_start + offset
        for p, r in pauses:
            if t >= p:
                t += r - p
        return t

    base = _iso_base(original)

    def stamp(abs_t: float) -> str:
        if base:
            return (base + timedelta(seconds=abs_t - t0)).isoformat()
        rel = int(max(abs_t - t0, 0))
        return f"{rel // 60:02d}:{rel % 60:02d}"

    out: list[tuple[float, int, dict[str, Any]]] = []
    for i, seg in enumerate(segments):
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        speaker = seg.get("speaker") if seg.get("speaker") in SPEAKERS else "unknown"
        abs_t = real(parse_timestamp(seg.get("start")) or 0.0)
        msg = {"timestamp": stamp(abs_t), "speaker": speaker, "text": text, "asr": True}
        if speaker == "unknown":
            msg["speaker_raw"] = str(seg.get("speaker"))
        out.append((abs_t, i, msg))

    # ** Из оригинала берём системные события и реплики ДО начала записи (приветствие оператора в файл не попадает)
    for j, (t, m) in enumerate(timed):
        pre_recording = t is not None and t < rec_start and m.get("speaker") != "system"
        if m.get("speaker") == "system" or pre_recording:
            item = {**m, "asr": False}
            if pre_recording:
                item["pre_recording"] = True
            out.append((t if t is not None else float("inf"), -1_000_000 + j, item))
    out.sort(key=lambda x: (x[0], x[1]))
    return [m for _, _, m in out]


async def transcribe(transcriber: LLMClient, conversation: dict[str, Any]) -> list[dict[str, Any]]:
    cid = conversation["id"]
    if not conversation.get("audio_url"):
        raise TranscriptionFailed("у диалога нет audio_url")
    started = time.monotonic()
    try:
        audio, fmt = await fetch_audio(conversation["audio_url"])
    except (AudioError, httpx.HTTPError) as e:
        logger.error("Audio download failed for %s: %s", cid, e)
        raise TranscriptionFailed(f"запись не скачалась ({e})") from e

    messages = [
        {"role": "system", "content": TRANSCRIBE_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": f"Язык клиента по метке датасета: {conversation.get('language') or '?'}. Запись звонка:"},
            {"type": "input_audio", "input_audio": {"data": base64.b64encode(audio).decode(), "format": fmt}},
        ]},
    ]
    logger.info("Transcribing %s: %.1f MB %s via %s", cid, len(audio) / 1e6, fmt, transcriber.model)
    try:
        raw, meta = await transcriber.complete_json(messages, SCHEMA)
    except LLMError as e:
        logger.error("Transcription failed for %s: %s", cid, e)
        raise TranscriptionFailed(str(e)) from e

    segments = raw.get("segments") if isinstance(raw.get("segments"), list) else []
    transcript = to_transcript([s for s in segments if isinstance(s, dict)], conversation.get("transcript") or [])
    if not any(m["asr"] for m in transcript):
        raise TranscriptionFailed("модель не вернула ни одной реплики")
    asr_meta = {
        "model": transcriber.model, "seconds": round(time.monotonic() - started, 1), "audio_bytes": len(audio),
        "segments": len(segments), "tokens": meta.get("tokens"), "cost_usd": meta.get("cost_usd"),
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    await asyncio.to_thread(db.set_transcript_asr, cid, transcript, asr_meta)
    logger.info("Transcribed %s: %d segments in %.1fs", cid, len(segments), asr_meta["seconds"])
    return transcript
