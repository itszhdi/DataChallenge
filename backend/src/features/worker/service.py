# ** Авто-воркер: фоновая задача lifespan, в авторежиме по одному берёт неоценённые диалоги в заданном порядке
import asyncio
import logging
from typing import AsyncIterator

from fastapi import HTTPException

from src import db
from src.config.settings import get_settings
from src.features.evaluation import jobs
from src.features.evaluation.service import SKIP_ERRORS, evaluate_conversation, tracked
from src.features.settings.service import load_app_settings as load_settings
from src.features.worker import state
from src.llm.client import LLMRegistry

logger = logging.getLogger(__name__)


async def ticks(interval: float) -> AsyncIterator[None]:
    while True:
        yield
        await asyncio.sleep(interval)


def next_candidate() -> dict | None:
    s = load_settings()
    found = db.auto_candidates(s.queue_sort, s.auto_dataset, get_settings().exclude_channels, limit=1, calls=s.auto_calls)
    return found[0] if found else None


async def step(registry: LLMRegistry) -> None:
    settings = await asyncio.to_thread(load_settings)
    if not settings.auto_mode:
        state.update(mode="manual", status="idle", reason="ручной режим", current=None)
        return
    if jobs.has_running():
        # * Ручной пакет уже расходует лимиты модели — ждём его окончания
        state.update(mode="auto", status="paused", reason="идёт пакетная оценка", current=None)
        return
    candidate = await asyncio.to_thread(next_candidate)
    if not candidate:
        state.update(mode="auto", status="idle", reason="нет новых диалогов", current=None)
        return

    llm = registry.active()
    cid = candidate["id"]
    state.update(mode="auto", status="running", reason="", current=cid)
    logger.info("Auto worker: evaluating %s (sort=%s, model=%s)", cid, settings.queue_sort, llm.model)
    try:
        await tracked(llm, cid, evaluate_conversation, "auto")
        state.state["processed"] += 1
    except SKIP_ERRORS as e:
        logger.info("Auto worker: %s skipped: %s", cid, getattr(e, "detail", e))
    except HTTPException as e:
        # ! Упавший диалог остаётся failed: воркер его не повторяет, только ручной Retry
        state.state["failed"] += 1
        state.update(last_error=f"{cid}: {e.detail}")
        logger.warning("Auto worker: %s failed: %s", cid, e.detail)
    finally:
        state.update(current=None)


async def run(registry: LLMRegistry) -> None:
    state.update(alive=True)
    logger.info("Auto worker started, interval=%.1fs", get_settings().worker_interval_sec)
    try:
        async for _ in ticks(get_settings().worker_interval_sec):
            try:
                await step(registry)
            except Exception as e:
                # ! Воркер не должен умирать из-за одного сбоя (БД занята, неожиданный ответ и т.п.)
                logger.exception("Auto worker step crashed")
                state.update(status="error", last_error=f"{type(e).__name__}: {e}", current=None)
    finally:
        state.update(alive=False, current=None)
        logger.info("Auto worker stopped")
