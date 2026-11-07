# * Выгрузка результатов в JSON: финальные ответы (с учётом апелляций) по последним оценкам
from typing import Any

from src.features.evaluation.service import summarize_latest

SCHEMA_VERSION = "1.1"


def _value(item: dict[str, Any]) -> Any:
    if item["status"] == "error" or item["na"]:
        return None
    if item["type"] == "scale":
        return item["value"]
    return item["value"] == 1


def build_export(dataset: str | None, team_name: str, model_mode: str, model_name: str) -> dict[str, Any]:
    results = []
    for cid, s in sorted(summarize_latest(dataset).items()):
        score = s["score"]
        meta = (s.get("evaluation") or {}).get("meta") or {}
        criteria = [
            {
                "criterion_id": i["id"],
                "value": _value(i),
                "rationale": i.get("explanation") or "",
                "evidence_turns": i.get("evidence_ids") or [],
            }
            for i in score["criteria"]
        ]
        results.append({
            "conversation_id": cid,
            "status": "partial" if score["preliminary"] else "ok",
            "prompt_version": meta.get("prompt_version"),
            "criteria_prompt_versions": meta.get("criteria_prompt_versions") or {},
            "criteria": criteria,
            "score": {"final_score": score["total"], "critical_flag": score["gross_errors"]["detected"]},
        })
    return {"schema_version": SCHEMA_VERSION, "team_name": team_name, "model": {"mode": model_mode, "name": model_name}, "results": results}
