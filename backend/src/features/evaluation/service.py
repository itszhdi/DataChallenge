import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import HTTPException

from src import db
from src.config.settings import get_settings
from src.features.checklists.service import diff_checklists
from src.features.evaluation import jobs
from src.features.evaluation.queue import build_queue, eta_by_conversation
from src.features.evaluation.exceptions import (
    ChannelExcluded,
    ConversationNotFound,
    EvaluationNotFound,
    JobAlreadyRunning,
    LLMUnavailable,
    NoActiveChecklist,
    NotEvaluable,
)
from src.features.evaluation.operator_summary import build_operator_summary
from src.features.evaluation.scoring import apply_appeals, score_evaluation
from src.features.evaluation.timing import with_offsets
from src.features.settings.schemas import QueueSort
from src.features.settings.service import load_app_settings
from src.features.transcription.service import prepare_transcript
from src.llm.client import LLMClient, LLMError, LLMRegistry
from src.llm.prompts import PROMPT_VERSION, build_messages, build_schema, ground_answers, select_criteria

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

        raw_claims = a.get("unverified_claims")
        if not isinstance(raw_claims, list):
            raw_claims = []
        claims = [x.strip()[:500] for x in raw_claims if isinstance(x, str) and x.strip()][:10]
        answer = {
            "status": "ok", "na": na, "value": None if na else value, "explanation": (a.get("explanation") or "").strip(),
            "evidence_ids": evidence, "checked_range": checked, "flags": flags,
            "needs_review": bool(a.get("needs_review")) or bool(claims),
            "unverified_claims": claims,
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
    # c01 N/A is a recording limitation specific to calls; keep stored checklist unchanged.
    criteria = [
        {**c, **({
            "na_allowed": (conversation.get("channel") or "").strip().lower() == "voice call",
            "na_condition": "Запись звонка явно начинается после начала разговора, поэтому приветствие могло не попасть в запись."
                if (conversation.get("channel") or "").strip().lower() == "voice call" else "",
        } if c["id"] == "c01_contact" else {})}
        for c in criteria
    ]
    messages = build_messages(checklist, conversation, criteria)
    try:
        selected_model = llm.model_for_channel(conversation.get("channel"))
        if selected_model == llm.model:
            raw, meta = await llm.complete_json(messages, build_schema(criteria))
        else:
            raw, meta = await llm.complete_json(messages, build_schema(criteria), channel=conversation.get("channel"))
    except LLMError as e:
        logger.error("Evaluation failed for %s: %s", conversation["id"], e)
        raise LLMUnavailable(str(e), e.code) from e
    raw = ground_answers(raw, conversation["transcript"])
    answers, warnings = validate_answers(criteria, raw, len(conversation["transcript"]))
    if warnings:
        logger.warning("Validation warnings for %s: %s", conversation["id"], warnings)
    meta.update(
        prompt_version=PROMPT_VERSION,
        criteria_prompt_versions={c["id"]: PROMPT_VERSION for c in criteria},
        warnings=warnings,
        evaluated_criteria=[c["id"] for c in criteria],
    )
    return answers, meta


async def evaluate_conversation(llm: LLMClient, conversation_id: str) -> int:
    conversation = await asyncio.to_thread(db.get_conversation, conversation_id)
    if not conversation:
        raise ConversationNotFound(conversation_id)
    if is_excluded(conversation):
        logger.info("Conversation %s skipped: excluded channel %s", conversation_id, conversation["channel"])
        raise ChannelExcluded(conversation["channel"])
    # ** Для звонков с записью — свой транскрипт из аудио (по настройке call_transcript)
    call_transcript = (await asyncio.to_thread(load_app_settings)).call_transcript
    transcript, source = await prepare_transcript(conversation, call_transcript)
    conversation = {**conversation, "transcript": transcript}
    check_evaluable(conversation)
    conversation_id = conversation["id"]
    checklist = await asyncio.to_thread(db.get_active_checklist)
    if not checklist:
        raise NoActiveChecklist()

    previous_id = await asyncio.to_thread(db.latest_evaluation_id, conversation_id)
    started = time.monotonic()
    answers, meta = await run_llm(llm, checklist["data"], conversation, select_criteria(checklist["data"]))
    meta["total_seconds"] = round(time.monotonic() - started, 2)
    meta["previous_evaluation_id"] = previous_id
    meta["transcript_source"] = source
    if source == "asr":
        # ! Снимок транскрипта: номера #N в ответах модели должны совпадать с карточкой даже после повторного распознавания
        meta["transcript"] = transcript
    evaluation_id = await asyncio.to_thread(db.insert_evaluation, conversation_id, checklist["id"], answers, meta)
    if previous_id:
        await asyncio.to_thread(carry_appeals, previous_id, evaluation_id, checklist["data"])
    logger.info("Conversation %s evaluated: evaluation_id=%s checklist_id=%s", conversation_id, evaluation_id, checklist["id"])
    return evaluation_id


def evaluated_transcript(evaluation: dict[str, Any], conversation: dict[str, Any]) -> list[dict[str, Any]]:
    return evaluation["meta"].get("transcript") or conversation["transcript"]


def carry_appeals(from_id: int, to_id: int, active: dict[str, Any], diff: dict[str, Any] | None = None) -> dict[str, int]:
    # * Решения апелляций сохраняются только для критериев, чья формулировка не менялась
    if diff is None:
        old = db.get_evaluation(from_id)
        diff = diff_checklists(db.get_checklist(old["checklist_id"])["data"], active)
    result = db.carry_appeals(from_id, to_id, diff["same"] + diff["weight_only"], [c["id"] for c in active["criteria"]])
    if any(result.values()):
        logger.info("Appeals carried from evaluation %s to %s: %s", from_id, to_id, result)
    return result


def build_card(evaluation_id: int) -> dict[str, Any]:
    evaluation = db.get_evaluation(evaluation_id)
    if not evaluation:
        raise EvaluationNotFound(evaluation_id)
    checklist = db.get_checklist(evaluation["checklist_id"])
    conversation = db.get_conversation(evaluation["conversation_id"])
    appeals = db.list_appeals(evaluation_id=evaluation_id)
    meta = evaluation["meta"]

    original = score_evaluation(checklist["data"], evaluation["answers"], conversation.get("channel"))
    final = score_evaluation(checklist["data"], apply_appeals(evaluation["answers"], appeals), conversation.get("channel"))
    for score in (original, final):
        score["warnings"] = meta.get("warnings", []) + score["warnings"]

    conversation["transcript"] = with_offsets(evaluated_transcript(evaluation, conversation))
    conversation["transcript_source"] = meta.get("transcript_source", "original")
    conversation.pop("transcript_asr", None)
    meta = {k: v for k, v in meta.items() if k != "transcript"}
    return {
        "evaluation": {k: evaluation[k] for k in ("id", "conversation_id", "checklist_id", "parent_id", "created_at")},
        "checklist": {"id": checklist["id"], "version": checklist["version"], "name": checklist["name"], "is_active": checklist["is_active"]},
        "meta": meta,
        "original": original,
        "final": final,
        "operator_summary": build_operator_summary(checklist["data"], final),
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
        score = score_evaluation(cl, apply_appeals(e["answers"], appeals_by_eval[e["id"]]), e.get("channel"))
        out[e["conversation_id"]] = {"evaluation": e, "checklist": cl, "score": score}
    return out


def list_conversations_with_scores(dataset: str | None = None, llm: LLMClient | None = None) -> list[dict[str, Any]]:
    items = db.list_conversations(dataset)
    summary = summarize_latest(dataset)
    eta = eta_by_conversation(build_queue(llm, dataset)) if llm else {}
    for item in items:
        item["eta_sec"] = eta.get(item["id"])
        s = summary.get(item["id"])
        item["total"] = s["score"]["total"] if s else None
        item["preliminary"] = s["score"]["preliminary"] if s else None
        item["gross_error"] = s["score"]["gross_errors"]["detected"] if s else False
        item["excluded"] = is_excluded(item)
    return items


class NothingToReapply(Exception):
    code = "no_evaluation"


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
    old_meta = old.get("meta") or {}
    inherited_versions = old_meta.get("criteria_prompt_versions") or {}
    criteria_versions = {cid: inherited_versions.get(cid, old_meta.get("prompt_version") or "unknown") for cid in copied}
    meta: dict[str, Any] = {
        "transcript_source": old_meta.get("transcript_source", "original"),
        **({"transcript": old_meta["transcript"]} if old_meta.get("transcript") else {}),
        "reapplied_from": evaluation_id,
        "copied": copied,
        "evaluated_criteria": needs,
        "diff": diff,
        "llm": None,
        "prompt_version": old_meta.get("prompt_version"),
        "criteria_prompt_versions": criteria_versions,
    }

    if needs:
        conversation = await asyncio.to_thread(db.get_conversation, old["conversation_id"])
        if is_excluded(conversation):
            raise ChannelExcluded(conversation["channel"])
        # ** Переоценка идёт по тому же транскрипту, что и исходная оценка
        conversation = {**conversation, "transcript": evaluated_transcript(old, conversation)}
        check_evaluable(conversation)
        criteria = select_criteria(active["data"], needs)
        new_answers, llm_meta = await run_llm(llm, active["data"], conversation, criteria)
        answers.update(new_answers)
        meta["llm"] = {k: v for k, v in llm_meta.items() if k not in ("warnings", "evaluated_criteria")}
        meta.update({k: llm_meta[k] for k in ("provider", "model", "tokens", "cost_usd", "prompt_version", "fallback_used") if k in llm_meta})
        criteria_versions.update(llm_meta.get("criteria_prompt_versions") or {})
        old_warnings += llm_meta["warnings"]
    meta["criteria_prompt_versions"] = criteria_versions
    meta["warnings"] = old_warnings

    new_id = await asyncio.to_thread(db.insert_evaluation, old["conversation_id"], active["id"], answers, meta, evaluation_id)
    meta_appeals = await asyncio.to_thread(carry_appeals, evaluation_id, new_id, active["data"], diff)
    logger.info(
        "Evaluation %s reapplied as %s: copied=%d llm_criteria=%s", evaluation_id, new_id, len(copied), needs or "none",
    )
    return {
        "evaluation_id": new_id, "parent_id": evaluation_id, "unchanged": False, "llm_called": bool(needs), "diff": diff,
        "appeals": meta_appeals,
    }


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


def _status_key(conversation_id: str) -> str | None:
    conv = db.get_conversation(conversation_id)
    return conv["id"] if conv else None


SKIP_ERRORS = (ChannelExcluded, NotEvaluable, NothingToReapply)
# ** Эти сбои не зависят от диалога, поэтому пакет сразу останавливается
STOP_BATCH_CODES = {"llm_unavailable", "llm_auth", "llm_model_not_found", "llm_quota"}


async def tracked(llm: LLMClient, conversation_id: str, action, source: str = "manual", job_id: str | None = None) -> int:
    # ** Единая точка записи статуса анализа: ручной запуск, пакет и воркер видны в UI одинаково
    key = await asyncio.to_thread(_status_key, conversation_id)
    if not key:
        return await action(llm, conversation_id)
    await asyncio.to_thread(db.start_status, key, source, job_id, llm.model)
    try:
        result = await action(llm, key)
    except SKIP_ERRORS as e:
        await asyncio.to_thread(db.finish_status, key, "skipped", getattr(e, "detail", None) or str(e))
        raise
    except HTTPException as e:
        await asyncio.to_thread(db.finish_status, key, "failed", str(e.detail))
        raise
    except Exception as e:
        await asyncio.to_thread(db.finish_status, key, "failed", f"{type(e).__name__}: {e}")
        raise
    await asyncio.to_thread(db.finish_status, key, "done")
    return result


async def run_batch(registry: LLMRegistry, job: dict[str, Any], conversation_ids: list[str], mode: str = "evaluate") -> None:
    # ** Воркеры берут id по порядку (очередь в выбранной сортировке); running ставится, только когда диалог ушёл в модель
    action = evaluate_conversation if mode == "evaluate" else reapply_conversation
    await asyncio.to_thread(db.queue_statuses, conversation_ids, "batch", job["id"])
    control = jobs.control(job["id"])
    pending = deque(conversation_ids)
    fatal: dict[str, Any] | None = None

    async def one(cid: str) -> None:
        nonlocal fatal
        job["current"].append(cid)
        task = asyncio.create_task(tracked(registry.active(), cid, action, "batch", job["id"]))
        control.tasks[cid] = task
        try:
            evaluation_id = await task
            job["done"].append({"conversation_id": cid, "evaluation_id": evaluation_id})
        except asyncio.CancelledError:
            # ! Отменили сам пакет (остановка сервера), а не диалог — пробрасываем дальше
            if not task.cancelled() or asyncio.current_task().cancelling():
                raise
            # * Пауза или остановка пользователем: диалог не обработан, processed не растёт
            if control.stopped:
                job["cancelled"].append(cid)
                await asyncio.to_thread(db.clear_statuses, [cid])
            else:
                pending.appendleft(cid)
                await asyncio.to_thread(db.requeue_status, cid)
            logger.info("Batch job %s: %s interrupted (%s)", job["id"], cid, "stop" if control.stopped else "pause")
            return
        except SKIP_ERRORS as e:
            job["skipped"].append({"conversation_id": cid, "reason": getattr(e, "detail", None) or str(e), "code": e.code})
        except HTTPException as e:
            failure = {"conversation_id": cid, "reason": e.detail, "code": getattr(e, "code", "internal")}
            job["failed"].append(failure)
            if failure["code"] in STOP_BATCH_CODES:
                fatal = failure
        except Exception as e:
            logger.exception("Batch job %s: conversation %s crashed", job["id"], cid)
            job["failed"].append({"conversation_id": cid, "reason": f"{type(e).__name__}: {e}", "code": "internal"})
        finally:
            job["current"].remove(cid)
            control.tasks.pop(cid, None)
        job["processed"] += 1

    async def worker() -> None:
        while True:
            # * На паузе воркер ждёт здесь; остановка будит его, чтобы выйти
            await control.resume.wait()
            if control.stopped or not pending:
                return
            cid = pending.popleft()
            if fatal:
                # ** Модель недоступна для всех: остальным диалогам незачем ждать повторы
                job["failed"].append({**fatal, "conversation_id": cid})
                await asyncio.to_thread(db.finish_status, cid, "failed", str(fatal["reason"]))
                job["processed"] += 1
                continue
            await one(cid)

    workers = registry.active().concurrency
    logger.info("Batch job %s (%s) started: %d conversations, %d workers", job["id"], mode, len(conversation_ids), workers)
    await asyncio.gather(*(worker() for _ in range(workers)))
    if control.stopped and pending:
        job["cancelled"].extend(pending)
        await asyncio.to_thread(db.clear_statuses, list(pending))
    jobs.finish(job)
    logger.info(
        "Batch job %s %s: done=%d failed=%d skipped=%d cancelled=%d",
        job["id"], "stopped" if job["stopped"] else "finished",
        len(job["done"]), len(job["failed"]), len(job["skipped"]), len(job["cancelled"]),
    )


QUEUE_ORDER: dict[QueueSort, tuple[str, bool]] = {
    "short_first": ("messages", False),
    "long_first": ("messages", True),
    "newest_first": ("imported_at", True),
    "oldest_first": ("imported_at", False),
}


def resolve_batch_ids(
    conversation_ids: list[str] | None, dataset: str | None, only_missing: bool, only_failed: bool = False
) -> list[str]:
    app = load_app_settings()
    items = list_conversations_with_scores(dataset) if app.include_errors else db.list_conversations(dataset)
    if conversation_ids is not None:
        wanted = set(conversation_ids)
        items = [i for i in items if i["id"] in wanted or i["source_id"] in wanted]
    if only_missing:
        # * Упавший диалог без оценки и так попадает в очередь; include_errors добавляет оценки с критериями без ответа
        items = [i for i in items if not i["last_evaluation_id"] or (app.include_errors and i["preliminary"])]
    if only_failed:
        items = [i for i in items if i["status"] == "failed"]
    # * Уже стоящие в очереди или в работе диалоги второй раз не ставим
    items = [i for i in items if i["status"] not in ("queued", "running")]
    key, reverse = QUEUE_ORDER[app.queue_sort]
    items = sorted(items, key=lambda i: i["seq"], reverse=reverse)
    return [i["id"] for i in sorted(items, key=lambda i: i[key], reverse=reverse)]


async def start_batch(
    registry: LLMRegistry, dataset: str | None, mode: str = "evaluate", only_missing: bool = False,
    conversation_ids: list[str] | None = None, only_failed: bool = False,
) -> dict[str, Any]:
    if jobs.current_job():
        raise JobAlreadyRunning()
    ids = await asyncio.to_thread(resolve_batch_ids, conversation_ids, dataset, only_missing, only_failed)
    job = jobs.create_job(mode, ids, registry.active().model)
    jobs.spawn(run_batch(registry, job, ids, mode))
    return job
