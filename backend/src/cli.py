"""Командная строка для сверки оценок CQA с ручным эталоном."""

import argparse
import asyncio
import csv
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from src import db
from src.config.settings import get_settings
from src.features.evaluation.service import run_llm
from src.features.settings.service import load_app_settings
from src.llm.client import LLMRegistry
from src.llm.prompts import select_criteria


def read_golden(path: Path, checklist: dict[str, Any]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"conversation_id", "criterion_id", "expected"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"CSV должен содержать колонки: {', '.join(sorted(required))}")
        rows = list(reader)

    criteria = {c["id"]: c for c in checklist["criteria"]}
    seen: set[tuple[str, str]] = set()
    for row_no, row in enumerate(rows, start=2):
        cid, criterion_id, expected = (row.get(k, "").strip() for k in ("conversation_id", "criterion_id", "expected"))
        if not cid or criterion_id not in criteria or not expected:
            raise ValueError(f"Строка {row_no}: пустое поле или неизвестный criterion_id {criterion_id!r}")
        key = (cid, criterion_id)
        if key in seen:
            raise ValueError(f"Строка {row_no}: повтор {cid}/{criterion_id}")
        seen.add(key)
        criterion = criteria[criterion_id]
        normalized = expected.lower()
        if normalized == "na":
            if not criterion.get("na_allowed"):
                raise ValueError(f"Строка {row_no}: N/A не разрешён для {criterion_id}")
        elif criterion["type"] == "scale":
            try:
                value = int(normalized)
            except ValueError as e:
                raise ValueError(f"Строка {row_no}: для шкалы ожидается числовая ступень") from e
            steps = {int(s["value"]) for s in criterion.get("scale", [])}
            if value not in steps:
                raise ValueError(f"Строка {row_no}: {value} не входит в шкалу {criterion_id}: {sorted(steps)}")
        elif normalized not in ("yes", "no"):
            raise ValueError(f"Строка {row_no}: для бинарного/флагового критерия ожидается yes, no или na")
        row["conversation_id"], row["criterion_id"], row["expected"] = cid, criterion_id, normalized
    return rows


def actual_label(answer: dict[str, Any] | None, criterion: dict[str, Any]) -> str:
    if not answer or answer.get("status") != "ok":
        return "ERROR"
    if answer.get("na"):
        return "na"
    value = answer.get("value")
    if criterion["type"] == "scale":
        return str(value)
    return "yes" if value == 1 else "no"


def _golden_rows(
    rows: list[dict[str, str]], checklist: dict[str, Any], limit: int | None
) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["conversation_id"]].append(row)
    # * --limit: быстрая сверка на первых N диалогах эталона, чтобы не тратить квоту на весь набор
    if limit:
        grouped = defaultdict(list, dict(list(grouped.items())[:limit]))
    missing = [cid for cid in grouped if db.get_conversation(cid) is None]
    if missing:
        raise ValueError("Диалоги отсутствуют в БД; сначала импортируй датасет: " + ", ".join(missing))
    return grouped


def _compare(
    conversation_id: str, expected_rows: list[dict[str, str]], answers: dict[str, Any], criteria_by_id: dict[str, Any]
) -> list[tuple[str, str, str, str, str]]:
    out = []
    for row in expected_rows:
        cid = row["criterion_id"]
        actual = actual_label(answers.get(cid), criteria_by_id[cid])
        explanation = (answers.get(cid) or {}).get("explanation", "").replace("\n", " ")
        out.append((conversation_id, cid, row["expected"], actual, explanation))
    return out


async def compare_golden(
    rows: list[dict[str, str]], checklist: dict[str, Any], profile: str | None = None, limit: int | None = None
) -> int:
    criteria_by_id = {c["id"]: c for c in checklist["criteria"]}
    grouped = _golden_rows(rows, checklist, limit)
    settings = get_settings()
    # ** Профиль как у сервера (настройка llm_profile), если не задан явно
    registry = LLMRegistry(settings, profile or load_app_settings().llm_profile)
    llm = registry.active()
    results: list[tuple[str, str, str, str, str]] = []
    try:
        for conversation_id, expected_rows in grouped.items():
            conversation = db.get_conversation(conversation_id)
            selected = select_criteria(checklist, [r["criterion_id"] for r in expected_rows])
            answers, _meta = await run_llm(llm, checklist, conversation, selected)
            results += _compare(conversation_id, expected_rows, answers, criteria_by_id)
    finally:
        await registry.close()
    return report_golden(results, len(grouped), f"{llm.provider}/{llm.model} (профиль {registry.active_name})")


