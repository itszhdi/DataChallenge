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


def test_normalize_message_attachments_and_garbage():
    from src.features.datasets.utils import normalize_message

    m = normalize_message({"timestamp": 75, "speaker": "Agent", "text": None, "attachments": [{"type": "image", "name": "check.jpg"}]})
    assert m["speaker"] == "operator" and m["timestamp"] == "01:15"
    assert m["text"] == "[вложение: attachments: image check.jpg]" and m["attachments"]
    odd = normalize_message({"speaker": "supervisor", "text": {"url": "https://x/y.pdf"}})
    assert odd["speaker"] == "unknown" and odd["speaker_raw"] == "supervisor" and "y.pdf" in odd["text"]
    assert normalize_message("просто строка")["text"] == "просто строка"


def test_first_response_from_operator_join():
    # ** Клиент 3 минуты общался с ботом — это не ожидание оператора
    tr = [
        {"timestamp": "00:00", "speaker": "client", "text": "вопрос"},
        {"timestamp": "00:02", "speaker": "bot", "text": "Соединяю с оператором"},
        {"timestamp": "03:40", "speaker": "client", "text": "да"},
        {"timestamp": "03:45", "speaker": "system", "text": "Эскалация на оператора."},
        {"timestamp": "04:30", "speaker": "operator", "text": "Здравствуйте!"},
        {"timestamp": "05:00", "speaker": "client", "text": "?"},
        {"timestamp": "09:00", "speaker": "operator", "text": "Ответ"},
    ]
    f = timing_facts(tr, 180)
    assert f["anchor_kind"] == "join" and f["first_response_sec"] == 45 and not f["first_response_exceeded"]
    assert f["long_pauses"] == [{"client_index": 6, "operator_index": 7, "seconds": 240}]
    no_join = timing_facts([tr[0], tr[1], tr[2], tr[4]], 180)
    assert no_join["anchor_kind"] == "client" and no_join["first_response_sec"] == 50
    assert timing_facts([{"speaker": "operator", "text": "hi"}])["first_response_sec"] is None


def test_asr_alignment_record_start_pause_and_pre_recording():
    from src.features.transcription.service import to_transcript

    t = "2026-11-06T10:00:{:02d}+05:00"
    original = [
        {"timestamp": t.format(0), "speaker": "system", "text": "Агент присоединился к разговору с клиентом."},
        {"timestamp": t.format(2), "speaker": "operator", "text": "Здравствуйте, меня зовут [Имя скрыто]."},
        {"timestamp": t.format(10), "speaker": "system", "text": "Запись и транскрибирование запущены."},
        {"timestamp": t.format(20), "speaker": "system", "text": "Запись и транскрибирование приостановлены."},
        {"timestamp": t.format(50), "speaker": "system", "text": "Запись и транскрибирование возобновлены."},
    ]
    segments = [{"start": "00:01", "speaker": "client", "text": "вопрос"}, {"start": "00:15", "speaker": "operator", "text": "ответ"}]
    out = to_transcript(segments, original)
    assert [m["text"][:7] for m in out] == ["Агент п", "Здравст", "Запись ", "вопрос", "Запись ", "Запись ", "ответ"]
    assert out[1]["pre_recording"] and out[3]["timestamp"] == t.format(11)
    # ** 15 с аудио = 10 (старт) + 15 + 30 (пауза 20→50) = 0:55 звонка
    assert out[6]["timestamp"] == t.format(55)


def test_luna_profile_request_and_submission_mode():
    from src.config.settings import Settings
    from src.features.export.submission import _mode
    from src.llm.client import LLMClient

    profiles = Settings(_env_file=None).llm_profiles()
    assert set(profiles) == {"gemini", "luna", "local"}
    luna, gemini = profiles["luna"], profiles["gemini"]
    assert luna.provider == "openai" and luna.model == "gpt-6-luna" and luna.base_url.startswith("https://api.openai.com")

    # ! Рассуждающие модели OpenAI отклоняют temperature — Luna его не получает, остальные получают 0
    msgs, schema = [{"role": "user", "content": "x"}], {"type": "object", "properties": {}, "additionalProperties": False}
    luna_kwargs = LLMClient(luna)._request_kwargs(msgs, schema, luna.model)
    assert "temperature" not in luna_kwargs and luna_kwargs["reasoning_effort"] == "low"
    assert luna_kwargs["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
    assert LLMClient(gemini)._request_kwargs(msgs, schema, gemini.model)["temperature"] == 0

    # ** В файле для сдачи Luna — внешний API, хотя провайдер openai, как у LM Studio
    assert _mode({"profile": "luna", "provider": "openai"}) == "external_api"
    assert _mode({"profile": "local", "provider": "openai"}) == "local"
    assert _mode({"profile": "fallback", "provider": "openai"}) == "local"
    assert _mode({"provider": "gemini"}) == "external_api"
