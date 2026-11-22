import sqlite3
import uuid
from dataclasses import dataclass
from email import policy
from email.message import EmailMessage
from typing import TYPE_CHECKING

from email_agent.config import RunMode, Settings
from email_agent.db import SendState, insert_send, read_send, set_send_sent
from email_agent.gmail import find_sent_thread_id, send_raw_message
from email_agent.templates import RenderedEmail

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1 import GmailResource  # pyright: ignore[reportMissingModuleSource]

SEND_ID_HEADER = "X-Agent-Send-Id"


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    rendered: RenderedEmail
    thread_id: str | None
    in_reply_to: str


def build_mime(from_address: str, send_id: str, outgoing: OutgoingEmail) -> bytes:
    message = EmailMessage()
    message["From"] = from_address
    message["To"] = outgoing.to
    message["Subject"] = outgoing.rendered.subject
    message[SEND_ID_HEADER] = send_id
    if outgoing.in_reply_to:
        message["In-Reply-To"] = outgoing.in_reply_to
        message["References"] = outgoing.in_reply_to
    message.set_content(outgoing.rendered.body)
    return message.as_bytes(policy=policy.SMTP)


def find_sent_send(gmail: GmailResource, send_id: str, outgoing: OutgoingEmail) -> str | None:
    return find_sent_thread_id(
        gmail, outgoing.to, outgoing.rendered.subject, SEND_ID_HEADER, send_id
    )


def is_dev_printed(settings: Settings, outgoing: OutgoingEmail) -> bool:
    """Dev sends only to the manager."""
    if settings.run_mode is not RunMode.DEV:
        return False
    return outgoing.to.casefold() != settings.manager_email.casefold()


def send_once(
    connection: sqlite3.Connection,
    gmail: GmailResource,
    settings: Settings,
    source_message_id: str,
    outgoing: OutgoingEmail,
) -> str:
    """
    @example
    send_once(connection, gmail, settings, "18c2", decline)  # no row → SENDING → send → SENT
    send_once(connection, gmail, settings, "18c2", decline)  # SENT → no send, same threadId
    send_once(connection, gmail, dev_settings, "18c2", decline)  # prints, no row
    send_once(connection, gmail, dev_settings, "18c2", task_forward)  # to manager: sent
    """
    template = outgoing.rendered.name
    if is_dev_printed(settings, outgoing):
        print(f"DEV would send {template} to {outgoing.to}")
        return ""
    send = read_send(connection, source_message_id, template)
    if send is not None and send.state is SendState.SENT:
        return find_sent_send(gmail, send.send_id, outgoing) or ""
    if send is None:
        send = insert_send(connection, source_message_id, template, uuid.uuid4().hex)
    else:
        # SENDING: may have gone out
        sent_thread_id = find_sent_send(gmail, send.send_id, outgoing)
        if sent_thread_id is not None:
            set_send_sent(connection, send)
            return sent_thread_id
    raw = build_mime(settings.agent_email, send.send_id, outgoing)
    thread_id = send_raw_message(gmail, raw, outgoing.thread_id)
    set_send_sent(connection, send)
    return thread_id
