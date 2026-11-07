# ** Баллы считает только этот модуль: чистые функции, без БД и LLM. Модель лишь отвечает на вопросы
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

ANSWER_FIELDS = ("explanation", "evidence_ids", "checked_range", "flags", "needs_review", "unverified_claims")


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def _round(value: Decimal, digits: int) -> float:
    # ! Только Decimal + ROUND_HALF_UP: встроенный round() даёт банковское округление (88.125 -> 88.12)
    return float(value.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))


def snap_to_scale(value: int, steps: list[int]) -> int:
    # * Ближайшая ступень шкалы; при равенстве расстояний — большая
    return min(steps, key=lambda s: (abs(s - value), -s))


def apply_appeals(answers: dict[str, Any], appeals: list[dict[str, Any]]) -> dict[str, Any]:
    # * Финальные ответы = исходные ответы модели + решения changed по апелляциям в порядке id
    final = {cid: dict(a) for cid, a in answers.items()}
    for appeal in sorted(appeals, key=lambda a: a["id"]):
        if appeal.get("status") == "resolved" and appeal.get("decision") == "changed" and appeal.get("new_answer"):
            cid = appeal["criterion_id"]
            final[cid] = {**final.get(cid, {}), **appeal["new_answer"], "status": "ok", "appeal_id": appeal["id"]}
    return final


def score_evaluation(checklist: dict[str, Any], answers: dict[str, Any], channel: str | None = None) -> dict[str, Any]:
    digits = int(checklist.get("settings", {}).get("rounding", 2))
    warnings: list[str] = []
    items: list[dict[str, Any]] = []
    gross = {"detected": False, "types": [], "criteria": []}

    for c in checklist["criteria"]:
        cid, ctype = c["id"], c["type"]
        weight = _d(c.get("weight", 0))
        ans = answers.get(cid)
        item = {
            "id": cid, "title": c.get("title", cid), "section": c.get("section"), "type": ctype,
            "weight": float(weight), "status": "ok", "answer": None, "value": None, "na": False,
            "raw_points": Decimal(0), "applicable": False,
        }
        if ans:
            item.update({k: ans.get(k) for k in ANSWER_FIELDS})
            if ans.get("appeal_id"):
                item["appeal_id"] = ans["appeal_id"]

        if not ans or ans.get("status") == "error" or (ans.get("value") is None and not ans.get("na")):
            item["status"] = "error"
            warnings.append(f"{cid}: нет ответа модели — критерий исключён, итог предварительный")
            items.append(item)
            continue

        na = bool(ans.get("na"))
        value = ans.get("value")
        na_allowed = (
            (channel or "").strip().lower() == "voice call"
            if cid == "c01_contact" else bool(c.get("na_allowed"))
        )
        if na and not na_allowed:
            warnings.append(f"{cid}: N/A не допускается — засчитано как «Нет»")
            na, value = False, 0
        if na:
            item.update(na=True, answer="na")
            items.append(item)
            continue

        value = int(value or 0)
        if ctype == "flag":
            detected = value == 1
            item.update(value=int(detected), answer="yes" if detected else "no")
            if detected:
                gross["detected"] = True
                gross["criteria"].append(cid)
                gross["types"].extend(t for t in (ans.get("flags") or []) if t not in gross["types"])
            items.append(item)
            continue

        if ctype == "scale":
            steps = [int(s["value"]) for s in c.get("scale", [])]
            if not steps:
                warnings.append(f"{cid}: у шкального критерия нет ступеней — критерий исключён")
                item["status"] = "error"
                items.append(item)
                continue
            if value not in steps:
                snapped = snap_to_scale(value, steps)
                warnings.append(f"{cid}: значение {value} не из шкалы — приведено к ступени {snapped}")
                value = snapped
            raw = weight * _d(value) / _d(max(steps)) if max(steps) else Decimal(0)
            item.update(value=value, answer=value)
        else:
            yes = value == 1
            raw = weight if yes else Decimal(0)
            item.update(value=int(yes), answer="yes" if yes else "no")

        item.update(raw_points=raw, applicable=True)
        items.append(item)

    applicable = [i for i in items if i["applicable"]]
    total_weight = sum((_d(i["weight"]) for i in applicable), Decimal(0))
    total_points = sum((i["raw_points"] for i in applicable), Decimal(0))

    # ** Перераспределение N/A: вес каждого применимого критерия масштабируется так, чтобы максимум был 100
    factor = Decimal(100) / total_weight if total_weight > 0 else Decimal(0)
    for i in items:
        i["effective_weight"] = _round(_d(i["weight"]) * factor, digits) if i["applicable"] else 0.0
        i["final_points"] = _round(i["raw_points"] * factor, digits) if i["applicable"] else 0.0
        i["points"] = _round(i["raw_points"], digits)
        del i["raw_points"]

    total = _round(total_points * factor, digits) if total_weight > 0 else None

    sections = []
    for s in checklist.get("sections", []) or [{"id": sid, "title": sid} for sid in dict.fromkeys(c.get("section") for c in checklist["criteria"])]:
        sec_items = [i for i in items if i["section"] == s["id"]]
        sec_app = [i for i in sec_items if i["applicable"]]
        sections.append({
            "id": s["id"], "title": s.get("title", s["id"]),
            "points": _round(sum((_d(i["final_points"]) for i in sec_app), Decimal(0)), digits),
            "max": _round(sum((_d(i["effective_weight"]) for i in sec_app), Decimal(0)), digits),
            "criteria": [i["id"] for i in sec_items],
        })

    has_errors = any(i["status"] == "error" for i in items)
    return {
        "total": total,
        "max_total": 100 if total is not None else None,
        "preliminary": has_errors,
        "criteria": items,
        "sections": sections,
        "gross_errors": gross,
        "warnings": warnings,
    }
