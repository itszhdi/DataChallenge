# * Выгрузка для сдачи организаторам: строго формат JSON 1.0 из приложения к гайду (results/<dev|prod>/results.json)
import json
import logging
from pathlib import Path
from typing import Any, Literal

from src import db
from src.config.settings import get_settings
from src.features.evaluation.service import summarize_latest

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0"
Target = Literal["dev", "prod"]
PROD_SIZE = 10

# ** Наши id критериев → коды организаторов; порядок = порядок в файле
CRITERION_CODES = {
    "c01_contact": "contact",
    "c02_needs": "discovery",
    "c03_ident": "identification",
    "c04_consult": "consultation",
    "c05_empathy": "empathy",
    "c06_flow": "dialogue",
    "c07_closing": "closure",
    "c08_gross": "critical",
}
BOOL = (True, False)
# * Допустимые значения по таблице организаторов; null = N/A
ALLOWED_VALUES: dict[str, tuple[Any, ...]] = {
    "contact": BOOL,
    "discovery": (*BOOL, None),
    "identification": (*BOOL, None),
    "consultation": (0, 5, 10, 15, 20, None),
    "empathy": BOOL,
    "dialogue": (0, 4, 7, 10),
    "closure": (*BOOL, None),
    "critical": BOOL,
}
SCALE_CODES = {"consultation", "dialogue"}
MODE_BY_PROVIDER = {"gemini": "external_api", "openai": "local"}


def _value_allowed(code: str, value: Any) -> bool:
    # ! В Python 0 == False: шкала и Да/Нет проверяются вместе с типом значения
    allowed = ALLOWED_VALUES[code]
    if value is None:
        return None in allowed
    if code in SCALE_CODES:
        return not isinstance(value, bool) and value in allowed
    return isinstance(value, bool)


def _value(item: dict[str, Any]) -> Any:
    if item["na"]:
        return None
    if item["type"] == "scale":
        return item["value"]
    return item["value"] == 1


def _criteria(score: dict[str, Any]) -> list[dict[str, Any]] | None:
    # * None — оценка неполная: для status=ok нужны все 8 критериев без ошибок
    by_id = {i["id"]: i for i in score["criteria"]}
    if any(cid not in by_id or by_id[cid]["status"] == "error" for cid in CRITERION_CODES):
        return None
    return [
        {
            "criterion_id": code,
            "value": _value(by_id[cid]),
            "rationale": by_id[cid].get("explanation") or "",
            "evidence_turns": sorted(set(by_id[cid].get("evidence_ids") or [])),
        }
        for cid, code in CRITERION_CODES.items()
    ]


def _error(conv: dict[str, Any], reason: str) -> dict[str, Any]:
    return {"conversation_id": conv["source_id"], "status": "error", "criteria": [], "score": None, "error": reason}


def _unevaluated_reason(conv: dict[str, Any]) -> str:
    if conv["status"] in ("failed", "skipped") and conv["status_error"]:
        return conv["status_error"]
    if conv["status"] in ("queued", "running"):
        return "Анализ не завершён к моменту выгрузки."
    return "Диалог не оценивался."


def _model(evaluations: list[dict[str, Any]], fallback: str) -> dict[str, str]:
    # * Режим и имя — по фактически использованным моделям, а не по текущей настройке
    providers = {(e["meta"] or {}).get("provider") for e in evaluations} - {None}
    names = sorted({(e["meta"] or {}).get("model") for e in evaluations} - {None})
    modes = {MODE_BY_PROVIDER.get(p, "external_api") for p in providers}
    mode = modes.pop() if len(modes) == 1 else ("hybrid" if modes else "external_api")
    return {"mode": mode, "name": ", ".join(names) or fallback}


