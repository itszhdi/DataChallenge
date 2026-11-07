import asyncio

from fastapi import APIRouter, status

from src import db
from src.dependencies import LLMDep, RegistryDep
from src.features.evaluation import jobs, service
from src.features.evaluation.queue import build_queue
from src.features.evaluation.exceptions import ConversationNotFound, JobNotFound, NoActiveChecklist
from src.features.evaluation.schemas import BatchRequest, EvaluateRequest
from src.llm.prompts import preview

router = APIRouter(tags=["evaluation"])


@router.post("/evaluate")
async def evaluate(body: EvaluateRequest, llm: LLMDep) -> dict:
    evaluation_id = await service.tracked(llm, body.conversation_id, service.evaluate_conversation)
    return await asyncio.to_thread(service.build_card, evaluation_id)


@router.post("/evaluate/batch", status_code=status.HTTP_202_ACCEPTED)
async def evaluate_batch(body: BatchRequest, registry: RegistryDep) -> dict:
    return await service.start_batch(
        registry, body.dataset, body.mode, body.only_missing, body.conversation_ids, body.only_failed
    )


@router.get("/jobs")
async def list_jobs(active: bool = False) -> list[dict]:
    # * Для восстановления прогресса после перезагрузки страницы
    return jobs.list_jobs(active)


@router.get("/queue")
async def get_queue(llm: LLMDep, dataset: str | None = None) -> dict:
    return await asyncio.to_thread(build_queue, llm, dataset)


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
