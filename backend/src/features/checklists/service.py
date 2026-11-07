import hashlib
import json
import logging
from typing import Any

from src import db
from src.config.settings import get_settings
from src.features.checklists.schemas import ChecklistData

logger = logging.getLogger(__name__)

# ** Поля, влияющие на ответ модели. Вес, секция и название сюда НЕ входят — их смена не требует LLM
FINGERPRINT_FIELDS = ("type", "rule", "na_allowed", "na_condition", "scale", "guidance", "examples_pass", "examples_fail", "flag_types")


def fingerprint(criterion: dict[str, Any]) -> str:
    payload = {k: criterion.get(k) for k in FINGERPRINT_FIELDS}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def diff_checklists(old: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any]:
    old_by_id = {c["id"]: c for c in (old or {}).get("criteria", [])}
    new_by_id = {c["id"]: c for c in new["criteria"]}
    result: dict[str, list[str]] = {"same": [], "weight_only": [], "changed": [], "new": [], "removed": []}
    for cid, c in new_by_id.items():
        prev = old_by_id.get(cid)
        if prev is None:
            result["new"].append(cid)
        elif fingerprint(prev) != fingerprint(c):
            result["changed"].append(cid)
        elif any(prev.get(k) != c.get(k) for k in ("weight", "section", "title")):
            result["weight_only"].append(cid)
        else:
            result["same"].append(cid)
    result["removed"] = [cid for cid in old_by_id if cid not in new_by_id]
    result["needs_llm"] = result["changed"] + result["new"]
    return result


def load_default_checklist() -> dict[str, Any]:
    # * Эталон организаторов: файл, а не первая версия в БД — её могли изменить
    return json.loads(get_settings().default_checklist_path.read_text(encoding="utf-8"))


def save_checklist(data: ChecklistData, comment: str) -> dict[str, Any]:
    previous = db.get_active_checklist()
    saved = db.insert_checklist(data.model_dump(), comment=comment)
    diff = diff_checklists(previous["data"] if previous else None, saved["data"])
    logger.info("Checklist v%s saved, diff: needs_llm=%s removed=%s", saved["version"], diff["needs_llm"], diff["removed"])
    return {"checklist": saved, "diff": diff}


def update_weights(weights: dict[str, float], comment: str) -> dict[str, Any]:
    active = db.get_active_checklist()
    if not active:
        raise LookupError("Нет активного чек-листа")
    data = active["data"]
    ids = {c["id"] for c in data["criteria"]}
    unknown = set(weights) - ids
    if unknown:
        raise ValueError(f"неизвестные критерии: {sorted(unknown)}")
    if any(w < 0 for w in weights.values()):
        raise ValueError("вес не может быть отрицательным")
    for c in data["criteria"]:
        if c["id"] in weights:
            c["weight"] = weights[c["id"]]
    return save_checklist(ChecklistData.model_validate(data), comment or f"Изменены веса: {weights}")
