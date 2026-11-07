import asyncio
import logging

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from src import db
from src.features.audio.service import AudioError, forget, resolve_media_url

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audio", tags=["audio"])

PASS_HEADERS = ("content-type", "content-length", "content-range", "accept-ranges")


@router.get("/{conversation_id}")
async def stream_audio(conversation_id: str, request: Request) -> StreamingResponse:
    # * Прокси записи: обходит CORS и поддерживает Range, чтобы в плеере работала перемотка к реплике
    conv = await asyncio.to_thread(db.get_conversation, conversation_id)
    if not conv or not conv.get("audio_url"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "У диалога нет записи")

    client = httpx.AsyncClient(timeout=httpx.Timeout(30, read=120), follow_redirects=True)
    headers = {"Range": request.headers["range"]} if "range" in request.headers else {}
    try:
        for attempt in (1, 2):
            media = await resolve_media_url(client, conv["audio_url"])
            upstream = await client.send(client.build_request("GET", media, headers=headers), stream=True)
            # ** Подпись ссылки истекла — сбрасываем кэш и берём свежую ссылку со страницы
            if upstream.status_code in (401, 403) and attempt == 1:
                await upstream.aclose()
                forget(conv["audio_url"])
                continue
            break
        if upstream.status_code >= 400:
            await upstream.aclose()
            raise AudioError(f"источник вернул {upstream.status_code}")
    except (AudioError, httpx.HTTPError) as e:
        await client.aclose()
        logger.error("Audio proxy failed for %s: %s", conversation_id, e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Не удалось получить запись: {e}") from e

    async def close() -> None:
        await upstream.aclose()
        await client.aclose()

    out_headers = {k: v for k, v in upstream.headers.items() if k.lower() in PASS_HEADERS}
    return StreamingResponse(
        upstream.aiter_bytes(), status_code=upstream.status_code, headers=out_headers, background=BackgroundTask(close)
    )
