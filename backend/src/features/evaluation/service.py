import asyncio
import logging
import time
from collections import defaultdict
from typing import Any

from fastapi import HTTPException

from src import db
from src.config.settings import get_settings
from src.features.checklists.service import diff_checklists
from src.features.evaluation import jobs
from src.features.evaluation.exceptions import (
    ChannelExcluded,
    ConversationNotFound,
    EvaluationNotFound,
    LLMUnavailable,
    NoActiveChecklist,
    NotEvaluable,
)
from src.features.evaluation.scoring import apply_appeals, score_evaluation
from src.features.evaluation.timing import with_offsets
from src.llm.client import LLMClient, LLMError
from src.llm.prompts import build_messages, build_schema, ground_answers, select_criteria

logger = logging.getLogger(__name__)


def is_excluded(conversation: dict[str, Any]) -> bool:
    excluded = {c.strip().lower() for c in get_settings().exclude_channels}
    return (conversation.get("channel") or "").strip().lower() in excluded


def check_evaluable(conversation: dict[str, Any]) -> None:
    # ** Пустой диалог или диалог без оператора не отправляем в модель: оценивать нечего
    transcript = conversation.get("transcript") or []
    if not transcript:
        raise NotEvaluable("пустой транскрипт")
    if not any(m.get("speaker") == "operator" and (m.get("text") or "").strip() for m in transcript):
        raise NotEvaluable("в диалоге нет реплик оператора")


def validate_answers(
    criteria: list[dict[str, Any]], raw: dict[str, Any], n_messages: int
) -> tuple[dict[str, Any], list[str]]:
    # * Приводим ответ модели к нашему формату; ошибки не роняют оценку, а становятся предупреждениями
    answers: dict[str, Any] = {}
    warnings: list[str] = []
    for c in criteria:
        cid = c["id"]
        a = raw.get(cid)
        if not isinstance(a, dict):
            answers[cid] = {"status": "error"}
            warnings.append(f"{cid}: модель не вернула ответ")
            continue

        evidence = []
        for e in a.get("evidence_ids") or []:
            if isinstance(e, int) and 1 <= e <= n_messages:
                evidence.append(e)
            else:
                warnings.append(f"{cid}: ссылка на несуществующую реплику #{e} удалена")

        na = bool(a.get("na")) if c.get("na_allowed") else False
        value = a.get("value")
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if not na and not isinstance(value, int):
            answers[cid] = {"status": "error", "explanation": a.get("explanation", "")}
            warnings.append(f"{cid}: некорректное значение {value!r}")
            continue

        if c["type"] == "scale":
            steps = [int(s["value"]) for s in c.get("scale", [])]
            if not na and value not in steps:
                warnings.append(f"{cid}: значение {value} не из шкалы {steps}")
        elif not na and value not in (0, 1):
            warnings.append(f"{cid}: значение {value} вне 0/1 — засчитано как {int(bool(value))}")
            value = int(bool(value))

        flags: list[str] = []
        if c["type"] == "flag":
            allowed = set(c.get("flag_types") or [])
            flags = [f for f in a.get("flags") or [] if not allowed or f in allowed]
            if value == 1 and allowed and not flags:
                warnings.append(f"{cid}: нарушение отмечено без типа")
            if value == 0:
                flags = []

        checked = (a.get("checked_range") or "").strip()
        is_no = not na and value == 0 and c["type"] != "flag"
        if is_no and not checked and not evidence:
            warnings.append(f"{cid}: «Нет» без доказательств и проверенного участка")

        answer = {
            "status": "ok", "na": na, "value": None if na else value, "explanation": (a.get("explanation") or "").strip(),
            "evidence_ids": evidence, "checked_range": checked, "flags": flags,
        }
        # Preserve the exact quote and its verification result for review/debugging.
        if "quote" in a:
            answer["quote"] = a.get("quote", "")
            answer["quote_ref"] = a.get("quote_ref", 0)
            answer["quote_verified"] = bool(a.get("quote_verified"))
        answers[cid] = answer
    return answers, warnings


