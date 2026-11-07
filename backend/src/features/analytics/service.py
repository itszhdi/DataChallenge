from collections import defaultdict
from statistics import mean
from typing import Any

from src.features.evaluation.service import summarize_latest

WORST_LIMIT = 5


def _avg(values: list[float]) -> float | None:
    return round(mean(values), 2) if values else None


def build_analytics(dataset: str | None = None) -> dict[str, Any]:
    summary = summarize_latest(dataset)
    totals = [s["score"]["total"] for s in summary.values() if s["score"]["total"] is not None]

    groups: dict[str, dict[str, list]] = {"language": defaultdict(list), "channel": defaultdict(list)}
    criteria: dict[str, dict[str, Any]] = {}
    gross_count = 0

    for s in summary.values():
        e, score = s["evaluation"], s["score"]
        for key in groups:
            if score["total"] is not None:
                groups[key][e.get(key) or "?"].append(score["total"])
        gross_count += int(score["gross_errors"]["detected"])
        for item in score["criteria"]:
            stat = criteria.setdefault(item["id"], {"id": item["id"], "title": item["title"], "type": item["type"],
                                                     "evaluated": 0, "na": 0, "errors": 0, "flags": 0, "_pct": []})
            if item["status"] == "error":
                stat["errors"] += 1
                continue
            stat["evaluated"] += 1
            if item["na"]:
                stat["na"] += 1
            elif item["type"] == "flag":
                stat["flags"] += int(item["value"] == 1)
            elif item["applicable"] and item["weight"] > 0:
                stat["_pct"].append(item["points"] / item["weight"] * 100)

    for stat in criteria.values():
        pct = stat.pop("_pct")
        stat["na_share"] = round(stat["na"] / stat["evaluated"] * 100, 2) if stat["evaluated"] else None
        stat["avg_fulfillment_pct"] = _avg(pct)

    worst = sorted(
        ({"conversation_id": cid, "evaluation_id": s["evaluation"]["id"], "total": s["score"]["total"]}
         for cid, s in summary.items() if s["score"]["total"] is not None),
        key=lambda x: x["total"],
    )[:WORST_LIMIT]

    return {
        "dataset": dataset,
        "evaluated": len(summary),
        "avg_total": _avg(totals),
        "by_language": {k: {"count": len(v), "avg_total": _avg(v)} for k, v in sorted(groups["language"].items())},
        "by_channel": {k: {"count": len(v), "avg_total": _avg(v)} for k, v in sorted(groups["channel"].items())},
        "criteria": list(criteria.values()),
        "gross_errors": gross_count,
        "worst": worst,
    }
