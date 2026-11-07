import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, TypedDict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src import db
from src.config.settings import Settings, get_settings
from src.features.settings.service import load as load_app_settings
from src.features.transcription.service import configure as configure_transcriber
from src.features.worker.service import run as run_worker
from src.llm.client import LLMRegistry
from src.router import api_router


class State(TypedDict):
    settings: Settings
    llm: LLMRegistry


def setup_logging(level: str) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # ** httpx на INFO печатает полный URL запроса, а в URL датасета секретная подпись
    logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings = get_settings()
    setup_logging(settings.log_level)
    await asyncio.to_thread(db.init_db)
    await asyncio.to_thread(db.seed_default_checklist, settings.default_checklist_path)
    stale = await asyncio.to_thread(db.reset_stale_statuses)
    app_settings = await asyncio.to_thread(load_app_settings)
    llm = LLMRegistry(settings, app_settings.llm_profile)
    configure_transcriber(llm.transcriber)
    logger = logging.getLogger(__name__)
    logger.info("CQA started: profile=%s model=%s auto_mode=%s", llm.active_name, llm.active().model, app_settings.auto_mode)
    if stale:
        logger.warning("Marked %d interrupted analyses as failed after restart", stale)
    worker = asyncio.create_task(run_worker(llm), name="auto-worker")
    try:
        yield {"settings": settings, "llm": llm}
    finally:
        worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker
        await llm.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="CQA", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"]
    )
    app.include_router(api_router)
    return app


app = create_app()
