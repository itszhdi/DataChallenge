# * Пакетные задачи живут в памяти процесса: для хакатона достаточно, после рестарта прогресс теряется
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# * running → paused → running …; finished — конец, в том числе после остановки (stopped=True)
ACTIVE = ("running", "paused")

_jobs: dict[str, dict[str, Any]] = {}
_tasks: set[asyncio.Task] = set()


@dataclass
class Control:
    # ** Управление идущим пакетом: в JSON задачи не попадает
    resume: asyncio.Event = field(default_factory=asyncio.Event)
    stopped: bool = False
    tasks: dict[str, asyncio.Task] = field(default_factory=dict)

    def interrupt(self) -> None:
        # ! Отмена задачи закрывает HTTP-запрос к модели, и LM Studio прекращает генерацию
        for task in self.tasks.values():
            task.cancel()


_controls: dict[str, Control] = {}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def create_job(kind: str, conversation_ids: list[str], model: str = "") -> dict[str, Any]:
    job = {
        "id": uuid.uuid4().hex[:12], "kind": kind, "status": "running", "total": len(conversation_ids), "processed": 0,
        "model": model, "conversation_ids": conversation_ids, "current": [],
        "done": [], "failed": [], "skipped": [], "cancelled": [], "stopped": False,
        "created_at": _now(), "paused_at": None, "finished_at": None,
    }
    _jobs[job["id"]] = job
    control = Control()
    control.resume.set()
    _controls[job["id"]] = control
    return job


def get_job(job_id: str) -> dict[str, Any] | None:
    return _jobs.get(job_id)


def control(job_id: str) -> Control:
    return _controls[job_id]


def current_job() -> dict[str, Any] | None:
    return next((job for job in _jobs.values() if job["status"] in ACTIVE), None)


def list_jobs(active_only: bool = False) -> list[dict[str, Any]]:
    # * Новые первыми по порядку создания: created_at с точностью до секунды даёт ничьи
    items = list(reversed(_jobs.values()))
    return [j for j in items if j["status"] in ACTIVE] if active_only else items[:20]


def has_running() -> bool:
    # * Пауза тоже держит очередь: авто-воркер не должен занимать модель, пока пользователь не решил
    return current_job() is not None


def pause(job: dict[str, Any]) -> None:
    c = _controls[job["id"]]
    c.resume.clear()
    job["status"] = "paused"
    job["paused_at"] = _now()
    c.interrupt()


def resume(job: dict[str, Any]) -> None:
    job["status"] = "running"
    job["paused_at"] = None
    _controls[job["id"]].resume.set()


def stop(job: dict[str, Any]) -> None:
    c = _controls[job["id"]]
    c.stopped = True
    job["stopped"] = True
    # * Будим воркеры, ждущие снятия паузы, чтобы они вышли
    c.resume.set()
    c.interrupt()


def finish(job: dict[str, Any]) -> None:
    job["status"] = "finished"
    job["finished_at"] = _now()
    job["paused_at"] = None
    _controls.pop(job["id"], None)


def spawn(coro) -> None:
    # ** Храним ссылку на задачу, иначе GC может убить её посреди пакета
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
