# * Сквозной сценарий защиты без сети: модель подменена, проверяем что LLM зовётся только когда нужно
from pathlib import Path

import httpx
import pytest

from src.config.settings import get_settings
from src.llm.client import LLMClient
from src.llm.prompts import PROMPT_VERSION
from src.main import app

SAMPLE = Path(__file__).parent / "sample_data.json"


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "db_path", tmp_path / "test.sqlite3")
    calls: list[list[str]] = []

    async def fake_complete(self, messages, schema):
        calls.append(list(schema["properties"]))
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
