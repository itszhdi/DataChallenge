# * Состояние очереди анализа и оценка оставшегося времени (ETA) по средней длительности последних оценок
from datetime import UTC, datetime
from statistics import mean
from typing import Any

from src import db
from src.config.settings import get_settings
from src.features.settings.service import load as load_settings
from src.features.worker import state as worker_state
from src.llm.client import LLMClient

# ** Пока у модели нет истории оценок, берём грубую оценку одной оценки
DEFAULT_EVAL_SEC = 30.0
# * Сколько кандидатов авто-воркера показывать в очереди (ETA считается по всем)
UPCOMING_LIMIT = 1000


def _elapsed(started_at: str | None) -> float:
    if not started_at:
        return 0.0
    return max((datetime.now(UTC) - datetime.fromisoformat(started_at)).total_seconds(), 0.0)


def average_seconds(llm: LLMClient) -> float:
    durations = db.recent_durations(llm.model) if llm.model else []
    return round(mean(durations), 1) if durations else DEFAULT_EVAL_SEC


def _brief(s: dict[str, Any]) -> dict[str, Any]:
    keys = ("conversation_id", "source_id", "dataset", "state", "source", "job_id", "error", "attempts", "model",
            "queued_at", "started_at", "finished_at")
    return {k: s.get(k) for k in keys}


def build_queue(llm: LLMClient, dataset: str | None = None) -> dict[str, Any]:
    # ** ETA считается по всей очереди (порядок общий), а фильтр по набору применяется к ответу
    settings = load_settings()
    upcoming = (
        db.auto_candidates(settings.auto_sort, settings.auto_dataset, get_settings().exclude_channels, UPCOMING_LIMIT)
        if settings.auto_mode else []
    )
    avg = average_seconds(llm)
    workers = max(1, llm.profile.concurrency)
    running = [_brief(s) for s in db.list_statuses(("running",))]
    queued = [_brief(s) for s in db.list_statuses(("queued",))]

    for r in running:
        r["elapsed_sec"] = round(_elapsed(r["started_at"]), 1)
        r["eta_sec"] = round(max(avg - r["elapsed_sec"], 1.0), 1)
    base = max((r["eta_sec"] for r in running), default=0.0)
    # * Очередь пакета, затем — кандидаты авто-воркера (они начнутся после пакета)
    waiting = queued + [
        {k: u[k] for k in ("conversation_id", "source_id", "dataset", "messages", "imported_at")} | {"state": "upcoming", "source": "auto"}
        for u in upcoming
    ]
    for pos, q in enumerate(waiting):
        q["position"] = pos + 1
        q["eta_sec"] = round(base + (pos // workers + 1) * avg, 1)

    failed = [_brief(s) for s in db.list_statuses(("failed",), dataset)]
    in_dataset = (lambda x: x.get("dataset") == dataset) if dataset else (lambda x: True)  # noqa: E731
    running = [r for r in running if in_dataset(r)]
    waiting = [q for q in waiting if in_dataset(q)]
    return {
        "worker": {**worker_state.snapshot(), "auto_mode": settings.auto_mode, "auto_sort": settings.auto_sort,
                   "auto_dataset": settings.auto_dataset},
        "model": {"profile": llm.profile.name, "name": llm.model, "avg_eval_sec": avg, "workers": workers},
        "running": running,
        "queued": [q for q in waiting if q["state"] == "queued"],
        "upcoming": [q for q in waiting if q["state"] == "upcoming"],
        "failed": failed,
        "counts": {"running": len(running), "queued": sum(q["state"] == "queued" for q in waiting),
                   "upcoming": sum(q["state"] == "upcoming" for q in waiting), "failed": len(failed)},
        "eta_total_sec": max([r["eta_sec"] for r in running] + [q["eta_sec"] for q in waiting], default=0.0),
    }


def eta_by_conversation(queue: dict[str, Any]) -> dict[str, float]:
    return {x["conversation_id"]: x["eta_sec"] for x in queue["running"] + queue["queued"] + queue["upcoming"]}
