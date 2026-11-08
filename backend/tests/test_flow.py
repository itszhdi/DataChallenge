# * Сквозной сценарий защиты без сети: модель подменена, проверяем что LLM зовётся только когда нужно
import asyncio
import json
from pathlib import Path

import httpx
import pytest

from src.config.settings import get_settings
from src.features.evaluation.service import resolve_batch_ids
from src.llm.client import LLMClient, LLMError
from src.llm.prompts import PROMPT_VERSION
from src.main import app


SAMPLE = Path(__file__).parent / "sample_data.json"


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "db_path", tmp_path / "test.sqlite3")
    monkeypatch.setattr(get_settings(), "worker_interval_sec", 0.01)
    monkeypatch.setattr(get_settings(), "exclude_channels", ["voice call"])
    monkeypatch.setattr(get_settings(), "results_dir", tmp_path / "results")
    calls: list[list[str]] = []

    async def fake_complete(self, messages, schema):
        calls.append(list(schema["properties"]))
        if "segments" in schema["properties"]:
            segments = [
                {"start": "00:00", "speaker": "operator", "text": "Freedom Broker, good morning, my name is John."},
                {"start": "00:06", "speaker": "client", "text": "Hi, what are the trading hours for US stocks?"},
                {"start": "00:15", "speaker": "operator", "text": "From 19:30 to 02:00 Astana time. Anything else? Goodbye!"},
            ]
            return {"segments": segments}, {"provider": "fake", "model": "fake-asr", "tokens": {}, "cost_usd": 0}
        out = {}
        for cid, s in schema["properties"].items():
            p = s["properties"]
            out[cid] = {"evidence_ids": [1], "checked_range": "", "explanation": "ok", "value": max(p["value"]["enum"]) if cid != "c08_gross" else 0}
            if "na" in p:
                out[cid]["na"] = cid == "c02_needs"
            if "flags" in p:
                out[cid]["flags"] = []
        return out, {"provider": "fake", "model": "fake", "tokens": {}, "cost_usd": 0}

    monkeypatch.setattr(LLMClient, "complete_json", fake_complete)
    async with app.router.lifespan_context(app) as state:
        async def asgi(scope, receive, send):
            scope["state"] = dict(state)
            await app(scope, receive, send)

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=asgi), base_url="http://test") as c:
            c.llm_calls = calls
            yield c


