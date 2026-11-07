# * Выгрузка результатов в JSON: финальные ответы (с учётом апелляций) по последним оценкам + статус каждого диалога набора
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src import db
from src.config.settings import get_settings
from src.features.evaluation.service import is_excluded, summarize_latest

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.1"


def _value(item: dict[str, Any]) -> Any:
    if item["status"] == "error" or item["na"]:
        return None
    if item["type"] == "scale":
        return item["value"]
    return item["value"] == 1


def _unevaluated(conv: dict[str, Any]) -> dict[str, Any]:
    # ** Диалоги без оценки тоже попадают в выгрузку — с причиной, чтобы было видно, почему нет баллов
    if conv["status"] in ("failed", "skipped"):
        status, reason = conv["status"], conv["status_error"] or ""
    elif conv["status"] in ("queued", "running"):
        status, reason = "pending", "анализ ещё идёт"
    elif is_excluded(conv):
        status, reason = "excluded", f"канал «{conv['channel']}» исключён (EXCLUDE_CHANNELS)"
    else:
        status, reason = "pending", "диалог ещё не оценивался"
    return {"status": status, "reason": reason, "criteria": [], "score": {"final_score": None, "critical_flag": False}}


def build_export(dataset: str | None, team_name: str, model_mode: str, model_name: str) -> dict[str, Any]:
    summary = summarize_latest(dataset)
    results = []
    for conv in db.list_conversations(dataset):
        base = {"conversation_id": conv["source_id"], "dataset": conv["dataset"], "channel": conv["channel"], "language": conv["language"]}
        s = summary.get(conv["id"])
        if not s:
            results.append(base | _unevaluated(conv))
            continue
        score = s["score"]
        criteria = [
            {
                "criterion_id": i["id"],
                "value": _value(i),
                "rationale": i.get("explanation") or "",
                "evidence_turns": i.get("evidence_ids") or [],
            }
            for i in score["criteria"]
        ]
        meta = s["evaluation"]["meta"]
        results.append(base | {
            "status": "partial" if score["preliminary"] else "ok",
            "evaluation_id": s["evaluation"]["id"],
            "model": meta.get("model"),
            "criteria": criteria,
            "score": {"final_score": score["total"], "critical_flag": score["gross_errors"]["detected"]},
        })
    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "team_name": team_name,
        "model": {"mode": model_mode, "name": model_name},
        "dataset": dataset,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "counts": counts,
        "results": results,
    }


def _safe_name(export: dict[str, Any]) -> str:
    # ! Имя набора идёт в путь файла: только безопасные символы, никаких «../»
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", export["dataset"] or "ALL").strip("_") or "ALL"


def export_filename(export: dict[str, Any]) -> str:
    stamp = datetime.fromisoformat(export["generated_at"]).strftime("%Y%m%d-%H%M%S")
    return f"{_safe_name(export)}_{stamp}.json"


def save_export(export: dict[str, Any]) -> dict[str, Any]:
    # * Файл с меткой времени + «latest», чтобы последний результат всегда лежал по одному пути
    out_dir: Path = get_settings().results_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    body = json.dumps(export, ensure_ascii=False, indent=2)
    path = out_dir / export_filename(export)
    latest = out_dir / f"{_safe_name(export)}_latest.json"
    path.write_text(body, encoding="utf-8")
    latest.write_text(body, encoding="utf-8")
    logger.info("Export saved: %s (%d results, counts=%s)", path, len(export["results"]), export["counts"])
    return {
        "path": str(path), "latest": str(latest), "file": path.name, "counts": export["counts"],
        "total": len(export["results"]), "generated_at": export["generated_at"],
    }
