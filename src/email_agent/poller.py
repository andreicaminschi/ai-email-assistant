import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

from email_agent.db import EmailRow, insert_email, read_history_id, read_known_ids, write_history_id
from email_agent.gmail import (
    HistoryExpired,
    MessageMetadata,
    get_history_id,
    get_message_metadata,
    list_added_inbox_ids,
    list_unread_inbox_ids,
)

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1 import GmailResource  # pyright: ignore[reportMissingModuleSource]


@dataclass(frozen=True)
class NewEmail:
    row: EmailRow
    subject: str


@dataclass(frozen=True)
class PollResult:
    new_emails: tuple[NewEmail, ...]
    gone_ids: tuple[str, ...]


def full_sync(gmail: GmailResource) -> tuple[list[str], str]:
    history_id = get_history_id(gmail)
    return list_unread_inbox_ids(gmail), history_id


def list_new_ids(gmail: GmailResource, saved_history_id: str | None) -> tuple[list[str], str]:
    if saved_history_id is None:
        return full_sync(gmail)
    try:
        return list_added_inbox_ids(gmail, saved_history_id)
    except HistoryExpired:
        return full_sync(gmail)


def poll_once(gmail: GmailResource, connection: sqlite3.Connection) -> PollResult:
    message_ids, history_id = list_new_ids(gmail, read_history_id(connection))
    known_ids = read_known_ids(connection, message_ids)
    unknown_ids = [message_id for message_id in message_ids if message_id not in known_ids]
    fetched = {message_id: get_message_metadata(gmail, message_id) for message_id in unknown_ids}
    present: list[MessageMetadata] = [message for message in fetched.values() if message is not None]
    in_arrival_order = sorted(present, key=lambda message: message.internal_date)
    new_emails = tuple(
        NewEmail(
            row=insert_email(connection, message.message_id, message.thread_id, message.internal_date),
            subject=message.subject,
        )
        for message in in_arrival_order
    )
    write_history_id(connection, history_id)
    gone_ids = tuple(message_id for message_id, message in fetched.items() if message is None)
    return PollResult(new_emails=new_emails, gone_ids=gone_ids)