async def test_full_flow(client):
    r = await client.post("/api/datasets/upload", files={"file": SAMPLE.open("rb")})
    assert r.json()["imported"] == 3

    # ! Реальные звонки не отправляются в модель
    assert (await client.post("/api/evaluate", json={"conversation_id": "s-en-003"})).status_code == 403

    card = (await client.post("/api/evaluate", json={"conversation_id": "s-ru-001"})).json()
    eid = card["evaluation"]["id"]
    assert card["final"]["total"] == 100.0 and len(client.llm_calls) == 1
    assert card["meta"]["prompt_version"] == PROMPT_VERSION
    assert set(card["meta"]["criteria_prompt_versions"].values()) == {PROMPT_VERSION}

    # * Смена веса: новая версия + пересчёт без модели
    r = (await client.patch("/api/checklists/active/weights", json={"weights": {"c01_contact": 30}})).json()
    assert r["diff"]["weight_only"] == ["c01_contact"] and r["reapplied"]["done"] == 1
    assert len(client.llm_calls) == 1

    # * Изменили формулировку одного критерия и добавили новый — модель спрашивается только по ним
    data = (await client.get("/api/checklists/active")).json()["data"]
    data["criteria"][1]["rule"] = "Да — оператор задал уточняющий вопрос."
    data["criteria"].append({"id": "c09_offer", "section": "flow", "title": "Доп. продукт", "type": "binary",
                             "weight": 5, "rule": "Да — оператор предложил подходящий продукт."})
    r = (await client.post("/api/checklists", json={"data": data, "comment": "защита"})).json()
    assert sorted(r["diff"]["needs_llm"]) == ["c02_needs", "c09_offer"]

    latest = (await client.get("/api/conversations/s-ru-001")).json()["evaluations"][0]["id"]
    card = (await client.post(f"/api/evaluations/{latest}/reapply")).json()
    assert sorted(client.llm_calls[-1]) == ["c02_needs", "c09_offer"]
    assert card["evaluation"]["parent_id"] == latest
    assert card["meta"]["prompt_version"] == PROMPT_VERSION
    assert set(card["meta"]["criteria_prompt_versions"].values()) == {PROMPT_VERSION}

    # * Апелляция: c04 20 -> 10 (вес 20 из применимых)
    new_eid = card["evaluation"]["id"]
    appeal = (await client.post(f"/api/evaluations/{new_eid}/appeals", json={"criterion_id": "c04_consult", "comment": "не всё"})).json()
    queue = (await client.get("/api/appeals", params={"status": "open"})).json()
    assert queue[0]["id"] == appeal["id"] and queue[0]["fragment"]
    bad = await client.post(f"/api/appeals/{appeal['id']}/resolve", json={"decision": "changed", "reason": "x", "value": 13})
    assert bad.status_code == 422
    r = (await client.post(f"/api/appeals/{appeal['id']}/resolve", json={"decision": "changed", "reason": "Пропущен второй вопрос", "value": 10})).json()
    assert r["original_total"] == 100.0 and r["final_total"] < 100.0

    analytics = (await client.get("/api/analytics")).json()
    assert analytics["evaluated"] == 1 and analytics["worst"][0]["total"] == r["final_total"]
    exported = (await client.get("/api/export", params={"dataset": "SAMPLE", "team_name": "test"})).json()
    assert exported["schema_version"] == "1.1"
    assert exported["results"][0]["prompt_version"] == PROMPT_VERSION
    assert set(exported["results"][0]["criteria_prompt_versions"].values()) == {PROMPT_VERSION}
    assert eid != new_eid
    # * Дашборд: апелляция считается один раз, диалог попадает в drill-down
    board = (await client.get("/api/analytics/dashboard")).json()
    assert board["summary"]["total_evaluated"] == 1
    assert board["appeals"] == {"filed": 1, "open": 0, "changed": 1, "changed_percent": 100.0}
    assert sum(b["count"] for b in board["distribution"]) == 1
    row = board["dialogs"][0]
    assert row["conversation_id"] == "s-ru-001" and row["id"] == "SAMPLE:s-ru-001" and row["criteria"]["c04_consult"]["percent"] == 50.0
    assert row["weak_criterion"] == "c04_consult" and board["bottleneck"]["criterion_id"] == "c04_consult"
    assert "c08_gross" not in {c["id"] for c in board["criteria_averages"]}


