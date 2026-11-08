# ** Весь доступ к БД — только здесь, чтобы потом можно было заменить SQLite на PostgreSQL
import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    dataset TEXT NOT NULL,
    seq INTEGER NOT NULL DEFAULT 0,
    channel TEXT,
    language TEXT,
    audio_url TEXT,
    transcript TEXT NOT NULL,
    transcript_asr TEXT,
    asr_meta TEXT,
    imported_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_conversations_dataset ON conversations(dataset);
CREATE INDEX IF NOT EXISTS ix_conversations_source ON conversations(source_id);

CREATE TABLE IF NOT EXISTS checklists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version INTEGER NOT NULL,
    name TEXT NOT NULL,
    data TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    checklist_id INTEGER NOT NULL REFERENCES checklists(id),
    answers TEXT NOT NULL,
    meta TEXT NOT NULL,
    parent_id INTEGER REFERENCES evaluations(id),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_evaluations_conversation ON evaluations(conversation_id);

CREATE TABLE IF NOT EXISTS appeals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id INTEGER NOT NULL REFERENCES evaluations(id),
    criterion_id TEXT NOT NULL,
    comment TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    decision TEXT,
    new_answer TEXT,
    reason TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_appeals_evaluation ON appeals(evaluation_id);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_status (
    conversation_id TEXT PRIMARY KEY REFERENCES conversations(id),
    state TEXT NOT NULL,
    source TEXT NOT NULL,
    job_id TEXT,
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    model TEXT,
    queued_at TEXT,
    started_at TEXT,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_analysis_status_state ON analysis_status(state);
"""

JSON_FIELDS = {"transcript", "transcript_asr", "asr_meta", "data", "answers", "meta", "new_answer"}
# ! Увеличивается при несовместимых изменениях; поддерживаемые старые схемы мигрируются при старте.
SCHEMA_VERSION = 2


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@contextmanager
def connect(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    # ** Новое соединение на операцию + короткая транзакция: пакетная оценка пишет параллельно
    conn = sqlite3.connect(db_path or get_settings().db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    out = dict(row)
    for key in JSON_FIELDS & out.keys():
        if out[key] is not None:
            out[key] = json.loads(out[key])
    if "is_active" in out:
        out["is_active"] = bool(out["is_active"])
    return out


def _rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [_row(r) for r in rows]


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


class SchemaOutdated(RuntimeError):
    pass


def init_db() -> None:
    path = get_settings().db_path
    with connect() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        exists = "conversations" in tables
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise SchemaOutdated(f"{path}: schema v{version} is newer than this app (supports v{SCHEMA_VERSION})")

        # * v0 used source conversation IDs as primary keys and lacked source_id/seq/ASR fields.
        # Preserve existing IDs so evaluation and appeal foreign keys remain valid.
        if exists and version < SCHEMA_VERSION:
            required = {
                "conversations": {"id", "dataset", "channel", "language", "audio_url", "transcript", "imported_at"},
                "checklists": {"id", "version", "name", "data", "comment", "is_active", "created_at"},
                "evaluations": {"id", "conversation_id", "checklist_id", "answers", "meta", "parent_id", "created_at"},
                "appeals": {"id", "evaluation_id", "criterion_id", "comment", "status", "decision", "new_answer", "reason", "created_at", "resolved_at"},
            }
            missing_by_table = {}
            for table, expected in required.items():
                if table in tables:
                    columns = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
                    missing = expected - columns
                    if missing:
                        missing_by_table[table] = sorted(missing)
            if missing_by_table:
                raise SchemaOutdated(f"{path}: unsupported legacy columns missing: {missing_by_table}; database left unchanged")

            conversation_columns = {r[1] for r in conn.execute("PRAGMA table_info(conversations)").fetchall()}
            if "source_id" not in conversation_columns:
                conn.execute("ALTER TABLE conversations ADD COLUMN source_id TEXT NOT NULL DEFAULT ''")
                conn.execute("UPDATE conversations SET source_id = id WHERE source_id = ''")
                logger.info("Database migrated: conversations.source_id added")
            if "seq" not in conversation_columns:
                conn.execute("ALTER TABLE conversations ADD COLUMN seq INTEGER NOT NULL DEFAULT 0")
                datasets = [r[0] for r in conn.execute("SELECT DISTINCT dataset FROM conversations ORDER BY dataset").fetchall()]
                for dataset in datasets:
                    rows = conn.execute(
                        "SELECT id FROM conversations WHERE dataset = ? ORDER BY imported_at, id", (dataset,)
                    ).fetchall()
                    conn.executemany(
                        "UPDATE conversations SET seq = ? WHERE id = ?",
                        [(seq, row[0]) for seq, row in enumerate(rows, start=1)],
                    )
                logger.info("Database migrated: conversations.seq added and populated")
        # * Миграция настроек из формата «одна строка JSON» (ветка фронта) в «ключ — значение»
        old_settings: dict[str, Any] = {}
        cols = {r[1] for r in conn.execute("PRAGMA table_info(app_settings)").fetchall()}
        if "data" in cols:
            row = conn.execute("SELECT data FROM app_settings WHERE id = 1").fetchone()
            old_settings = json.loads(row[0]) if row else {}
            conn.execute("DROP TABLE app_settings")
            logger.info("Database migrated: app_settings converted to key/value (%d fields)", len(old_settings))
        conn.executescript(SCHEMA)
        if old_settings:
            conn.executemany(
                "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", [(k, _dump(v)) for k, v in old_settings.items()]
            )
        # * Лёгкая миграция v2: колонки своего транскрипта звонка добавляются без пересоздания БД
        columns = {r[1] for r in conn.execute("PRAGMA table_info(conversations)").fetchall()}
        for col in ("transcript_asr", "asr_meta"):
            if col not in columns:
                conn.execute(f"ALTER TABLE conversations ADD COLUMN {col} TEXT")
                logger.info("Database migrated: conversations.%s added", col)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    logger.info("Database ready at %s", path)


# * Диалоги


def conversation_key(dataset: str, source_id: str) -> str:
    # ** Внутренний id = набор + исходный id: одинаковые id из DEV и TEST не перезаписывают друг друга
    return f"{dataset}:{source_id}"


def upsert_conversations(dataset: str, records: list[dict[str, Any]]) -> int:
    now = _now()
    rows = [
        (
            conversation_key(dataset, r["conversation_id"]), r["conversation_id"], dataset, r.get("seq", 0),
            r.get("channel"), r.get("language"), r.get("audio_url"), _dump(r["transcript"]), now,
        )
        for r in records
    ]
    with connect() as conn:
        for row in rows:
            key, source_id, row_dataset, seq, channel, language, audio_url, transcript, imported_at = row
            existing = conn.execute(
                """SELECT id FROM conversations WHERE id = ? OR (dataset = ? AND source_id = ?)
                   ORDER BY CASE WHEN id = ? THEN 0 ELSE 1 END LIMIT 1""",
                (key, row_dataset, source_id, key),
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE conversations SET source_id = ?, dataset = ?, seq = ?, channel = ?, language = ?,
                       audio_url = ?, transcript = ?, imported_at = ? WHERE id = ?""",
                    (source_id, row_dataset, seq, channel, language, audio_url, transcript, imported_at, existing[0]),
                )
            else:
                conn.execute(
                    """INSERT INTO conversations
                       (id, source_id, dataset, seq, channel, language, audio_url, transcript, imported_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    row,
                )
    return len(rows)


def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    # * Принимаем и внутренний id (DEV:p1-ru-001), и исходный, если он однозначен
    with connect() as conn:
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if row is None:
            if ":" in conversation_id:
                dataset, source_id = conversation_id.split(":", 1)
                row = conn.execute(
                    "SELECT * FROM conversations WHERE dataset = ? AND source_id = ?", (dataset, source_id)
                ).fetchone()
            else:
                rows = conn.execute("SELECT * FROM conversations WHERE source_id = ? LIMIT 2", (conversation_id,)).fetchall()
                row = rows[0] if len(rows) == 1 else None
        return _row(row)


def list_conversations(dataset: str | None = None) -> list[dict[str, Any]]:
    # * Список без транскрипта + id последней оценки и число открытых апелляций по ней
    sql = """
        SELECT c.id, c.source_id, c.dataset, c.seq, c.channel, c.language, c.audio_url, c.imported_at, json_array_length(c.transcript) AS messages,
               json_array_length(c.transcript_asr) AS asr_messages,
               (SELECT e.id FROM evaluations e WHERE e.conversation_id = c.id ORDER BY e.id DESC LIMIT 1) AS last_evaluation_id,
               s.state AS status, s.source AS status_source, s.error AS status_error, s.attempts AS status_attempts,
               s.queued_at AS status_queued_at, s.started_at AS status_started_at, s.finished_at AS status_finished_at
        FROM conversations c LEFT JOIN analysis_status s ON s.conversation_id = c.id {where} ORDER BY c.dataset, c.seq, c.id
    """
    where, params = ("WHERE c.dataset = ?", (dataset,)) if dataset else ("", ())
    with connect() as conn:
        items = _rows(conn.execute(sql.format(where=where), params).fetchall())
        for item in items:
            eid = item["last_evaluation_id"]
            item["open_appeals"] = (
                conn.execute("SELECT COUNT(*) FROM appeals WHERE evaluation_id = ? AND status = 'open'", (eid,)).fetchone()[0]
                if eid
                else 0
            )
    return items


def list_datasets() -> list[dict[str, Any]]:
    with connect() as conn:
        return _rows(conn.execute("SELECT dataset, COUNT(*) AS total FROM conversations GROUP BY dataset ORDER BY dataset").fetchall())


# * Чек-листы: каждое сохранение — новая версия, активна ровно одна


def insert_checklist(data: dict[str, Any], comment: str = "", activate: bool = True) -> dict[str, Any]:
    with connect() as conn:
        version = conn.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM checklists").fetchone()[0]
        if activate:
            conn.execute("UPDATE checklists SET is_active = 0 WHERE is_active = 1")
        cur = conn.execute(
            "INSERT INTO checklists (version, name, data, comment, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (version, data.get("name", f"Checklist v{version}"), _dump(data), comment, int(activate), _now()),
        )
        row = conn.execute("SELECT * FROM checklists WHERE id = ?", (cur.lastrowid,)).fetchone()
    logger.info("Checklist saved: id=%s version=%s active=%s", cur.lastrowid, version, activate)
    return _row(row)


def get_checklist(checklist_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        return _row(conn.execute("SELECT * FROM checklists WHERE id = ?", (checklist_id,)).fetchone())


def get_active_checklist() -> dict[str, Any] | None:
    with connect() as conn:
        return _row(conn.execute("SELECT * FROM checklists WHERE is_active = 1 ORDER BY id DESC LIMIT 1").fetchone())


def list_checklists() -> list[dict[str, Any]]:
    with connect() as conn:
        return _rows(
            conn.execute("SELECT id, version, name, comment, is_active, created_at FROM checklists ORDER BY id DESC").fetchall()
        )


def activate_checklist(checklist_id: int) -> bool:
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM checklists WHERE id = ?", (checklist_id,)).fetchone():
            return False
        conn.execute("UPDATE checklists SET is_active = (id = ?)", (checklist_id,))
    return True


def seed_default_checklist(path: Path) -> None:
    if get_active_checklist():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    insert_checklist(data, comment="Начальная конфигурация организаторов")
    logger.info("Default checklist seeded from %s", path)


# * Оценки


def insert_evaluation(
    conversation_id: str, checklist_id: int, answers: dict[str, Any], meta: dict[str, Any], parent_id: int | None = None
) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO evaluations (conversation_id, checklist_id, answers, meta, parent_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (conversation_id, checklist_id, _dump(answers), _dump(meta), parent_id, _now()),
        )
        return cur.lastrowid


def get_evaluation(evaluation_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        return _row(conn.execute("SELECT * FROM evaluations WHERE id = ?", (evaluation_id,)).fetchone())


def list_evaluations(conversation_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        return _rows(
            conn.execute("SELECT * FROM evaluations WHERE conversation_id = ? ORDER BY id DESC", (conversation_id,)).fetchall()
        )


def latest_evaluations(dataset: str | None = None) -> list[dict[str, Any]]:
    # * Последняя оценка по каждому диалогу (для аналитики и пакетных пересчётов)
    sql = """
        SELECT e.*, c.source_id, c.language, c.channel, c.dataset FROM evaluations e
        JOIN conversations c ON c.id = e.conversation_id
        WHERE e.id = (SELECT MAX(id) FROM evaluations WHERE conversation_id = e.conversation_id) {extra}
        ORDER BY e.conversation_id
    """
    extra, params = ("AND c.dataset = ?", (dataset,)) if dataset else ("", ())
    with connect() as conn:
        return _rows(conn.execute(sql.format(extra=extra), params).fetchall())


# * Апелляции


def insert_appeal(evaluation_id: int, criterion_id: str, comment: str) -> dict[str, Any]:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO appeals (evaluation_id, criterion_id, comment, created_at) VALUES (?, ?, ?, ?)",
            (evaluation_id, criterion_id, comment, _now()),
        )
        return _row(conn.execute("SELECT * FROM appeals WHERE id = ?", (cur.lastrowid,)).fetchone())


def get_appeal(appeal_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        return _row(conn.execute("SELECT * FROM appeals WHERE id = ?", (appeal_id,)).fetchone())


def list_appeals(status: str | None = None, evaluation_id: int | None = None) -> list[dict[str, Any]]:
    clauses, params = [], []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if evaluation_id is not None:
        clauses.append("evaluation_id = ?")
        params.append(evaluation_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as conn:
        return _rows(conn.execute(f"SELECT * FROM appeals {where} ORDER BY id", params).fetchall())


def resolve_appeal(appeal_id: int, decision: str, reason: str, new_answer: dict[str, Any] | None) -> dict[str, Any] | None:
    with connect() as conn:
        conn.execute(
            "UPDATE appeals SET status = 'resolved', decision = ?, reason = ?, new_answer = ?, resolved_at = ? WHERE id = ?",
            (decision, reason, _dump(new_answer) if new_answer is not None else None, _now(), appeal_id),
        )
        return _row(conn.execute("SELECT * FROM appeals WHERE id = ?", (appeal_id,)).fetchone())


def latest_evaluation_id(conversation_id: str) -> int | None:
    with connect() as conn:
        row = conn.execute("SELECT MAX(id) FROM evaluations WHERE conversation_id = ?", (conversation_id,)).fetchone()
        return row[0]


REOPEN_NOTE = "\n[Критерий изменён после решения «{decision}: {reason}» — пересмотрите апелляцию]"


def carry_appeals(from_evaluation_id: int, to_evaluation_id: int, unchanged_ids: list[str], present_ids: list[str]) -> dict[str, int]:
    # ** Апелляции живут на актуальной оценке: открытые переезжают, решения копируются, по изменённым критериям — снова открываются
    unchanged, present = set(unchanged_ids), set(present_ids)
    moved = copied = reopened = 0
    with connect() as conn:
        rows = _rows(conn.execute("SELECT * FROM appeals WHERE evaluation_id = ? ORDER BY id", (from_evaluation_id,)).fetchall())
        # ! По критерию допускается одна открытая апелляция: переоткрываем только последнее решение и только если открытой нет
        open_criteria = {a["criterion_id"] for a in rows if a["status"] == "open"}
        last_resolved = {a["criterion_id"]: a["id"] for a in rows if a["status"] == "resolved"}
        for a in rows:
            if a["criterion_id"] not in present:
                continue
            if a["status"] == "open":
                conn.execute("UPDATE appeals SET evaluation_id = ? WHERE id = ?", (to_evaluation_id, a["id"]))
                moved += 1
            elif a["criterion_id"] in unchanged:
                conn.execute(
                    """INSERT INTO appeals (evaluation_id, criterion_id, comment, status, decision, new_answer, reason, created_at, resolved_at)
                       VALUES (?, ?, ?, 'resolved', ?, ?, ?, ?, ?)""",
                    (to_evaluation_id, a["criterion_id"], a["comment"], a["decision"],
                     _dump(a["new_answer"]) if a["new_answer"] is not None else None, a["reason"], a["created_at"], a["resolved_at"]),
                )
                copied += 1
            elif a["id"] == last_resolved[a["criterion_id"]] and a["criterion_id"] not in open_criteria:
                note = REOPEN_NOTE.format(decision=a["decision"], reason=a["reason"])
                conn.execute(
                    "INSERT INTO appeals (evaluation_id, criterion_id, comment, created_at) VALUES (?, ?, ?, ?)",
                    (to_evaluation_id, a["criterion_id"], a["comment"] + note, a["created_at"]),
                )
                reopened += 1
    return {"moved": moved, "copied": copied, "reopened": reopened}


# * Настройки приложения (переключаются из UI)


def get_app_settings() -> dict[str, Any]:
    with connect() as conn:
        return {r["key"]: json.loads(r["value"]) for r in conn.execute("SELECT key, value FROM app_settings").fetchall()}


def set_app_settings(values: dict[str, Any]) -> None:
    with connect() as conn:
        conn.executemany(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [(k, _dump(v)) for k, v in values.items()],
        )


# * Статусы анализа: переживают перезагрузку страницы и рестарт сервера


def queue_statuses(conversation_ids: list[str], source: str, job_id: str | None) -> None:
    now = _now()
    with connect() as conn:
        conn.executemany(
            """INSERT INTO analysis_status (conversation_id, state, source, job_id, queued_at)
               VALUES (?, 'queued', ?, ?, ?)
               ON CONFLICT(conversation_id) DO UPDATE SET state='queued', source=excluded.source, job_id=excluded.job_id,
                 error=NULL, queued_at=excluded.queued_at, started_at=NULL, finished_at=NULL""",
            [(cid, source, job_id, now) for cid in conversation_ids],
        )


def start_status(conversation_id: str, source: str, job_id: str | None, model: str) -> None:
    now = _now()
    with connect() as conn:
        conn.execute(
            """INSERT INTO analysis_status (conversation_id, state, source, job_id, attempts, model, queued_at, started_at)
               VALUES (?, 'running', ?, ?, 1, ?, ?, ?)
               ON CONFLICT(conversation_id) DO UPDATE SET state='running', source=excluded.source, job_id=excluded.job_id,
                 error=NULL, attempts=attempts + 1, model=excluded.model, started_at=excluded.started_at, finished_at=NULL,
                 queued_at=COALESCE(analysis_status.queued_at, excluded.queued_at)""",
            (conversation_id, source, job_id, model, now, now),
        )


def finish_status(conversation_id: str, state: str, error: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE analysis_status SET state = ?, error = ?, finished_at = ? WHERE conversation_id = ?",
            (state, error, _now(), conversation_id),
        )


def reset_stale_statuses() -> int:
    # ! После рестарта задачи в памяти потеряны: всё, что было в работе, помечаем упавшим, чтобы можно было повторить
    with connect() as conn:
        cur = conn.execute(
            "UPDATE analysis_status SET state = 'failed', error = 'сервер перезапущен во время анализа', finished_at = ? "
            "WHERE state IN ('queued', 'running')",
            (_now(),),
        )
        return cur.rowcount


def list_statuses(states: tuple[str, ...], dataset: str | None = None) -> list[dict[str, Any]]:
    marks = ",".join("?" * len(states))
    sql = f"""SELECT s.*, c.source_id, c.dataset FROM analysis_status s JOIN conversations c ON c.id = s.conversation_id
              WHERE s.state IN ({marks}) {{extra}} ORDER BY s.queued_at, c.seq"""
    extra, params = ("AND c.dataset = ?", (*states, dataset)) if dataset else ("", states)
    with connect() as conn:
        return _rows(conn.execute(sql.format(extra=extra), params).fetchall())


def recent_durations(model: str, limit: int = 20) -> list[float]:
    # * Длительность последних успешных оценок модели — основа для ETA
    with connect() as conn:
        rows = conn.execute(
            """SELECT json_extract(meta, '$.total_seconds') FROM evaluations
               WHERE json_extract(meta, '$.model') = ? AND json_extract(meta, '$.total_seconds') IS NOT NULL
               ORDER BY id DESC LIMIT ?""",
            (model, limit),
        ).fetchall()
    return [float(r[0]) for r in rows]


# * Ключи совпадают с QueueSort настроек: дата = дата импорта + порядок записи в наборе, длина = число реплик
AUTO_SORT_SQL = {
    "oldest_first": "c.imported_at ASC, c.seq ASC",
    "newest_first": "c.imported_at DESC, c.seq DESC",
    "short_first": "messages ASC, c.imported_at ASC, c.seq ASC",
    "long_first": "messages DESC, c.imported_at ASC, c.seq ASC",
}


AUTO_CALLS_SQL = {"mixed": "", "first": "is_call DESC, ", "last": "is_call ASC, "}


def auto_candidates(
    sort: str, dataset: str | None, excluded_channels: list[str], limit: int = 1, calls: str = "mixed"
) -> list[dict[str, Any]]:
    # ** Только диалоги без оценки и без статуса: упавшие/пропущенные воркер не трогает (повтор — вручную)
    order = AUTO_CALLS_SQL[calls] + AUTO_SORT_SQL[sort]
    excluded = [c.strip().lower() for c in excluded_channels]
    marks = ",".join("?" * len(excluded)) or "''"
    sql = f"""SELECT c.id AS conversation_id, c.id, c.source_id, c.dataset, c.seq, c.imported_at,
                     json_array_length(c.transcript) AS messages,
                     (COALESCE(c.audio_url, '') != '') AS is_call
              FROM conversations c LEFT JOIN analysis_status s ON s.conversation_id = c.id
              WHERE s.conversation_id IS NULL
                AND NOT EXISTS (SELECT 1 FROM evaluations e WHERE e.conversation_id = c.id)
                AND lower(trim(COALESCE(c.channel, ''))) NOT IN ({marks}) {{extra}}
              ORDER BY {order} LIMIT ?"""
    extra, params = ("AND c.dataset = ?", [*excluded, dataset]) if dataset else ("", list(excluded))
    with connect() as conn:
        return _rows(conn.execute(sql.format(extra=extra), [*params, limit]).fetchall())


def set_transcript_asr(conversation_id: str, transcript: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE conversations SET transcript_asr = ?, asr_meta = ? WHERE id = ?",
            (_dump(transcript), _dump(meta), conversation_id),
        )
