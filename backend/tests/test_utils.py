from src.features.datasets.service import dataset_url, extract_records
from src.features.evaluation.timing import parse_timestamp, timing_facts, with_offsets


def test_dataset_url_keeps_signature():
    base = "https://x.example/invoke?api-version=1&sp=%2Ftriggers&sv=1.0&sig=SECRET"
    assert dataset_url(base, "DEV") == base + "&group_id=DEV"


def test_extract_records_envelope():
    group, records = extract_records({"isSuccess": True, "data": {"dataset_group_id": "DEV", "records": [{"a": 1}]}})
    assert group == "DEV" and records == [{"a": 1}]


def test_timing_mmss_and_iso():
    assert parse_timestamp("01:10") == 70
    iso = [
        {"timestamp": "2026-11-06T10:15:02+05:00", "speaker": "operator", "text": ""},
        {"timestamp": "2026-11-06T10:16:02+05:00", "speaker": "client", "text": ""},
    ]
    assert [m["offset_sec"] for m in with_offsets(iso)] == [0, 60]


def test_first_response_exceeded():
    tr = [
        {"timestamp": "00:05", "speaker": "client", "text": "q"},
        {"timestamp": "04:30", "speaker": "operator", "text": "a"},
    ]
    facts = timing_facts(tr, 180)
    assert facts["first_response_sec"] == 265 and facts["first_response_exceeded"]
    assert facts["long_pauses"][0]["seconds"] == 265


def test_gemini_schema_strips_unsupported():
    from src.llm.client import extract_json, gemini_schema

    schema = {"type": "object", "additionalProperties": False, "properties": {
        "v": {"type": "integer", "enum": [0, 5, 10]}, "f": {"type": "string", "enum": ["insult"]}}}
    out = gemini_schema(schema)
    assert "additionalProperties" not in out
    assert "enum" not in out["properties"]["v"] and "0, 5, 10" in out["properties"]["v"]["description"]
    assert out["properties"]["f"]["enum"] == ["insult"]
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('<think>скобки {не JSON}</think>\n{"a": 2}') == {"a": 2}