async def test_messy_import_and_id_collision(client):
    import json

    records = [
        {"conversation_id": "s-ru-001", "channel": "agent chat", "language": "RU", "transcript": [
            {"timestamp": None, "speaker": "client", "text": None, "file": {"type": "image", "name": "a.png"}},
            {"timestamp": 12, "speaker": "operator", "text": "Здравствуйте!"},
            {"speaker": "robot", "text": ["?"]},
        ]},
        {"conversation_id": "empty-1", "transcript": []},
        {"conversation_id": "no-op", "transcript": [{"speaker": "client", "text": "алло"}]},
        {"channel": "agent chat", "transcript": []},
    ]
    await client.post("/api/datasets/upload", files={"file": SAMPLE.open("rb")})
    r = (await client.post("/api/datasets/upload?dataset=OTHER", files={"file": ("x.json", json.dumps(records))})).json()
    assert r["imported"] == 3 and r["skipped"] == 1 and r["warnings"]

    # ** Одинаковый id в разных наборах — две разные записи
    sample = (await client.get("/api/conversations/SAMPLE:s-ru-001")).json()
    other = (await client.get("/api/conversations/OTHER:s-ru-001")).json()
    assert len(sample["transcript"]) == 9 and len(other["transcript"]) == 3 and other["source_id"] == "s-ru-001"

    for cid in ("OTHER:empty-1", "OTHER:no-op"):
        assert (await client.post("/api/evaluate", json={"conversation_id": cid})).status_code == 422
    assert (await client.post("/api/evaluate", json={"conversation_id": "OTHER:s-ru-001"})).status_code == 200
    assert client.llm_calls
    export = (await client.get("/api/export", params={"dataset": "OTHER"})).json()
    assert {r["conversation_id"]: r["status"] for r in export["results"]} == {"s-ru-001": "ok", "empty-1": "skipped", "no-op": "skipped"}
    assert export["counts"] == {"ok": 1, "skipped": 2}

    # * Экспорт всех статусов в файл: звонок исключён, неоценённый KZ — pending
    r = await client.get("/api/export", params={"dataset": "SAMPLE", "download": True})
    assert r.headers["content-disposition"].startswith('attachment; filename="SAMPLE_') and len(r.json()["results"]) == 3
    saved = (await client.post("/api/export/save", params={"dataset": "../x", "team_name": "t"})).json()
    assert Path(saved["path"]).parent == get_settings().results_dir and saved["file"].startswith("x_")
    saved = (await client.post("/api/export/save", params={"dataset": "SAMPLE", "team_name": "t"})).json()
    data = json.loads(Path(saved["latest"]).read_text(encoding="utf-8"))
    assert {r["conversation_id"]: r["status"] for r in data["results"]} == {"s-ru-001": "pending", "s-kz-002": "pending", "s-en-003": "excluded"}


async def test_appeals_survive_reevaluation_and_threshold_change(client):
    await client.post("/api/datasets/upload", files={"file": SAMPLE.open("rb")})
    eid1 = (await client.post("/api/evaluate", json={"conversation_id": "s-ru-001"})).json()["evaluation"]["id"]
    await client.post(f"/api/evaluations/{eid1}/appeals", json={"criterion_id": "c04_consult", "comment": "открытая"})
    done = (await client.post(f"/api/evaluations/{eid1}/appeals", json={"criterion_id": "c05_empathy", "comment": "решённая"})).json()
    await client.post(f"/api/appeals/{done['id']}/resolve", json={"decision": "changed", "reason": "сухо", "value": 0})

    # * Полная переоценка: открытая переехала, решение сохранилось и влияет на итог
    card = (await client.post("/api/evaluate", json={"conversation_id": "s-ru-001"})).json()
    by_crit = {a["criterion_id"]: a for a in card["appeals"]}
    assert by_crit["c04_consult"]["status"] == "open" and by_crit["c05_empathy"]["decision"] == "changed"
    assert card["final"]["total"] < card["original"]["total"]

    # ** Смена порога → переоценка c06 (uses_timing); смена названия c05 → тоже к модели, а его решение переоткрывается
    data = (await client.get("/api/checklists/active")).json()["data"]
    data["settings"]["first_response_threshold_sec"] = 120
    data["criteria"][4]["title"] = "Эмпатия"
    r = (await client.post("/api/checklists", json={"data": data, "comment": "порог"})).json()
    assert r["diff"]["threshold_changed"] and sorted(r["diff"]["needs_llm"]) == ["c05_empathy", "c06_flow"]

    card = (await client.post(f"/api/evaluations/{card['evaluation']['id']}/reapply")).json()
    assert sorted(client.llm_calls[-1]) == ["c05_empathy", "c06_flow"]
    assert card["reapply"]["appeals"] == {"moved": 1, "copied": 0, "reopened": 1}
    assert all(a["status"] == "open" for a in card["appeals"]) and "пересмотрите" in card["appeals"][-1]["comment"]



