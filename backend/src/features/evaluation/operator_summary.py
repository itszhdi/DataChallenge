"""Краткая обратная связь оператору, отделённая от расчёта оценки."""

from typing import Any


COACHING_TIPS = {
    "c01_contact": "В первом ответе поздоровайтесь на языке клиента и назовите своё имя.",
    "c02_needs": "Учитывайте уже сообщённые детали и уточняйте только то, чего действительно не хватает.",
    "c03_ident": "Подтвердите личность до раскрытия данных по счёту или выполнения защищённого действия.",
    "c04_consult": "Ответьте на каждый существенный вопрос или дайте конкретный следующий шаг.",
    "c05_empathy": "Отреагируйте на конкретную проблему клиента, сохраняя вежливый тон.",
    "c06_flow": "Предупреждайте о задержках и ведите разговор ясно, последовательно и без повторных вопросов.",
    "c07_closing": "Подведите итог или предложите дальнейшую помощь, затем попрощайтесь.",
    "c08_gross": "Используйте официальные каналы; не предлагайте личные платные услуги и не раскрывайте конфиденциальные сведения.",
}


def _tip(criterion: dict[str, Any]) -> str:
    tip = COACHING_TIPS.get(criterion["id"])
    if tip:
        return tip
    guidance = (criterion.get("guidance") or "").strip()
    rule = (criterion.get("rule") or "").strip()
    return guidance or (f"Ориентируйтесь на правило критерия: {rule}" if rule else "Следуйте требованиям этого критерия.")


def build_operator_summary(checklist: dict[str, Any], score: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Собирает советы только из готовых ответов модели; новых LLM-вызовов нет."""
    criteria = {c["id"]: c for c in checklist.get("criteria", [])}
    strengths: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []

    for item in score.get("criteria", []):
        criterion = criteria.get(item.get("id"), {})
        cid = item.get("id", "")
        if item.get("na"):
            continue
        if item.get("status") == "error":
            review.append({"criterion_id": cid, "title": item.get("title", cid)})
            continue

        explanation = (item.get("explanation") or "").strip()
        evidence_ids = item.get("evidence_ids") or []
        if item.get("type") == "flag":
            if item.get("value") == 1:
                improvements.append({
                    "criterion_id": cid,
                    "title": item.get("title", cid),
                    "feedback": explanation,
                    "action": _tip(criterion),
                    "evidence_ids": evidence_ids,
                    "priority": "critical",
                })
            continue

        passed = False
        if item.get("type") == "scale":
            steps = [int(s["value"]) for s in criterion.get("scale", [])]
            passed = bool(steps) and item.get("value") == max(steps)
        else:
            passed = item.get("value") == 1

        if passed:
            strengths.append({
                "criterion_id": cid,
                "title": item.get("title", cid),
                "feedback": explanation,
                "evidence_ids": evidence_ids,
            })
        else:
            improvements.append({
                "criterion_id": cid,
                "title": item.get("title", cid),
                "feedback": explanation,
                "action": _tip(criterion),
                "evidence_ids": evidence_ids,
                "priority": "normal",
            })

    return {"strengths": strengths, "improvements": improvements, "review": review}