async def run_llm(
    llm: LLMClient, checklist: dict[str, Any], conversation: dict[str, Any], criteria: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    messages = build_messages(checklist, conversation, criteria)
    try:
        raw, meta = await llm.complete_json(messages, build_schema(criteria))
    except LLMError as e:
        logger.error("Evaluation failed for %s: %s", conversation["id"], e)
        raise LLMUnavailable(str(e)) from e
    raw = ground_answers(raw, conversation["transcript"])
    answers, warnings = validate_answers(criteria, raw, len(conversation["transcript"]))
    if warnings:
        logger.warning("Validation warnings for %s: %s", conversation["id"], warnings)
    meta.update(warnings=warnings, evaluated_criteria=[c["id"] for c in criteria])
    return answers, meta


async def evaluate_conversation(llm: LLMClient, conversation_id: str) -> int:
    conversation = await asyncio.to_thread(db.get_conversation, conversation_id)
    if not conversation:
        raise ConversationNotFound(conversation_id)
    if is_excluded(conversation):
        logger.info("Conversation %s skipped: excluded channel %s", conversation_id, conversation["channel"])
        raise ChannelExcluded(conversation["channel"])
    check_evaluable(conversation)
    conversation_id = conversation["id"]
    checklist = await asyncio.to_thread(db.get_active_checklist)
    if not checklist:
        raise NoActiveChecklist()

    started = time.monotonic()
    answers, meta = await run_llm(llm, checklist["data"], conversation, select_criteria(checklist["data"]))
    meta["total_seconds"] = round(time.monotonic() - started, 2)
    evaluation_id = await asyncio.to_thread(db.insert_evaluation, conversation_id, checklist["id"], answers, meta)
    logger.info("Conversation %s evaluated: evaluation_id=%s checklist_id=%s", conversation_id, evaluation_id, checklist["id"])
    return evaluation_id


def build_card(evaluation_id: int) -> dict[str, Any]:
    evaluation = db.get_evaluation(evaluation_id)
    if not evaluation:
        raise EvaluationNotFound(evaluation_id)
    checklist = db.get_checklist(evaluation["checklist_id"])
    conversation = db.get_conversation(evaluation["conversation_id"])
    appeals = db.list_appeals(evaluation_id=evaluation_id)
    meta = evaluation["meta"]

    original = score_evaluation(checklist["data"], evaluation["answers"])
    final = score_evaluation(checklist["data"], apply_appeals(evaluation["answers"], appeals))
    for score in (original, final):
        score["warnings"] = meta.get("warnings", []) + score["warnings"]

    conversation["transcript"] = with_offsets(conversation["transcript"])
    return {
        "evaluation": {k: evaluation[k] for k in ("id", "conversation_id", "checklist_id", "parent_id", "created_at")},
        "checklist": {"id": checklist["id"], "version": checklist["version"], "name": checklist["name"], "is_active": checklist["is_active"]},
        "meta": meta,
        "original": original,
        "final": final,
        "appeals": appeals,
        "conversation": conversation,
    }


def summarize_latest(dataset: str | None = None) -> dict[str, dict[str, Any]]:
    # * Итоги последних оценок для списков и аналитики: баллы считаются на лету по ответам
    evaluations = db.latest_evaluations(dataset)
    appeals_by_eval: dict[int, list] = defaultdict(list)
    for a in db.list_appeals(status="resolved"):
        appeals_by_eval[a["evaluation_id"]].append(a)
    checklists: dict[int, dict] = {}
    out = {}
    for e in evaluations:
        cl = checklists.setdefault(e["checklist_id"], db.get_checklist(e["checklist_id"])["data"])
        score = score_evaluation(cl, apply_appeals(e["answers"], appeals_by_eval[e["id"]]))
        out[e["conversation_id"]] = {"evaluation": e, "checklist": cl, "score": score}
    return out


def list_conversations_with_scores(dataset: str | None = None) -> list[dict[str, Any]]:
    items = db.list_conversations(dataset)
    summary = summarize_latest(dataset)
    for item in items:
        s = summary.get(item["id"])
        item["total"] = s["score"]["total"] if s else None
        item["preliminary"] = s["score"]["preliminary"] if s else None
        item["gross_error"] = s["score"]["gross_errors"]["detected"] if s else False
        item["excluded"] = is_excluded(item)
    return items


class NothingToReapply(Exception):
    pass


async def reapply(llm: LLMClient, evaluation_id: int) -> dict[str, Any]:
    # * Переносит оценку на активный чек-лист: неизменные ответы копируются, модель спрашивается только по изменённым/новым
    old = await asyncio.to_thread(db.get_evaluation, evaluation_id)
    if not old:
        raise EvaluationNotFound(evaluation_id)
    active = await asyncio.to_thread(db.get_active_checklist)
    if not active:
        raise NoActiveChecklist()
    if old["checklist_id"] == active["id"]:
        return {"evaluation_id": evaluation_id, "parent_id": None, "unchanged": True, "llm_called": False}

    old_checklist = await asyncio.to_thread(db.get_checklist, old["checklist_id"])
    diff = diff_checklists(old_checklist["data"], active["data"])
    copied = [cid for cid in diff["same"] + diff["weight_only"] if old["answers"].get(cid, {}).get("status") == "ok"]
    # ** Критерии, по которым раньше не было ответа, тоже переспрашиваем
    needs = [c["id"] for c in active["data"]["criteria"] if c["id"] not in copied]
    answers = {cid: old["answers"][cid] for cid in copied}
    old_warnings = [w for w in old["meta"].get("warnings", []) if w.split(":")[0] in copied]
    meta: dict[str, Any] = {"reapplied_from": evaluation_id, "copied": copied, "evaluated_criteria": needs, "diff": diff, "llm": None}

    if needs:
        conversation = await asyncio.to_thread(db.get_conversation, old["conversation_id"])
        if is_excluded(conversation):
            raise ChannelExcluded(conversation["channel"])
        check_evaluable(conversation)
        criteria = select_criteria(active["data"], needs)
        new_answers, llm_meta = await run_llm(llm, active["data"], conversation, criteria)
        answers.update(new_answers)
        meta["llm"] = {k: v for k, v in llm_meta.items() if k not in ("warnings", "evaluated_criteria")}
        meta.update({k: llm_meta[k] for k in ("provider", "model", "tokens", "cost_usd") if k in llm_meta})
        old_warnings += llm_meta["warnings"]
    meta["warnings"] = old_warnings

    new_id = await asyncio.to_thread(db.insert_evaluation, old["conversation_id"], active["id"], answers, meta, evaluation_id)
    await asyncio.to_thread(db.copy_resolved_appeals, evaluation_id, new_id, copied)
    logger.info(
        "Evaluation %s reapplied as %s: copied=%d llm_criteria=%s", evaluation_id, new_id, len(copied), needs or "none",
    )
    return {"evaluation_id": new_id, "parent_id": evaluation_id, "unchanged": False, "llm_called": bool(needs), "diff": diff}


async def reapply_conversation(llm: LLMClient, conversation_id: str) -> int:
    conversation = await asyncio.to_thread(db.get_conversation, conversation_id)
    if not conversation:
        raise ConversationNotFound(conversation_id)
    evaluation_id = await asyncio.to_thread(db.latest_evaluation_id, conversation["id"])
    if not evaluation_id:
        raise NothingToReapply("у диалога нет оценки")
    return (await reapply(llm, evaluation_id))["evaluation_id"]


async def reapply_many(llm: LLMClient, dataset: str | None) -> dict[str, Any]:
    # * Синхронный пересчёт всех последних оценок (используется при смене весов — без вызова модели)
    latest = await asyncio.to_thread(db.latest_evaluations, dataset)
    done, failed = 0, []
    for e in latest:
        try:
            await reapply(llm, e["id"])
            done += 1
        except HTTPException as ex:
            failed.append({"conversation_id": e["conversation_id"], "reason": ex.detail})
    logger.info("Reapplied %d evaluations, failed=%d", done, len(failed))
    return {"total": len(latest), "done": done, "failed": failed}


async def run_batch(llm: LLMClient, job: dict[str, Any], conversation_ids: list[str], mode: str = "evaluate") -> None:
    # ** Параллелизм ограничивает сам LLM-клиент (LLM_CONCURRENCY + троттлинг), здесь просто запускаем всё
    action = evaluate_conversation if mode == "evaluate" else reapply_conversation

    async def one(cid: str) -> None:
        try:
            evaluation_id = await action(llm, cid)
            job["done"].append({"conversation_id": cid, "evaluation_id": evaluation_id})
        except (ChannelExcluded, NotEvaluable, NothingToReapply) as e:
            job["skipped"].append({"conversation_id": cid, "reason": getattr(e, "detail", None) or str(e)})
        except HTTPException as e:
            job["failed"].append({"conversation_id": cid, "reason": e.detail})
        except Exception as e:
            logger.exception("Batch job %s: conversation %s crashed", job["id"], cid)
            job["failed"].append({"conversation_id": cid, "reason": f"{type(e).__name__}: {e}"})
        finally:
            job["processed"] += 1

    logger.info("Batch job %s (%s) started: %d conversations", job["id"], mode, len(conversation_ids))
    await asyncio.gather(*(one(cid) for cid in conversation_ids))
    jobs.finish(job)
    logger.info(
        "Batch job %s finished: done=%d failed=%d skipped=%d",
        job["id"], len(job["done"]), len(job["failed"]), len(job["skipped"]),
    )


def resolve_batch_ids(conversation_ids: list[str] | None, dataset: str | None, only_missing: bool) -> list[str]:
    items = db.list_conversations(dataset)
    if conversation_ids is not None:
        wanted = set(conversation_ids)
        items = [i for i in items if i["id"] in wanted or i["source_id"] in wanted]
    if only_missing:
        items = [i for i in items if not i["last_evaluation_id"]]
    return [i["id"] for i in items]
