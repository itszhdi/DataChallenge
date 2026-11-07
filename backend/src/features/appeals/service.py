import logging
import re
from typing import Any

from fastapi import HTTPException, status

from src import db
from src.features.appeals.schemas import AppealCreate, AppealResolve
from src.features.evaluation.scoring import apply_appeals, score_evaluation
from src.features.evaluation.timing import with_offsets

logger = logging.getLogger(__name__)

FRAGMENT_CONTEXT = 2


def _not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} не найдена")


def _criterion(checklist: dict[str, Any], criterion_id: str) -> dict[str, Any]:
    c = next((c for c in checklist["criteria"] if c["id"] == criterion_id), None)
    if not c:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Критерия {criterion_id} нет в чек-листе этой оценки")
    return c


def create_appeal(evaluation_id: int, body: AppealCreate) -> dict[str, Any]:
    evaluation = db.get_evaluation(evaluation_id)
    if not evaluation:
        raise _not_found("Оценка")
    _criterion(db.get_checklist(evaluation["checklist_id"])["data"], body.criterion_id)
    if any(a["criterion_id"] == body.criterion_id for a in db.list_appeals(status="open", evaluation_id=evaluation_id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "По этому критерию уже есть открытая апелляция")
    appeal = db.insert_appeal(evaluation_id, body.criterion_id, body.comment.strip())
    logger.info("Appeal %s created: evaluation=%s criterion=%s", appeal["id"], evaluation_id, body.criterion_id)
    return appeal


def _fragment(transcript: list[dict[str, Any]], item: dict[str, Any]) -> list[dict[str, Any]]:
    # * Фрагмент ±2 реплики вокруг доказательств (или проверенного участка «#2–#5»)
    anchors = list(item.get("evidence_ids") or [])
    anchors += [int(n) for n in re.findall(r"#?(\d+)", item.get("checked_range") or "")]
    anchors = [a for a in anchors if 1 <= a <= len(transcript)]
    if not anchors:
        return transcript
    lo, hi = max(1, min(anchors) - FRAGMENT_CONTEXT), min(len(transcript), max(anchors) + FRAGMENT_CONTEXT)
    return [m for m in transcript if lo <= m["index"] <= hi]


def appeal_view(appeal: dict[str, Any]) -> dict[str, Any]:
    evaluation = db.get_evaluation(appeal["evaluation_id"])
    checklist = db.get_checklist(evaluation["checklist_id"])["data"]
    conversation = db.get_conversation(evaluation["conversation_id"])
    others = [a for a in db.list_appeals(evaluation_id=evaluation["id"]) if a["id"] != appeal["id"]]
    final = score_evaluation(checklist, apply_appeals(evaluation["answers"], others), conversation.get("channel"))
    item = next(i for i in final["criteria"] if i["id"] == appeal["criterion_id"])
    transcript = with_offsets(evaluation["meta"].get("transcript") or conversation["transcript"])
    return {
        **appeal,
        "conversation_id": conversation["id"],
        "language": conversation["language"],
        "channel": conversation["channel"],
        "criterion": {**_criterion(checklist, appeal["criterion_id"]), **(
            {"na_allowed": (conversation.get("channel") or "").strip().lower() == "voice call",
             "na_condition": "Запись звонка явно начинается после начала разговора, поэтому приветствие могло не попасть в запись."
             if (conversation.get("channel") or "").strip().lower() == "voice call" else ""}
            if appeal["criterion_id"] == "c01_contact" else {}
        )},
        "disputed": item,
        "total": final["total"],
        "fragment": _fragment(transcript, item),
    }


def list_appeals(status_filter: str | None) -> list[dict[str, Any]]:
    return [appeal_view(a) for a in db.list_appeals(status=status_filter)]


def _validate_new_answer(c: dict[str, Any], body: AppealResolve, channel: str | None = None) -> dict[str, Any]:
    if body.na:
        allowed = ((channel or "").strip().lower() == "voice call") if c["id"] == "c01_contact" else bool(c.get("na_allowed"))
        if not allowed:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Для {c['id']} N/A не допускается")
        return {"na": True, "value": None}
    allowed = [int(s["value"]) for s in c["scale"]] if c["type"] == "scale" else [0, 1]
    if body.value not in allowed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Для {c['id']} допустимы значения {allowed}")
    return {"na": False, "value": body.value}


def resolve_appeal(appeal_id: int, body: AppealResolve) -> dict[str, Any]:
    appeal = db.get_appeal(appeal_id)
    if not appeal:
        raise _not_found("Апелляция")
    if appeal["status"] != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "Апелляция уже рассмотрена")
    evaluation = db.get_evaluation(appeal["evaluation_id"])
    checklist = db.get_checklist(evaluation["checklist_id"])["data"]
    conversation = db.get_conversation(evaluation["conversation_id"])

    new_answer = None
    if body.decision == "changed":
        c = _criterion(checklist, appeal["criterion_id"])
        new_answer = _validate_new_answer(c, body, conversation.get("channel"))
        new_answer["explanation"] = f"Изменено по апелляции: {body.reason.strip()}"
        if c["type"] != "flag":
            new_answer["flags"] = []

    resolved = db.resolve_appeal(appeal_id, body.decision, body.reason.strip(), new_answer)
    appeals = db.list_appeals(evaluation_id=evaluation["id"])
    original = score_evaluation(checklist, evaluation["answers"], conversation.get("channel"))
    final = score_evaluation(checklist, apply_appeals(evaluation["answers"], appeals), conversation.get("channel"))
    logger.info(
        "Appeal %s resolved: decision=%s total %s -> %s", appeal_id, body.decision, original["total"], final["total"]
    )
    return {"appeal": resolved, "original_total": original["total"], "final_total": final["total"], "final": final}
