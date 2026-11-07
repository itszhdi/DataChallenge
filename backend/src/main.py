import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, TypedDict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src import db
from src.config.settings import Settings, get_settings
from src.features.settings.service import apply_app_settings, load_app_settings
from src.llm.client import LLMClient
from src.router import api_router


class State(TypedDict):
    settings: Settings
    llm: LLMClient


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
    logging.getLogger(__name__).info("CQA started: provider=%s model=%s", settings.llm_provider, settings.llm_model)
    llm = LLMClient(settings)
    apply_app_settings(llm, await asyncio.to_thread(load_app_settings))
    try:
        yield {"settings": settings, "llm": llm}
    finally:
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
