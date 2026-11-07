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
    dataset TEXT NOT NULL,
    channel TEXT,
    language TEXT,
    audio_url TEXT,
    transcript TEXT NOT NULL,
    imported_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_conversations_dataset ON conversations(dataset);

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
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

JSON_FIELDS = {"transcript", "data", "answers", "meta", "new_answer"}


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


def init_db() -> None:
    path = get_settings().db_path
    with connect() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
    logger.info("Database ready at %s", path)


# * Настройки приложения: одна запись, поля проверяются схемой на уровне фичи


def get_app_settings() -> dict[str, Any] | None:
    with connect() as conn:
        row = _row(conn.execute("SELECT data FROM app_settings WHERE id = 1").fetchone())
    return row["data"] if row else None


def save_app_settings(data: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO app_settings (id, data, updated_at) VALUES (1, ?, ?)
               ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at""",
            (_dump(data), _now()),
        )


# * Диалоги


def upsert_conversations(dataset: str, records: list[dict[str, Any]]) -> int:
    now = _now()
    rows = [
        (r["conversation_id"], dataset, r.get("channel"), r.get("language"), r.get("audio_url"), _dump(r["transcript"]), now)
        for r in records
    ]
    with connect() as conn:
        conn.executemany(
            """INSERT INTO conversations (id, dataset, channel, language, audio_url, transcript, imported_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET dataset=excluded.dataset, channel=excluded.channel,
                 language=excluded.language, audio_url=excluded.audio_url,
                 transcript=excluded.transcript, imported_at=excluded.imported_at""",
            rows,
        )
    return len(rows)


def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        return _row(conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone())


def list_conversations(dataset: str | None = None) -> list[dict[str, Any]]:
    # * Список без транскрипта + id последней оценки и число открытых апелляций по ней
    sql = """
        SELECT c.id, c.dataset, c.channel, c.language, c.audio_url, c.imported_at, json_array_length(c.transcript) AS messages,
               (SELECT e.id FROM evaluations e WHERE e.conversation_id = c.id ORDER BY e.id DESC LIMIT 1) AS last_evaluation_id
        FROM conversations c {where} ORDER BY c.id
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
        SELECT e.*, c.language, c.channel, c.dataset FROM evaluations e
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


def copy_resolved_appeals(from_evaluation_id: int, to_evaluation_id: int, criteria_ids: list[str]) -> int:
    # * При переносе оценки на новый чек-лист решения по апелляциям для неизменных критериев сохраняются
    if not criteria_ids:
        return 0
    marks = ",".join("?" * len(criteria_ids))
    with connect() as conn:
        cur = conn.execute(
            f"""INSERT INTO appeals (evaluation_id, criterion_id, comment, status, decision, new_answer, reason, created_at, resolved_at)
                SELECT ?, criterion_id, comment, status, decision, new_answer, reason, created_at, resolved_at
                FROM appeals WHERE evaluation_id = ? AND status = 'resolved' AND criterion_id IN ({marks}) ORDER BY id""",
            (to_evaluation_id, from_evaluation_id, *criteria_ids),
        )
        return cur.rowcount
