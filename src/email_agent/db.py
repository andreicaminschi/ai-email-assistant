import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

DB_FILE_NAME = "agent.db"
HISTORY_ID_KEY = "history_id"

SCHEMA = """
CREATE TABLE IF NOT EXISTS emails (
    message_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    internal_date INTEGER NOT NULL,
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    internal INTEGER,
    triage TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    message_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    label TEXT NOT NULL,
    urgent INTEGER,
    action TEXT NOT NULL,
    outcome TEXT NOT NULL,
    detail TEXT NOT NULL
);
"""

EMAIL_COLUMNS = "message_id, thread_id, internal_date, state, attempts, internal, triage, updated_at"


class State(StrEnum):
    NEW = "NEW"
    SKIPPED = "SKIPPED"
    APPROVAL_REPLY = "APPROVAL_REPLY"
    CLASSIFYING = "CLASSIFYING"
    CLASSIFIED = "CLASSIFIED"
    ARCHIVED = "ARCHIVED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    DONE = "DONE"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass(frozen=True)
class EmailRow:
    message_id: str
    thread_id: str
    internal_date: int
    state: State
    attempts: int
    internal: bool | None
    triage: str | None
    updated_at: str


class EmailNotFound(Exception):
    pass


def database_path(data_dir: Path) -> Path:
    return data_dir / DB_FILE_NAME


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def open_database(data_dir: Path) -> sqlite3.Connection:
    data_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path(data_dir), autocommit=True)
    connection.executescript(SCHEMA)
    return connection


def to_email_row(row: tuple[object, ...]) -> EmailRow:
    message_id, thread_id, internal_date, state, attempts, internal, triage, updated_at = row
    return EmailRow(
        message_id=str(message_id),
        thread_id=str(thread_id),
        internal_date=int(str(internal_date)),
        state=State(state),
        attempts=int(str(attempts)),
        internal=None if internal is None else bool(internal),
        triage=None if triage is None else str(triage),
        updated_at=str(updated_at),
    )


def insert_email(
    connection: sqlite3.Connection, message_id: str, thread_id: str, internal_date: int
) -> EmailRow:
    row = connection.execute(
        f"INSERT INTO emails (message_id, thread_id, internal_date, state, updated_at)"
        f" VALUES (?, ?, ?, ?, ?) RETURNING {EMAIL_COLUMNS}",
        (message_id, thread_id, internal_date, State.NEW, utc_now()),
    ).fetchone()
    return to_email_row(row)


def read_email(connection: sqlite3.Connection, message_id: str) -> EmailRow | None:
    row = connection.execute(
        f"SELECT {EMAIL_COLUMNS} FROM emails WHERE message_id = ?", (message_id,)
    ).fetchone()
    return None if row is None else to_email_row(row)


def set_email_state(connection: sqlite3.Connection, message_id: str, state: State) -> EmailRow:
    row = connection.execute(
        f"UPDATE emails SET state = ?, updated_at = ? WHERE message_id = ? RETURNING {EMAIL_COLUMNS}",
        (state, utc_now(), message_id),
    ).fetchone()
    if row is None:
        raise EmailNotFound(message_id)
    return to_email_row(row)


def raise_attempts(connection: sqlite3.Connection, message_id: str) -> EmailRow:
    row = connection.execute(
        f"UPDATE emails SET attempts = attempts + 1, updated_at = ? WHERE message_id = ?"
        f" RETURNING {EMAIL_COLUMNS}",
        (utc_now(), message_id),
    ).fetchone()
    if row is None:
        raise EmailNotFound(message_id)
    return to_email_row(row)


def set_email_classifying(
    connection: sqlite3.Connection, message_id: str, internal: bool
) -> EmailRow:
    row = connection.execute(
        f"UPDATE emails SET state = ?, internal = ?, updated_at = ? WHERE message_id = ?"
        f" RETURNING {EMAIL_COLUMNS}",
        (State.CLASSIFYING, internal, utc_now(), message_id),
    ).fetchone()
    if row is None:
        raise EmailNotFound(message_id)
    return to_email_row(row)