async def test_settings_order_and_auto_evaluation(client):
    assert (await client.get("/api/settings")).json()["request_delay_ms"] == 500
    settings = {"queue_sort": "long_first", "only_missing": True, "include_errors": False, "concurrency": 3,
                "request_delay_ms": 0, "auto_evaluate_on_import": True, "default_group_id": "CTRL"}
    saved = (await client.put("/api/settings", json=settings)).json()
    assert {k: saved[k] for k in settings} == settings and "profiles" in saved
    assert (await client.put("/api/settings", json={**settings, "concurrency": 9})).status_code == 422

    # * Автооценка запускается импортом, очередь идёт от длинных диалогов
    imported = (await client.post("/api/datasets/upload", files={"file": SAMPLE.open("rb")})).json()
    assert imported["job_id"]
    for _ in range(50):
        job = (await client.get(f"/api/jobs/{imported['job_id']}")).json()
        if job["status"] == "finished":
            break
        await asyncio.sleep(0.01)
    assert job["status"] == "finished" and len(job["done"]) == 2 and len(job["skipped"]) == 1

    rows = (await client.get("/api/conversations")).json()
    expected = [r["id"] for r in sorted(rows, key=lambda r: -r["messages"])]
    assert resolve_batch_ids(None, None, only_missing=False) == expected


async def test_default_checklist_and_source_check(client, monkeypatch):
    default = (await client.get("/api/checklists/default")).json()
    assert len(default["criteria"]) == 8

    async def fake_fetch(group_id, url=None):
        return {"isSuccess": True, "data": {"dataset_group_id": group_id, "records": [{}, {}]}}

    monkeypatch.setattr("src.features.datasets.service.fetch_payload", fake_fetch)
    check = (await client.get("/api/datasets/check", params={"group_id": "CTRL"})).json()
    assert check == {"dataset": "CTRL", "total_records": 2}
    assert (await client.get("/api/datasets")).json() == []


async def wait_job(client, job_id):
    for _ in range(100):
        job = (await client.get(f"/api/jobs/{job_id}")).json()
        if job["status"] == "finished":
            return job
        await asyncio.sleep(0.01)
    raise AssertionError("job did not finish")


async def test_batch_stops_when_model_is_unavailable(client, monkeypatch):
    calls = []

    async def down(self, messages, schema):
        calls.append(1)
        raise LLMError("connection refused", "llm_unavailable")

    monkeypatch.setattr(LLMClient, "complete_json", down)
    await client.post("/api/datasets/upload", files={"file": SAMPLE.open("rb")})
    started = (await client.post("/api/evaluate/batch", json={"dataset": None})).json()
    job = await wait_job(client, started["id"])
    assert len(calls) == 1 and {f["code"] for f in job["failed"]} == {"llm_unavailable"}
    assert job["processed"] == job["total"] == 3 and job["current"] == []


async def test_only_one_job_at_a_time(client, monkeypatch):
    release = asyncio.Event()

    async def slow(self, messages, schema):
        await release.wait()
        raise LLMError("too many requests", "llm_rate_limited")

    monkeypatch.setattr(LLMClient, "complete_json", slow)
    await client.post("/api/datasets/upload", files={"file": SAMPLE.open("rb")})
    payload = {"conversation_ids": ["s-ru-001"]}
    started = (await client.post("/api/evaluate/batch", json=payload)).json()
    assert started["conversation_ids"] == ["SAMPLE:s-ru-001"]
    busy = await client.post("/api/evaluate/batch", json=payload)
    assert busy.status_code == 409 and busy.headers["x-error-code"] == "job_running"
    await asyncio.sleep(0.01)
    assert (await client.get(f"/api/jobs/{started['id']}")).json()["current"] == ["SAMPLE:s-ru-001"]
    release.set()
    job = await wait_job(client, started["id"])
    assert job["failed"][0]["code"] == "llm_rate_limited"


async def _wait_job(client, job_id):
    import asyncio

    for _ in range(100):
        job = (await client.get(f"/api/jobs/{job_id}")).json()
        if job["status"] == "finished":
            return job
        await asyncio.sleep(0.02)
    raise AssertionError("job did not finish")


