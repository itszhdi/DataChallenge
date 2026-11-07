from fastapi import APIRouter, Request

from src.features.analytics.router import router as analytics_router
from src.features.appeals.router import router as appeals_router
from src.features.audio.router import router as audio_router
from src.features.checklists.router import router as checklists_router
from src.features.conversations.router import router as conversations_router
from src.features.datasets.router import router as datasets_router
from src.features.evaluation.router import router as evaluation_router
from src.features.export.router import router as export_router
from src.features.settings.router import router as settings_router
from src.features.worker.router import router as worker_router

api_router = APIRouter(prefix="/api")
api_router.include_router(datasets_router)
api_router.include_router(conversations_router)
api_router.include_router(checklists_router)
api_router.include_router(evaluation_router)
api_router.include_router(appeals_router)
api_router.include_router(analytics_router)
api_router.include_router(export_router)
api_router.include_router(audio_router)
api_router.include_router(settings_router)
api_router.include_router(worker_router)


@api_router.get("/health", tags=["system"])
async def health(request: Request) -> dict:
    llm = request.state.llm.active()
    return {"status": "ok", "profile": llm.profile.name, "provider": llm.provider, "model": llm.model}
