import asyncio

from fastapi import APIRouter, status

from src import db
from src.dependencies import LLMDep
from src.features.evaluation import jobs, service
from src.features.evaluation.exceptions import ConversationNotFound, JobNotFound, NoActiveChecklist
from src.features.evaluation.prompt import preview
from src.features.evaluation.schemas import BatchRequest, EvaluateRequest

router = APIRouter(tags=["evaluation"])


@router.post("/evaluate")
async def evaluate(body: EvaluateRequest, llm: LLMDep) -> dict:
    evaluation_id = await service.evaluate_conversation(llm, body.conversation_id)
    return await asyncio.to_thread(service.build_card, evaluation_id)


@router.post("/evaluate/batch", status_code=status.HTTP_202_ACCEPTED)
async def evaluate_batch(body: BatchRequest, llm: LLMDep) -> dict:
    ids = await asyncio.to_thread(service.resolve_batch_ids, body.conversation_ids, body.dataset, body.only_missing)
    job = jobs.create_job(body.mode, len(ids))
    jobs.spawn(service.run_batch(llm, job, ids, body.mode))
    return job


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    job = jobs.get_job(job_id)
    if not job:
        raise JobNotFound(job_id)
    return job


@router.get("/evaluations/{evaluation_id}")
async def get_evaluation(evaluation_id: int) -> dict:
    return await asyncio.to_thread(service.build_card, evaluation_id)


@router.post("/evaluations/{evaluation_id}/reapply")
async def reapply(evaluation_id: int, llm: LLMDep) -> dict:
    result = await service.reapply(llm, evaluation_id)
    card = await asyncio.to_thread(service.build_card, result["evaluation_id"])
    card["reapply"] = result
    return card


@router.get("/prompt/{conversation_id}")
async def get_prompt(conversation_id: str) -> dict:
    # * Отладка: какой промпт и схема уйдут в модель (без вызова модели)
    conversation = await asyncio.to_thread(db.get_conversation, conversation_id)
    if not conversation:
        raise ConversationNotFound(conversation_id)
    checklist = await asyncio.to_thread(db.get_active_checklist)
    if not checklist:
        raise NoActiveChecklist()
    return preview(checklist["data"], conversation)