def compare_stored(rows: list[dict[str, str]], checklist: dict[str, Any], limit: int | None = None) -> int:
    # ** Сверка с уже сохранёнными оценками (последняя по диалогу, до апелляций): без вызова модели и без затрат
    criteria_by_id = {c["id"]: c for c in checklist["criteria"]}
    grouped = _golden_rows(rows, checklist, limit)
    results: list[tuple[str, str, str, str, str]] = []
    models: set[str] = set()
    for conversation_id, expected_rows in grouped.items():
        conversation = db.get_conversation(conversation_id)
        evaluation_id = db.latest_evaluation_id(conversation["id"])
        if not evaluation_id:
            raise ValueError(f"У диалога {conversation_id} нет оценки; сначала оцените набор")
        evaluation = db.get_evaluation(evaluation_id)
        models.add((evaluation["meta"] or {}).get("model") or "?")
        results += _compare(conversation_id, expected_rows, evaluation["answers"], criteria_by_id)
    return report_golden(results, len(grouped), f"сохранённые оценки ({', '.join(sorted(models))})")


def report_golden(results: list[tuple[str, str, str, str, str]], dialogs: int, source: str) -> int:
    grouped_results: dict[str, list[tuple[str, str, str, str, str]]] = defaultdict(list)
    for result in results:
        grouped_results[result[1]].append(result)
    print(f"\nМодель: {source}")
    print(f"Сверено ответов: {len(results)} по {dialogs} диалогам\n")
    print(f"{'Критерий':<20} {'Совпало':>9} {'Всего':>7} {'Точность':>10}")
    print("-" * 50)
    for cid in sorted(grouped_results):
        items = grouped_results[cid]
        correct = sum(expected == actual for _, _, expected, actual, _ in items)
        print(f"{cid:<20} {correct:>9} {len(items):>7} {correct / len(items):>9.1%}")
    correct = sum(expected == actual for _, _, expected, actual, _ in results)
    print("-" * 50)
    print(f"{'Итого':<20} {correct:>9} {len(results):>7} {correct / len(results):>9.1%}")

    mismatches = [r for r in results if r[2] != r[3]]
    if mismatches:
        print("\nРасхождения (эталон → модель):")
        for conversation_id, cid, expected, actual, explanation in mismatches:
            print(f"- {conversation_id} / {cid}: {expected} → {actual}. {explanation}")
    return 0 if not mismatches else 1


def print_stats(dataset: str | None) -> int:
    # * Время и стоимость по последним оценкам набора: для таблицы «Точность и стоимость» в README
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in db.latest_evaluations(dataset):
        meta = e["meta"] or {}
        by_model[f"{meta.get('profile', '?')} · {meta.get('model', '?')}"].append(meta)
    if not by_model:
        print("Оценок нет")
        return 1
    print(f"{'Профиль · модель':<34} {'Оценок':>7} {'Ср. время, с':>13} {'Ср. токены in/out':>18} {'Ср. $':>10} {'Всего $':>9}")
    for name, metas in sorted(by_model.items()):
        n = len(metas)
        sec = sum(m.get("total_seconds") or m.get("seconds") or 0 for m in metas) / n
        tok_in = sum((m.get("tokens") or {}).get("prompt_tokens", 0) for m in metas) / n
        tok_out = sum((m.get("tokens") or {}).get("completion_tokens", 0) for m in metas) / n
        cost = sum(m.get("cost_usd") or 0 for m in metas)
        print(f"{name:<34} {n:>7} {sec:>13.1f} {f'{tok_in:.0f}/{tok_out:.0f}':>18} {cost / n:>10.5f} {cost:>9.4f}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="cqa", description="Инструменты CQA")
    subparsers = parser.add_subparsers(dest="command", required=True)
    golden_parser = subparsers.add_parser("golden", help="сравнить ответы модели с CSV-эталоном")
    golden_parser.add_argument("csv", type=Path, help="CSV с conversation_id,criterion_id,expected")
    golden_parser.add_argument("--profile", choices=["gemini", "luna", "local"], help="профиль модели (по умолчанию из настроек)")
    golden_parser.add_argument("--limit", type=int, help="сверить только первые N диалогов")
    golden_parser.add_argument("--stored", action="store_true", help="сверить с сохранёнными оценками, без вызова модели")
    stats_parser = subparsers.add_parser("stats", help="время, токены и стоимость последних оценок")
    stats_parser.add_argument("--dataset", help="набор, например DEV (по умолчанию все)")
    args = parser.parse_args()

    if args.command == "stats":
        db.init_db()
        raise SystemExit(print_stats(args.dataset))

    if args.command == "golden":
        try:
            db.init_db()
            db.seed_default_checklist(get_settings().default_checklist_path)
            checklist = db.get_active_checklist()
            if not checklist:
                raise ValueError("Нет активного чек-листа")
            rows = read_golden(args.csv, checklist["data"])
            if args.stored:
                raise SystemExit(compare_stored(rows, checklist["data"], args.limit))
            raise SystemExit(asyncio.run(compare_golden(rows, checklist["data"], args.profile, args.limit)))
        except (OSError, ValueError) as e:
            print(f"Ошибка: {e}", file=sys.stderr)
            raise SystemExit(2) from e


if __name__ == "__main__":
    main()
