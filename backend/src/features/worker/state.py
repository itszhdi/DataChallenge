# * Состояние авто-воркера в памяти процесса (читается очередью и /api/worker)
from datetime import UTC, datetime
from typing import Any

state: dict[str, Any] = {
    "alive": False, "mode": "manual", "status": "idle", "reason": "", "current": None,
    "processed": 0, "failed": 0, "last_tick": None, "last_error": None,
}


def update(**values: Any) -> None:
    state.update(values, last_tick=datetime.now(UTC).isoformat(timespec="seconds"))


def snapshot() -> dict[str, Any]:
    return dict(state)