async def test_statuses_retry_failed_and_profile_switch(client, monkeypatch):
    from src.llm.client import LLMError

    good = LLMClient.complete_json

    async def broken(self, messages, schema):
        raise LLMError("quota exceeded")

    await client.post("/api/datasets/upload", files={"file": SAMPLE.open("rb")})
    monkeypatch.setattr(LLMClient, "complete_json", broken)
    job = (await client.post("/api/evaluate/batch", json={"dataset": "SAMPLE"})).json()
    job = await _wait_job(client, job["id"])
    assert len(job["failed"]) == 2 and len(job["skipped"]) == 1

    # * Статусы видны в списке и в очереди и переживают перезагрузку страницы
    items = {i["source_id"]: i for i in (await client.get("/api/conversations")).json()}
    assert items["s-ru-001"]["status"] == "failed" and "quota" in items["s-ru-001"]["status_error"]
    assert items["s-en-003"]["status"] == "skipped"
    queue = (await client.get("/api/queue")).json()
    assert queue["counts"]["failed"] == 2 and queue["model"]["avg_eval_sec"] > 0
    assert (await client.get("/api/jobs")).json()[0]["id"] == job["id"]

    # ** Retry только упавших
    monkeypatch.setattr(LLMClient, "complete_json", good)
    job = (await client.post("/api/evaluate/batch", json={"only_failed": True})).json()
    assert job["total"] == 2
    job = await _wait_job(client, job["id"])
    assert len(job["done"]) == 2
    assert (await client.get("/api/queue")).json()["counts"]["failed"] == 0

    # * Переключение модели на лету
    r = (await client.patch("/api/settings", json={"llm_profile": "local", "queue_sort": "long_first"})).json()
    assert r["llm_profile"] == "local" and r["profiles"]["local"]["active"] and r["auto_mode"] is False
    assert (await client.get("/api/health")).json()["profile"] == "local"
    assert (await client.patch("/api/settings", json={"queue_sort": "random"})).status_code == 422


async def test_auto_worker_order_and_no_auto_retry(client, monkeypatch):
    import asyncio

    from src.llm.client import LLMError

    good = LLMClient.complete_json
    seen: list[str] = []

    async def picky(self, messages, schema):
        # * Диалог узнаём по метаданным в промпте; KZ-чат «падает»
        text = messages[1]["content"]
        seen.append("kz" if "s-kz-002" in text else "ru")
        if "s-kz-002" in text:
            raise LLMError("boom")
        return await good(self, messages, schema)

    await client.post("/api/datasets/upload", files={"file": SAMPLE.open("rb")})
    monkeypatch.setattr(LLMClient, "complete_json", picky)
    queue = (await client.get("/api/queue")).json()
    assert queue["counts"]["upcoming"] == 0

    # * Звонки сначала / в конце, сортировка внутри групп сохраняется (проверяем запрос кандидатов без гонки с воркером)
    from src import db

    order = lambda calls: [c["source_id"] for c in db.auto_candidates("short_first", None, [], 10, calls)]  # noqa: E731
    assert order("first") == ["s-en-003", "s-kz-002", "s-ru-001"]
    assert order("last") == ["s-kz-002", "s-ru-001", "s-en-003"]
    assert (await client.patch("/api/settings", json={"auto_calls": "sometimes"})).status_code == 422

    await client.patch("/api/settings", json={"auto_mode": True, "queue_sort": "short_first"})
    queue = (await client.get("/api/queue")).json()
    # ** Звонок исключён, короткий KZ-чат первым
    assert [u["source_id"] for u in queue["upcoming"]] == ["s-kz-002", "s-ru-001"] and queue["upcoming"][1]["eta_sec"] > 0

    for _ in range(200):
        items = {i["source_id"]: i for i in (await client.get("/api/conversations")).json()}
        if items["s-ru-001"]["status"] == "done":
            break
        await asyncio.sleep(0.02)
    await asyncio.sleep(0.1)
    assert seen == ["kz", "ru"]
    assert items["s-kz-002"]["status"] == "failed" and items["s-kz-002"]["status_attempts"] == 1
    assert items["s-en-003"]["status"] is None
    worker = (await client.get("/api/worker")).json()
    assert worker["alive"] and worker["mode"] == "auto" and worker["status"] == "idle" and worker["failed"] == 1

    await client.patch("/api/settings", json={"auto_mode": False})


