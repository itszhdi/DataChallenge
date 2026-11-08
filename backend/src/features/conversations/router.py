import asyncio

from fastapi import APIRouter, HTTPException, status

from src import db
from src.dependencies import LLMDep, RegistryDep
from src.config.settings import get_settings
from src.features.transcription.service import TranscriptionDisabled, transcribe
from src.features.evaluation.service import list_conversations_with_scores
from src.features.evaluation.timing import with_offsets

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(llm: LLMDep, dataset: str | None = None) -> list[dict]:
    return await asyncio.to_thread(list_conversations_with_scores, dataset, llm)


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str) -> dict:
    conv = await asyncio.to_thread(db.get_conversation, conversation_id)
    if not conv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Диалог не найден")
    conv["transcript"] = with_offsets(conv["transcript"])
    if conv.get("transcript_asr"):
        conv["transcript_asr"] = with_offsets(conv["transcript_asr"])
    evaluations = await asyncio.to_thread(db.list_evaluations, conv["id"])
    conv["evaluations"] = [{k: e[k] for k in ("id", "checklist_id", "parent_id", "created_at", "meta")} for e in evaluations]
    return conv


@router.post("/{conversation_id}/transcribe")
async def transcribe_call(conversation_id: str, registry: RegistryDep) -> dict:
    # * Принудительно (заново) распознаёт запись; старые оценки хранят свой снимок транскрипта и не ломаются
    if not get_settings().transcribe_enabled:
        raise TranscriptionDisabled()
    conv = await asyncio.to_thread(db.get_conversation, conversation_id)
    if not conv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Диалог не найден")
    transcript = await transcribe(registry.transcriber, conv)
    conv = await asyncio.to_thread(db.get_conversation, conv["id"])
    return {"conversation_id": conv["id"], "transcript_asr": with_offsets(transcript), "asr_meta": conv["asr_meta"]}
