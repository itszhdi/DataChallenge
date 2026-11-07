# * Пакетные задачи живут в памяти процесса: для хакатона достаточно, после рестарта прогресс теряется
import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

_jobs: dict[str, dict[str, Any]] = {}
_tasks: set[asyncio.Task] = set()


def create_job(kind: str, total: int, model: str = "") -> dict[str, Any]:
    job = {
        "id": uuid.uuid4().hex[:12], "kind": kind, "status": "running", "total": total, "processed": 0, "model": model,
        "done": [], "failed": [], "skipped": [], "created_at": datetime.now(UTC).isoformat(timespec="seconds"), "finished_at": None,
    }
    _jobs[job["id"]] = job
    return job


def get_job(job_id: str) -> dict[str, Any] | None:
    return _jobs.get(job_id)


def list_jobs(active_only: bool = False) -> list[dict[str, Any]]:
    items = sorted(_jobs.values(), key=lambda j: j["created_at"], reverse=True)
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