async def test_call_transcribed_from_audio(client, monkeypatch):
    from src.features.transcription import service as asr

    async def fake_audio(url):
        return b"ID3fake", "mp3"

    monkeypatch.setattr(get_settings(), "exclude_channels", [])
    monkeypatch.setattr(asr, "fetch_audio", fake_audio)
    await client.post("/api/datasets/upload", files={"file": SAMPLE.open("rb")})

    # ** По умолчанию распознавание выключено: звонок оценивается по тексту датасета, запись в модель не уходит
    card = (await client.post("/api/evaluate", json={"conversation_id": "s-en-003"})).json()
    assert card["conversation"]["transcript_source"] == "original" and ["segments"] not in client.llm_calls
    assert (await client.post("/api/conversations/s-en-003/transcribe")).status_code == 409
    assert (await client.get("/api/settings")).json()["transcribe_enabled"] is False
    client.llm_calls.clear()
    monkeypatch.setattr(get_settings(), "transcribe_enabled", True)

    # ** Звонок оценивается по своему транскрипту (call_transcript=asr по умолчанию), снимок хранится в оценке
    card = (await client.post("/api/evaluate", json={"conversation_id": "s-en-003"})).json()
    assert client.llm_calls[0] == ["segments"] and card["conversation"]["transcript_source"] == "asr"
    assert [m["speaker"] for m in card["conversation"]["transcript"]] == ["operator", "client", "operator"]
    assert card["conversation"]["transcript"][1]["timestamp"].startswith("2026-11-06T10:15:08")
    conv = (await client.get("/api/conversations/s-en-003")).json()
    assert conv["asr_meta"]["model"] == get_settings().transcribe_model and len(conv["transcript_asr"]) == 3

    # * Повторная оценка не распознаёт заново; при original — оценка по транскрипту датасета
    await client.post("/api/evaluate", json={"conversation_id": "s-en-003"})
    assert sum(c == ["segments"] for c in client.llm_calls) == 1
    await client.patch("/api/settings", json={"call_transcript": "original"})
    card = (await client.post("/api/evaluate", json={"conversation_id": "s-en-003"})).json()
    assert card["conversation"]["transcript_source"] == "original" and "transcript" not in card["meta"]


async def test_submission_format(client, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "results_dir", tmp_path / "results")
    await client.post("/api/datasets/upload", files={"file": SAMPLE.open("rb")})
    await client.post("/api/evaluate", json={"conversation_id": "s-ru-001"})

    body = (await client.get("/api/export/submission", params={"dataset": "SAMPLE", "target": "dev"})).json()
    sub, check = body["submission"], body["check"]
    assert sub["schema_version"] == "1.0" and set(sub) == {"schema_version", "team_name", "model", "results"}
    assert check["errors"] == [] and check["counts"] == {"ok": 1, "error": 2}
    ok = next(r for r in sub["results"] if r["status"] == "ok")
    assert ok["conversation_id"] == "s-ru-001" and set(ok) == {"conversation_id", "status", "criteria", "score"}
    assert [c["criterion_id"] for c in ok["criteria"]] == [
        "contact", "discovery", "identification", "consultation", "empathy", "dialogue", "closure", "critical"]
    assert ok["score"]["critical_flag"] is ok["criteria"][-1]["value"]
    error = next(r for r in sub["results"] if r["status"] == "error")
    assert error["criteria"] == [] and error["score"] is None and error["error"]

    saved = (await client.post("/api/export/submission/save", params={"dataset": "SAMPLE", "target": "dev", "team_name": "T"})).json()
    path = tmp_path / "results" / "dev" / "results.json"
    assert saved["path"] == str(path) and json.loads(path.read_text(encoding="utf-8"))["team_name"] == "T"
    assert (await client.post("/api/export/submission/save", params={"dataset": "SAMPLE", "target": "../x"})).status_code == 422


