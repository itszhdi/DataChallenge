from fastapi import APIRouter, Request

from src.features.checklists.router import router as checklists_router
from src.features.conversations.router import router as conversations_router
from src.features.datasets.router import router as datasets_router

api_router = APIRouter(prefix="/api")
api_router.include_router(datasets_router)
api_router.include_router(conversations_router)
api_router.include_router(checklists_router)


@api_router.get("/health", tags=["system"])
async def health(request: Request) -> dict:
    settings = request.state.settings
    return {"status": "ok", "provider": settings.llm_provider, "model": settings.llm_model}
