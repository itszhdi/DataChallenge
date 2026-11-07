import asyncio

from fastapi import APIRouter, HTTPException, status

from src import db
from src.features.evaluation.service import list_conversations_with_scores
from src.features.evaluation.timing import with_offsets

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(dataset: str | None = None) -> list[dict]:
    return await asyncio.to_thread(list_conversations_with_scores, dataset)


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str) -> dict:
    conv = await asyncio.to_thread(db.get_conversation, conversation_id)
    if not conv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Диалог не найден")
    conv["transcript"] = with_offsets(conv["transcript"])
    evaluations = await asyncio.to_thread(db.list_evaluations, conversation_id)
    conv["evaluations"] = [{k: e[k] for k in ("id", "checklist_id", "parent_id", "created_at", "meta")} for e in evaluations]
    return conv