async def test_pause_resume_and_stop_batch(client, monkeypatch):
    good = LLMClient.complete_json
    # * Каждый вызов модели ждёт свой замок: тест сам решает, какой ответ отпустить
    gates: list[asyncio.Event] = []
    cancelled = []

    async def slow(self, messages, schema):
        gate = asyncio.Event()
        gates.append(gate)
        try:
            await gate.wait()
        except asyncio.CancelledError:
            cancelled.append(len(gates))
            raise
        return await good(self, messages, schema)

    async def wait_for(job_id, check):
        for _ in range(200):
            job = (await client.get(f"/api/jobs/{job_id}")).json()
            if check(job):
                return job
            await asyncio.sleep(0.01)
        raise AssertionError(f"job state not reached: {job}")

    monkeypatch.setattr(LLMClient, "complete_json", slow)
    await client.post("/api/datasets/upload", files={"file": SAMPLE.open("rb")})
    ids = ["s-ru-001", "s-kz-002"]
    job = (await client.post("/api/evaluate/batch", json={"conversation_ids": ids})).json()
    first = job["conversation_ids"][0]
    await wait_for(job["id"], lambda j: len(gates) == 1)

    # ** Пауза прерывает запрос к модели и возвращает диалог в очередь, не считая его обработанным
    assert (await client.post("/api/jobs/current/pause")).json()["status"] == "paused"
    job = await wait_for(job["id"], lambda j: not j["current"])
    assert cancelled == [1] and job["processed"] == 0
    items = {i["id"]: i for i in (await client.get("/api/conversations")).json()}
    assert items[first]["status"] == "queued"
    assert (await client.post("/api/evaluate/batch", json={"conversation_ids": ids})).status_code == 409
    await asyncio.sleep(0.05)
    assert len(gates) == 1

    # * Продолжение: тот же диалог берётся первым и оценивается
    assert (await client.post(f"/api/jobs/{job['id']}/resume")).json()["status"] == "running"
    job = await wait_for(job["id"], lambda j: len(gates) == 2)
    assert job["current"] == [first]
    gates[1].set()
    job = await wait_for(job["id"], lambda j: len(gates) == 3)
    assert job["done"][0]["conversation_id"] == first

    # * Остановка: текущий прерван, статус снят, готовая оценка остаётся
    assert (await client.post(f"/api/jobs/{job['id']}/stop")).json()["stopped"] is True
    job = await wait_for(job["id"], lambda j: j["status"] == "finished")
    assert len(job["done"]) == 1 and len(job["cancelled"]) == 1 and job["processed"] == 1 and cancelled == [1, 3]
    items = {i["id"]: i for i in (await client.get("/api/conversations")).json()}
    assert items[job["cancelled"][0]]["status"] is None and items[first]["last_evaluation_id"]
    assert (await client.post(f"/api/jobs/{job['id']}/stop")).status_code == 409


async def test_stop_auto_worker(client, monkeypatch):
    gate = asyncio.Event()

    async def hang(self, messages, schema):
        await gate.wait()

    monkeypatch.setattr(LLMClient, "complete_json", hang)
    await client.post("/api/datasets/upload", files={"file": SAMPLE.open("rb")})
    await client.patch("/api/settings", json={"auto_mode": True})
    for _ in range(200):
        if (await client.get("/api/queue")).json()["counts"]["running"]:
            break
        await asyncio.sleep(0.01)
    assert (await client.post("/api/worker/stop")).json()["interrupted"] is True
    await asyncio.sleep(0.05)
    assert (await client.get("/api/settings")).json()["auto_mode"] is False
    queue = (await client.get("/api/queue")).json()
    assert queue["counts"]["running"] == 0 and queue["counts"]["failed"] == 0
