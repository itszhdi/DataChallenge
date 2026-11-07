from collections import defaultdict
from statistics import mean
from typing import Any

from src import db
from src.config.settings import get_settings
from src.features.evaluation.service import summarize_latest

WORST_LIMIT = 5
# * Диапазоны итога для распределения: ровно 90 относится к норме
CRITICAL_BELOW = 50
RISK_BELOW = 75
NORM_UP_TO = 90


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
        ({"id": cid, "conversation_id": s["evaluation"].get("source_id") or cid,
          "evaluation_id": s["evaluation"]["id"], "total": s["score"]["total"]}
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


def _percent(item: dict[str, Any]) -> float | None:
    # * Выполнение критерия в процентах; None, если он не влияет на итог (N/A, ошибка, флаг, вес 0)
    if item["status"] == "error" or not item["applicable"] or item["weight"] <= 0:
        return None
    return round(item["points"] / item["weight"] * 100, 2)


def _bucket(total: float) -> str:
    if total < CRITICAL_BELOW:
        return "critical"
    if total < RISK_BELOW:
        return "risk"
    return "norm" if total <= NORM_UP_TO else "reference"


def _dialog_row(cid: str, data: dict[str, Any]) -> dict[str, Any]:
    e, score = data["evaluation"], data["score"]
    criteria = {i["id"]: {"answer": i["answer"], "percent": _percent(i)} for i in score["criteria"]}
    weak = [(p, -i["weight"], i["id"]) for i in score["criteria"] if (p := criteria[i["id"]]["percent"]) is not None and p < 100]
    # * conversation_id — исходный id для показа, id — составной ключ для перехода в карточку
    return {
        "id": cid,
        "conversation_id": e.get("source_id") or cid,
        "dataset": e.get("dataset"),
        "evaluation_id": e["id"],
        "language": e.get("language"),
        "channel": e.get("channel"),
        "total": score["total"],
        "preliminary": score["preliminary"],
        "bucket": _bucket(score["total"]) if score["total"] is not None else None,
        "gross_error": score["gross_errors"]["detected"],
        "gross_types": score["gross_errors"]["types"],
        "weak_criterion": min(weak)[2] if weak else None,
        "criteria": criteria,
    }


def _appeals_stats(evaluation_ids: set[int]) -> dict[str, Any]:
    # ! Только по последним оценкам: reapply копирует решённые апелляции новыми строками, иначе они задвоятся
    appeals = [a for a in db.list_appeals() if a["evaluation_id"] in evaluation_ids]
    changed = sum(a["decision"] == "changed" for a in appeals)
    resolved = sum(a["status"] == "resolved" for a in appeals)
    return {
        "filed": len(appeals),
        "open": len(appeals) - resolved,
        "changed": changed,
        "changed_percent": round(changed / resolved * 100, 2) if resolved else None,
    }


def build_dashboard(dataset: str | None = None) -> dict[str, Any]:
    # * Сводка для супервайзера: dialogs отдаётся целиком, чтобы фронт фильтровал drill-down мгновенно
    summary = summarize_latest(dataset)
    rows = [_dialog_row(cid, s) for cid, s in sorted(summary.items())]
    totals = [r["total"] for r in rows if r["total"] is not None]
    fatal = sum(r["gross_error"] for r in rows)

    stats: dict[str, dict[str, Any]] = {}
    for s in summary.values():
        for item in s["score"]["criteria"]:
            if item["type"] == "flag" or item["status"] == "error":
                continue
            stat = stats.setdefault(item["id"], {"id": item["id"], "title": item["title"], "weight": item["weight"], "evaluated": 0, "na": 0, "_pct": []})
            stat["evaluated"] += 1
            stat["na"] += int(item["na"])
            if (p := _percent(item)) is not None:
                stat["_pct"].append(p)
    criteria = []
    for stat in stats.values():
        pct = stat.pop("_pct")
        if stat["weight"] > 0:
            criteria.append({**stat, "avg_percent": _avg(pct)})

    scored = [c for c in criteria if c["avg_percent"] is not None]
    worst = min(scored, key=lambda c: (c["avg_percent"], -c["weight"]), default=None)
    segments: dict[str, dict[str, list[float]]] = {"language": defaultdict(list), "channel": defaultdict(list)}
    for r in rows:
        if r["total"] is not None:
            for key, groups in segments.items():
                groups[r[key] or "?"].append(r["total"])

    return {
        "dataset": dataset,
        "summary": {
            "average_score": _avg(totals),
            "target_score": get_settings().cqa_target_score,
            "total_evaluated": len(rows),
            "fatal_count": fatal,
            "fatal_percent": round(fatal / len(rows) * 100, 2) if rows else None,
        },
        "bottleneck": {"criterion_id": worst["id"], "title": worst["title"], "avg_percent": worst["avg_percent"]} if worst else None,
        "appeals": _appeals_stats({s["evaluation"]["id"] for s in summary.values()}),
        "criteria_averages": criteria,
        "by_language": {k: {"count": len(v), "avg_total": _avg(v)} for k, v in sorted(segments["language"].items())},
        "by_channel": {k: {"count": len(v), "avg_total": _avg(v)} for k, v in sorted(segments["channel"].items())},
        "distribution": [
            {"bucket": b, "count": sum(_bucket(t) == b for t in totals)} for b in ("critical", "risk", "norm", "reference")
        ],
        "dialogs": rows,
    }
