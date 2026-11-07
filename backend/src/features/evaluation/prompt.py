# * Промпт и JSON-схема собираются из конфигурации чек-листа — ничего не захардкожено под 8 критериев
import json
from typing import Any

from src.features.evaluation.timing import SPEAKER_RU, format_offset, timing_facts, with_offsets

LANG_RU = {"RU": "русский", "KZ": "казахский", "EN": "английский"}

SYSTEM_PROMPT = """Ты — эксперт службы контроля качества (QA) контакт-центра брокерской компании Freedom.
Ты оцениваешь работу ОПЕРАТОРА в диалоге с клиентом строго по чек-листу.

Правила:
1. Оцениваются только действия оператора. Реплики бота и системные события — контекст; системное сообщение может быть доказательством (например, «клиент идентифицирован», «чат закрыт»).
2. Диалог может быть на русском, казахском или английском. Объяснения пиши ВСЕГДА на русском, 1–2 предложения.
3. «Нет» — действие было нужно, но оператор его пропустил или выполнил неправильно. N/A — критерий неприменим по своему условию. N/A ставь только там, где он разрешён, и только если условие неприменимости выполнено — объясни, какое именно.
4. evidence_ids — только номера реплик из транскрипта (#N), подтверждающих ответ. Для пропущенного действия укажи в checked_range проверенный участок («#2–#5») и в объяснении — где действие ожидалось и чего не хватило. Если всё подтверждено конкретными репликами, checked_range может быть пустой строкой.
5. Не додумывай: опирайся только на текст транскрипта и вычисленные факты о времени. Теги и вложения в оценку не входят.
6. Порядок рассуждения: сначала найди доказательства, затем сформулируй объяснение, затем выставь оценку.
7. Пример хорошего обоснования: «Завершение — Нет. После ответа на вопрос оператор закрыл чат без прощания. Основание — последняя реплика оператора (#7) и сообщение о закрытии чата (#8).»

Верни ТОЛЬКО JSON по заданной схеме: по одному объекту на каждый критерий."""


def _answer_hint(c: dict[str, Any]) -> str:
    if c["type"] == "binary":
        return "value: 1 = Да, 0 = Нет."
    if c["type"] == "flag":
        types = ", ".join(c.get("flag_types") or [])
        return f"value: 1 = нарушение выявлено, 0 = не выявлено. flags: типы выявленных нарушений ({types}), пустой список если 0."
    steps = ", ".join(str(s["value"]) for s in c.get("scale", []))
    return f"value: одна из ступеней шкалы ({steps})."


def render_criterion(c: dict[str, Any]) -> str:
    lines = [f"### {c['id']} — {c.get('title', '')} [{c['type']}]", f"Правило: {c.get('rule', '')}"]
    if c["type"] == "scale":
        lines.append("Шкала:")
        lines += [f"  {s['value']} — {s.get('description', '')}" for s in sorted(c["scale"], key=lambda s: -s["value"])]
    lines.append(f"N/A: {c['na_condition']} (тогда na=true)" if c.get("na_allowed") else "N/A не допускается.")
    if c.get("guidance"):
        lines.append(f"Пояснение: {c['guidance']}")
    for ex in c.get("examples_pass") or []:
        lines.append(f"Пример «Да»: {ex}")
    for ex in c.get("examples_fail") or []:
        lines.append(f"Пример «Нет»: {ex}")
    lines.append(f"Как отвечать: {_answer_hint(c)}")
    return "\n".join(lines)


def render_timing(facts: dict[str, Any]) -> str:
    thr = facts["threshold_sec"]
    lines = [f"Порог первой реакции: {thr} с ({thr // 60} мин)."]
    if facts["first_response_sec"] is None:
        lines.append("Первая реакция оператора на клиента: не определена (нет ответа оператора после реплики клиента или нет времени).")
    else:
        verdict = "ПРЕВЫШЕН" if facts["first_response_exceeded"] else "не превышен"
        lines.append(
            f"Первая реакция оператора: #{facts['first_operator_reply_index']} через {facts['first_response_sec']:.0f} с "
            f"после первой реплики клиента #{facts['first_client_index']} — порог {verdict}."
        )
    if facts["long_pauses"]:
        pauses = "; ".join(f"#{p['client_index']}→#{p['operator_index']}: {p['seconds']:.0f} с" for p in facts["long_pauses"])
        lines.append(f"Паузы клиент→оператор дольше порога: {pauses}.")
    else:
        lines.append("Пауз клиент→оператор дольше порога нет.")
    return "\n".join(lines)


def render_transcript(transcript: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"[#{m['index']}] {format_offset(m['offset_sec'])} {SPEAKER_RU.get(m['speaker'], m['speaker'])}: {m.get('text', '')}"
        for m in with_offsets(transcript)
    )


def select_criteria(checklist: dict[str, Any], criteria_ids: list[str] | None = None) -> list[dict[str, Any]]:
    if criteria_ids is None:
        return list(checklist["criteria"])
    wanted = set(criteria_ids)
    return [c for c in checklist["criteria"] if c["id"] in wanted]


def build_messages(
    checklist: dict[str, Any], conversation: dict[str, Any], criteria: list[dict[str, Any]]
) -> list[dict[str, str]]:
    threshold = int(checklist.get("settings", {}).get("first_response_threshold_sec", 180))
    lang = conversation.get("language") or "?"
    user = "\n\n".join([
        f"Канал: {conversation.get('channel') or '?'}. Язык клиента: {LANG_RU.get(lang, lang)} ({lang}).",
        "## Чек-лист\n" + "\n\n".join(render_criterion(c) for c in criteria),
        "## Факты о времени (вычислены кодом)\n" + render_timing(timing_facts(conversation["transcript"], threshold)),
        "## Транскрипт\n" + render_transcript(conversation["transcript"]),
    ])
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def criterion_schema(c: dict[str, Any]) -> dict[str, Any]:
    # ** Порядок полей важен: доказательства → объяснение → оценка (модель генерирует по порядку)
    props: dict[str, Any] = {
        "evidence_ids": {"type": "array", "items": {"type": "integer"}},
        "checked_range": {"type": "string"},
        "explanation": {"type": "string"},
    }
    if c.get("na_allowed"):
        props["na"] = {"type": "boolean"}
    if c["type"] == "scale":
        props["value"] = {"type": "integer", "enum": [int(s["value"]) for s in c["scale"]]}
    else:
        props["value"] = {"type": "integer", "enum": [0, 1]}
    if c["type"] == "flag" and c.get("flag_types"):
        props["flags"] = {"type": "array", "items": {"type": "string", "enum": list(c["flag_types"])}}
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def build_schema(criteria: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {c["id"]: criterion_schema(c) for c in criteria},
        "required": [c["id"] for c in criteria],
        "additionalProperties": False,
    }


def preview(checklist: dict[str, Any], conversation: dict[str, Any], criteria_ids: list[str] | None = None) -> dict[str, Any]:
    # * Для отладки: промпт и схема без вызова модели
    criteria = select_criteria(checklist, criteria_ids)
    messages = build_messages(checklist, conversation, criteria)
    return {"messages": messages, "schema": build_schema(criteria), "chars": len(json.dumps(messages, ensure_ascii=False))}
