# * Записи звонков у организаторов: audio_url отдаёт HTML-страницу с <source src> на файл в Dynamics (подпись ~1 час)
import html
import logging
import re
import time
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

SOURCE_RE = re.compile(r"<(?:source|audio)[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE)
# ** Кэшируем найденную ссылку на файл меньше срока её подписи, чтобы перемотка не дёргала страницу каждый раз
CACHE_TTL_SEC = 30 * 60
ALLOWED_MEDIA_SUFFIXES = (".dynamics.com", ".powerplatform.com", ".blob.core.windows.net")

_cache: dict[str, tuple[float, str]] = {}


class AudioError(Exception):
    pass


def _is_allowed(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and any((parsed.hostname or "").endswith(s) for s in ALLOWED_MEDIA_SUFFIXES)


async def resolve_media_url(client: httpx.AsyncClient, page_url: str) -> str:
    cached = _cache.get(page_url)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    if not _is_allowed(page_url):
        raise AudioError("адрес записи не из доверенного домена")

    resp = await client.get(page_url)
    resp.raise_for_status()
    ctype = resp.headers.get("content-type", "")
    if ctype.startswith("audio/"):
        media = page_url
    else:
        match = SOURCE_RE.search(resp.text)
        if not match:
            logger.error("Audio page has no <source>: content-type=%s", ctype)
            raise AudioError("на странице записи нет ссылки на аудио")
        media = html.unescape(match.group(1))
    if not _is_allowed(media):
        raise AudioError("ссылка на аудио ведёт на недоверенный домен")
    _cache[page_url] = (time.monotonic() + CACHE_TTL_SEC, media)
    return media


def forget(page_url: str) -> None:
    _cache.pop(page_url, None)
