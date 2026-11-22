import json
import sqlite3
from dataclasses import asdict
from enum import StrEnum

from email_agent.db import AuditRow, State, insert_audit


class Action(StrEnum):
    NONE = "none"
    LABEL_ONLY = "label_only"
    NONE_UNCLASSIFIED = "none_unclassified"
    FINANCE_AND_ARCHIVE = "finance_and_archive"
    MOVE_TO_SPAM = "move_to_spam"
    ARCHIVE = "archive"
    DECLINE_AND_ARCHIVE = "decline_and_archive"
    FORWARD_FOR_APPROVAL = "forward_for_approval"
    ASK_FOR_DATE = "ask_for_date"
    IGNORE_REPLY = "ignore_reply"
    SEND_TASK_APPROVED = "send_task_approved"
    SEND_TASK_REJECTED = "send_task_rejected"
    CREATE_EVENT = "create_event"
    SEND_MEETING_DECLINE = "send_meeting_decline"


def format_audit_line(entry: AuditRow) -> str:
    return json.dumps(asdict(entry))


def write_audit_entry(
    connection: sqlite3.Connection,
    message_id: str,
    thread_id: str,
    action: Action,
    outcome: State,
    detail: str,
    label: str = "",
    urgent: bool | None = None,
) -> AuditRow:
    entry = insert_audit(connection, message_id, thread_id, label, urgent, action, outcome, detail)
    print(format_audit_line(entry))
    return entry