def set_email_classified(connection: sqlite3.Connection, message_id: str, triage: str) -> EmailRow:
    row = connection.execute(
        f"UPDATE emails SET state = ?, triage = ?, updated_at = ? WHERE message_id = ?"
        f" RETURNING {EMAIL_COLUMNS}",
        (State.CLASSIFIED, triage, utc_now(), message_id),
    ).fetchone()
    if row is None:
        raise EmailNotFound(message_id)
    return to_email_row(row)


@dataclass(frozen=True)
class AuditRow:
    id: int
    at: str
    message_id: str
    thread_id: str
    label: str
    urgent: bool | None
    action: str
    outcome: State
    detail: str


def insert_audit(
    connection: sqlite3.Connection,
    message_id: str,
    thread_id: str,
    label: str,
    urgent: bool | None,
    action: str,
    outcome: State,
    detail: str,
) -> AuditRow:
    at = utc_now()
    row = connection.execute(
        "INSERT INTO audit (at, message_id, thread_id, label, urgent, action, outcome, detail)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
        (at, message_id, thread_id, label, urgent, action, outcome, detail),
    ).fetchone()
    return AuditRow(
        id=int(str(row[0])),
        at=at,
        message_id=message_id,
        thread_id=thread_id,
        label=label,
        urgent=urgent,
        action=action,
        outcome=outcome,
        detail=detail,
    )


def delete_audit_rows(connection: sqlite3.Connection, message_id: str) -> str:
    connection.execute("DELETE FROM audit WHERE message_id = ?", (message_id,))
    return message_id


def read_new_emails(connection: sqlite3.Connection) -> tuple[EmailRow, ...]:
    rows = connection.execute(
        f"SELECT {EMAIL_COLUMNS} FROM emails WHERE state = ? ORDER BY internal_date",
        (State.NEW,),
    ).fetchall()
    return tuple(to_email_row(row) for row in rows)


def read_processed_emails(connection: sqlite3.Connection) -> tuple[EmailRow, ...]:
    rows = connection.execute(
        f"SELECT {EMAIL_COLUMNS} FROM emails WHERE state != ? ORDER BY internal_date",
        (State.NEW,),
    ).fetchall()
    return tuple(to_email_row(row) for row in rows)


def reset_email(connection: sqlite3.Connection, message_id: str) -> EmailRow:
    delete_audit_rows(connection, message_id)
    row = connection.execute(
        f"UPDATE emails SET state = ?, attempts = 0, internal = NULL, triage = NULL,"
        f" updated_at = ? WHERE message_id = ? RETURNING {EMAIL_COLUMNS}",
        (State.NEW, utc_now(), message_id),
    ).fetchone()
    if row is None:
        raise EmailNotFound(message_id)
    return to_email_row(row)


def delete_email(connection: sqlite3.Connection, message_id: str) -> str:
    delete_audit_rows(connection, message_id)
    connection.execute("DELETE FROM emails WHERE message_id = ?", (message_id,))
    return message_id


def read_known_ids(connection: sqlite3.Connection, message_ids: list[str]) -> frozenset[str]:
    if not message_ids:
        return frozenset()
    placeholders = ", ".join("?" for _ in message_ids)
    rows = connection.execute(
        f"SELECT message_id FROM emails WHERE message_id IN ({placeholders})", message_ids
    ).fetchall()
    return frozenset(str(row[0]) for row in rows)


def read_history_id(connection: sqlite3.Connection) -> str | None:
    row = connection.execute("SELECT value FROM meta WHERE key = ?", (HISTORY_ID_KEY,)).fetchone()
    return None if row is None else str(row[0])


def write_history_id(connection: sqlite3.Connection, history_id: str) -> str:
    connection.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?)"
        " ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        (HISTORY_ID_KEY, history_id),
    )
    return history_id
