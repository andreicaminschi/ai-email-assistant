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
CREATE TABLE IF NOT EXISTS sends (
    message_id TEXT NOT NULL,
    template TEXT NOT NULL,
    send_id TEXT NOT NULL,
    state TEXT NOT NULL,
    PRIMARY KEY (message_id, template)
);
CREATE TABLE IF NOT EXISTS approvals (
    forward_thread_id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    original_thread_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    state TEXT NOT NULL,
    sender_email TEXT NOT NULL,
    sender_name TEXT NOT NULL,
    original_subject TEXT NOT NULL,
    meeting_start TEXT,
    meeting_end TEXT,
    latest_sender_rfc_id TEXT NOT NULL,
    updated_at TEXT NOT NULL
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


UNFINISHED_STATES = (State.NEW, State.CLASSIFYING, State.CLASSIFIED, State.ARCHIVED)


class SendState(StrEnum):
    SENDING = "SENDING"
    SENT = "SENT"


@dataclass(frozen=True)
class SendRow:
    message_id: str
    template: str
    send_id: str
    state: SendState


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


def read_unfinished_emails(connection: sqlite3.Connection) -> tuple[EmailRow, ...]:
    placeholders = ", ".join("?" for _ in UNFINISHED_STATES)
    rows = connection.execute(
        f"SELECT {EMAIL_COLUMNS} FROM emails WHERE state IN ({placeholders})"
        f" ORDER BY internal_date",
        UNFINISHED_STATES,
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


def read_send(connection: sqlite3.Connection, message_id: str, template: str) -> SendRow | None:
    row = connection.execute(
        "SELECT send_id, state FROM sends WHERE message_id = ? AND template = ?",
        (message_id, template),
    ).fetchone()
    if row is None:
        return None
    return SendRow(message_id, template, str(row[0]), SendState(row[1]))


def insert_send(
    connection: sqlite3.Connection, message_id: str, template: str, send_id: str
) -> SendRow:
    connection.execute(
        "INSERT INTO sends (message_id, template, send_id, state) VALUES (?, ?, ?, ?)",
        (message_id, template, send_id, SendState.SENDING),
    )
    return SendRow(message_id, template, send_id, SendState.SENDING)


def set_send_sent(connection: sqlite3.Connection, send: SendRow) -> SendRow:
    connection.execute(
        "UPDATE sends SET state = ? WHERE message_id = ? AND template = ?",
        (SendState.SENT, send.message_id, send.template),
    )
    return SendRow(send.message_id, send.template, send.send_id, SendState.SENT)


class ApprovalKind(StrEnum):
    MEETING = "MEETING"
    TASK = "TASK"


APPROVAL_COLUMNS = (
    "forward_thread_id, message_id, original_thread_id, kind, state, sender_email,"
    " sender_name, original_subject, meeting_start, meeting_end, latest_sender_rfc_id,"
    " updated_at"
)


@dataclass(frozen=True)
class ApprovalRow:
    forward_thread_id: str
    message_id: str
    original_thread_id: str
    kind: ApprovalKind
    state: State
    sender_email: str
    sender_name: str
    original_subject: str
    meeting_start: str | None
    meeting_end: str | None
    latest_sender_rfc_id: str
    updated_at: str


def to_approval_row(row: tuple[object, ...]) -> ApprovalRow:
    (
        forward_thread_id,
        message_id,
        original_thread_id,
        kind,
        state,
        sender_email,
        sender_name,
        original_subject,
        meeting_start,
        meeting_end,
        latest_sender_rfc_id,
        updated_at,
    ) = row
    return ApprovalRow(
        forward_thread_id=str(forward_thread_id),
        message_id=str(message_id),
        original_thread_id=str(original_thread_id),
        kind=ApprovalKind(kind),
        state=State(state),
        sender_email=str(sender_email),
        sender_name=str(sender_name),
        original_subject=str(original_subject),
        meeting_start=None if meeting_start is None else str(meeting_start),
        meeting_end=None if meeting_end is None else str(meeting_end),
        latest_sender_rfc_id=str(latest_sender_rfc_id),
        updated_at=str(updated_at),
    )


def save_approval(connection: sqlite3.Connection, approval: ApprovalRow) -> ApprovalRow:
    """A rerun overwrites the row for the same forward thread."""
    row = connection.execute(
        f"INSERT INTO approvals ({APPROVAL_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        f" ON CONFLICT (forward_thread_id) DO UPDATE SET"
        f" message_id = excluded.message_id, original_thread_id = excluded.original_thread_id,"
        f" kind = excluded.kind, state = excluded.state, sender_email = excluded.sender_email,"
        f" sender_name = excluded.sender_name, original_subject = excluded.original_subject,"
        f" meeting_start = excluded.meeting_start, meeting_end = excluded.meeting_end,"
        f" latest_sender_rfc_id = excluded.latest_sender_rfc_id,"
        f" updated_at = excluded.updated_at"
        f" RETURNING {APPROVAL_COLUMNS}",
        (
            approval.forward_thread_id,
            approval.message_id,
            approval.original_thread_id,
            approval.kind,
            approval.state,
            approval.sender_email,
            approval.sender_name,
            approval.original_subject,
            approval.meeting_start,
            approval.meeting_end,
            approval.latest_sender_rfc_id,
            utc_now(),
        ),
    ).fetchone()
    return to_approval_row(row)


def read_approval(connection: sqlite3.Connection, forward_thread_id: str) -> ApprovalRow | None:
    row = connection.execute(
        f"SELECT {APPROVAL_COLUMNS} FROM approvals WHERE forward_thread_id = ?",
        (forward_thread_id,),
    ).fetchone()
    return None if row is None else to_approval_row(row)


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
