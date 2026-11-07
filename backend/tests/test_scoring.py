import copy
import json
from pathlib import Path

import pytest

from src.features.evaluation.scoring import apply_appeals, score_evaluation

CHECKLIST = json.loads((Path(__file__).parents[1] / "checklists" / "default_checklist.json").read_text())


def ans(value=None, na=False, flags=None):
    return {"status": "ok", "value": value, "na": na, "flags": flags or [], "explanation": "", "evidence_ids": [], "checked_range": ""}


def example():
    # * c01 Да, c02 N/A, c03 Да, c04=15, c05 Да, c06=7, c07 Нет, c08 Нет
    return {
        "c01_contact": ans(1), "c02_needs": ans(na=True), "c03_ident": ans(1), "c04_consult": ans(15),
        "c05_empathy": ans(1), "c06_flow": ans(7), "c07_closing": ans(0), "c08_gross": ans(0),
    }


def by_id(result, cid):
    return next(i for i in result["criteria"] if i["id"] == cid)


def test_all_max_is_100():
    a = {c["id"]: ans(max((s["value"] for s in c["scale"]), default=1) if c["type"] != "flag" else 0) for c in CHECKLIST["criteria"]}
    assert score_evaluation(CHECKLIST, a)["total"] == 100.0


def test_example_total():
    assert score_evaluation(CHECKLIST, example())["total"] == 82.94


def test_weight_change_without_llm():
    cl = copy.deepcopy(CHECKLIST)
    cl["criteria"][0]["weight"] = 30
    assert score_evaluation(cl, example())["total"] == 86.19


def test_appeal_changes_total():
    appeals = [{"id": 1, "criterion_id": "c04_consult", "status": "resolved", "decision": "changed", "new_answer": {"value": 20, "na": False}}]
    assert score_evaluation(CHECKLIST, apply_appeals(example(), appeals))["total"] == 88.82


def test_na_redistribution():
    a = {c["id"]: ans(max((s["value"] for s in c["scale"]), default=1) if c["type"] != "flag" else 0) for c in CHECKLIST["criteria"]}
    a["c03_ident"] = ans(na=True)
    a["c01_contact"] = ans(0)
    r = score_evaluation(CHECKLIST, a)
    assert r["total"] == 87.5
    assert by_id(r, "c01_contact")["effective_weight"] == 12.5


def test_na_not_allowed_becomes_no():
    a = example()
    a["c01_contact"] = ans(na=True)
    r = score_evaluation(CHECKLIST, a)
    assert by_id(r, "c01_contact")["answer"] == "no"
    assert any("c01_contact" in w for w in r["warnings"])


def test_gross_flag_does_not_affect_total():
    a = example()
    a["c08_gross"] = ans(1, flags=["bypass_offer"])
    r = score_evaluation(CHECKLIST, a)
    assert r["total"] == 82.94
    assert r["gross_errors"] == {"detected": True, "types": ["bypass_offer"], "criteria": ["c08_gross"]}


def test_all_na_total_null():
    cl = {"criteria": [{"id": "a", "type": "binary", "weight": 10, "na_allowed": True, "section": "s"}]}
    assert score_evaluation(cl, {"a": ans(na=True)})["total"] is None


def test_scale_snaps_to_step():
    a = example()
    a["c04_consult"] = ans(13)
    r = score_evaluation(CHECKLIST, a)
    assert by_id(r, "c04_consult")["value"] == 15 and r["warnings"]


def test_round_half_up():
    cl = {"criteria": [
        {"id": "a", "type": "binary", "weight": 70.5, "section": "s"},
        {"id": "b", "type": "binary", "weight": 9.5, "section": "s"},
    ]}
    assert score_evaluation(cl, {"a": ans(1), "b": ans(0)})["total"] == 88.13


def test_missing_answer_is_preliminary():
    a = example()
    del a["c05_empathy"]
    r = score_evaluation(CHECKLIST, a)
    assert r["preliminary"] and by_id(r, "c05_empathy")["status"] == "error"
