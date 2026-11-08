import asyncio
import logging

from fastapi import APIRouter, status

from src import db
from src.dependencies import LLMDep, RegistryDep
from src.features.evaluation import jobs, service
from src.features.evaluation.queue import build_queue
from src.features.evaluation.exceptions import ConversationNotFound, JobNotActive, JobNotFound, NoActiveChecklist
from src.features.evaluation.schemas import BatchRequest, EvaluateRequest
from src.llm.prompts import preview

logger = logging.getLogger(__name__)

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


def _find_job(job_id: str) -> dict:
    # * current — идущая или поставленная на паузу задача (удобно для make pause/resume/stop)
    job = jobs.current_job() if job_id == "current" else jobs.get_job(job_id)
    if not job:
        raise JobNotFound(job_id)
    return job


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    return _find_job(job_id)


@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str) -> dict:
    job = _find_job(job_id)
    if job["status"] != "running" or job["stopped"]:
        raise JobNotActive(job["id"], "поставить на паузу")
    jobs.pause(job)
    logger.info("Batch job %s paused by user", job["id"])
    return job


@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str) -> dict:
    job = _find_job(job_id)
    if job["status"] != "paused" or job["stopped"]:
        raise JobNotActive(job["id"], "продолжить")
    jobs.resume(job)
    logger.info("Batch job %s resumed by user", job["id"])
    return job


@router.post("/jobs/{job_id}/stop")
async def stop_job(job_id: str) -> dict:
    job = _find_job(job_id)
    if job["status"] not in jobs.ACTIVE:
        raise JobNotActive(job["id"], "остановить")
    jobs.stop(job)
    logger.info("Batch job %s stopped by user", job["id"])
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
