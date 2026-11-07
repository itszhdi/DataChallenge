# * Пакетные задачи живут в памяти процесса: для хакатона достаточно, после рестарта прогресс теряется
import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

_jobs: dict[str, dict[str, Any]] = {}
_tasks: set[asyncio.Task] = set()


def create_job(kind: str, conversation_ids: list[str], model: str = "") -> dict[str, Any]:
    job = {
        "id": uuid.uuid4().hex[:12], "kind": kind, "status": "running", "total": len(conversation_ids), "processed": 0,
        "model": model, "conversation_ids": conversation_ids, "current": [],
        "done": [], "failed": [], "skipped": [], "created_at": datetime.now(UTC).isoformat(timespec="seconds"), "finished_at": None,
    }
    _jobs[job["id"]] = job
    return job


def get_job(job_id: str) -> dict[str, Any] | None:
    return _jobs.get(job_id)


def current_job() -> dict[str, Any] | None:
    return next((job for job in _jobs.values() if job["status"] == "running"), None)


def list_jobs(active_only: bool = False) -> list[dict[str, Any]]:
    # * Новые первыми по порядку создания: created_at с точностью до секунды даёт ничьи
    items = list(reversed(_jobs.values()))
    return [j for j in items if j["status"] == "running"] if active_only else items[:20]


def has_running() -> bool:
    return any(j["status"] == "running" for j in _jobs.values())


def finish(job: dict[str, Any]) -> None:
    job["status"] = "finished"
    job["finished_at"] = datetime.now(UTC).isoformat(timespec="seconds")


def spawn(coro) -> None:
    # ** Храним ссылку на задачу, иначе GC может убить её посреди пакета
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