def build_submission(dataset: str, team_name: str, fallback_model: str) -> dict[str, Any]:
    summary = summarize_latest(dataset)
    results, used = [], []
    for conv in db.list_conversations(dataset):
        s = summary.get(conv["id"])
        if not s:
            results.append(_error(conv, _unevaluated_reason(conv)))
            continue
        criteria = _criteria(s["score"])
        if criteria is None:
            results.append(_error(conv, "Модель не вернула ответ по части критериев, оценка неполная."))
            continue
        used.append(s["evaluation"])
        critical = next(c["value"] for c in criteria if c["criterion_id"] == "critical")
        results.append({
            "conversation_id": conv["source_id"],
            "status": "ok",
            "criteria": criteria,
            "score": {"final_score": s["score"]["total"], "critical_flag": critical},
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "team_name": team_name,
        "model": _model(used, fallback_model),
        "results": results,
    }


def _transcript_length(conv: dict[str, Any], evaluation: dict[str, Any] | None) -> int:
    # ** Номера реплик — по транскрипту, на котором оценивала модель; для сдачи он должен быть исходным
    snapshot = ((evaluation or {}).get("meta") or {}).get("transcript")
    return len(snapshot) if snapshot else len(conv["transcript"])


def validate_submission(submission: dict[str, Any], dataset: str, target: Target) -> dict[str, list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    convs = {c["source_id"]: c for c in (db.get_conversation(c["id"]) for c in db.list_conversations(dataset))}
    latest = {e["conversation_id"]: e for e in db.latest_evaluations(dataset)}
    results = submission["results"]
    ids = [r["conversation_id"] for r in results]

    if not results:
        errors.append("В выгрузке нет ни одной записи.")
    if len(ids) != len(set(ids)):
        errors.append("Есть повторяющиеся conversation_id.")
    if set(ids) != set(convs):
        errors.append(f"conversation_id не совпадают с импортированным набором {dataset}.")
    if not submission["team_name"].strip():
        warnings.append("Не указано название команды (team_name).")
    if target == "prod" and len(results) != PROD_SIZE:
        warnings.append(f"В prod должно быть ровно {PROD_SIZE} записей, сейчас {len(results)}.")

    for r in results:
        cid = r["conversation_id"]
        if r["status"] == "error":
            warnings.append(f"{cid}: status=error — {r['error']}")
            continue
        conv = convs.get(cid)
        evaluation = latest.get(conv["id"]) if conv else None
        if ((evaluation or {}).get("meta") or {}).get("transcript_source") == "asr":
            warnings.append(f"{cid}: оценён по распознанному транскрипту, номера реплик могут не совпасть с API.")
        turns = _transcript_length(conv, evaluation) if conv else 0
        codes = [c["criterion_id"] for c in r["criteria"]]
        if sorted(codes) != sorted(CRITERION_CODES.values()):
            errors.append(f"{cid}: нужны все 8 критериев ровно по одному разу, сейчас {codes}.")
        for c in r["criteria"]:
            if c["criterion_id"] not in ALLOWED_VALUES:
                errors.append(f"{cid}: неизвестный код критерия {c['criterion_id']}.")
            elif not _value_allowed(c["criterion_id"], c["value"]):
                if c["criterion_id"] == "contact" and c["value"] is None:
                    warnings.append(f"{cid}: contact = null (N/A для звонка), а формат допускает только true/false.")
                else:
                    errors.append(f"{cid}: недопустимое значение {c['criterion_id']} = {c['value']!r}.")
            if any(not isinstance(t, int) or not 1 <= t <= turns for t in c["evidence_turns"]):
                errors.append(f"{cid}: {c['criterion_id']} ссылается на реплику вне транскрипта (1–{turns}).")
        score = r["score"]
        critical = next((c["value"] for c in r["criteria"] if c["criterion_id"] == "critical"), None)
        if score["critical_flag"] is not critical:
            errors.append(f"{cid}: critical_flag не совпадает с критерием critical.")
        if score["final_score"] is not None and not 0 <= score["final_score"] <= 100:
            errors.append(f"{cid}: final_score вне диапазона 0–100.")

    counts = {"ok": sum(r["status"] == "ok" for r in results), "error": sum(r["status"] == "error" for r in results)}
    return {"errors": errors, "warnings": warnings, "counts": counts}


def submission_path(target: Target) -> Path:
    return get_settings().results_dir / target / "results.json"


def save_submission(submission: dict[str, Any], target: Target) -> Path:
    path = submission_path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(submission, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # ** В Docker файл создаётся от root: открываем его на запись, чтобы пользователь мог править и удалять файл на хосте
    path.parent.chmod(0o777)
    path.chmod(0o666)
    logger.info("Submission saved: %s (%d results)", path, len(submission["results"]))
    return path
