from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from email_agent.audit import Action
from email_agent.classify.models import Label, Triage
from email_agent.config import RunMode
from email_agent.db import State
from email_agent.message import ParsedEmail
from email_agent.sender import OutgoingEmail
from email_agent.templates import (
    TemplateName,
    read_sender_name,
    render_template,
    strip_reply_prefix,
)

DEV_SPAM_LABEL = "This is spam"
DEV_ARCHIVE_LABEL = "This is archived"
URGENT_LABEL = "URGENT"
FINANCE_LABEL = "Finance"
INBOX_LABEL_ID = "INBOX"


@dataclass(frozen=True)
class HandlerInput:
    parsed: ParsedEmail
    triage: Triage
    label_ids: Mapping[str, str]
    run_mode: RunMode
    send_sales_decline: bool


@dataclass(frozen=True)
class ArchiveChanges:
    add_label_ids: tuple[str, ...]
    remove_label_ids: tuple[str, ...]


@dataclass(frozen=True)
class HandlerResult:
    """Order: labels, sends, archive."""

    add_label_ids: tuple[str, ...]
    remove_label_ids: tuple[str, ...]
    action: Action
    state: State
    sends: tuple[OutgoingEmail, ...] = ()
    archive: ArchiveChanges | None = None


type Handler = Callable[[HandlerInput], HandlerResult]


def read_tag_ids(handler_input: HandlerInput) -> tuple[str, ...]:
    """The email's label, plus URGENT when flagged."""
    label_ids = handler_input.label_ids
    label_id = label_ids[handler_input.triage.label]
    if handler_input.triage.urgent:
        return (label_id, label_ids[URGENT_LABEL])
    return (label_id,)


def read_archive_changes(handler_input: HandlerInput) -> ArchiveChanges:
    """
    @example
    read_archive_changes(dev_input)   # → ArchiveChanges(("<This is archived id>",), ())
    read_archive_changes(prod_input)  # → ArchiveChanges((), ("INBOX",))
    """
    if handler_input.run_mode is RunMode.DEV:
        return ArchiveChanges((handler_input.label_ids[DEV_ARCHIVE_LABEL],), ())
    return ArchiveChanges((), (INBOX_LABEL_ID,))


def build_sales_decline(parsed: ParsedEmail) -> OutgoingEmail:
    values = {
        "sender_name": read_sender_name(parsed.from_name, parsed.from_address),
        "original_subject": strip_reply_prefix(parsed.subject),
    }
    rendered = render_template(TemplateName.SALES_DECLINE, values, urgent=False)
    return OutgoingEmail(
        to=parsed.reply_to or parsed.from_address,
        rendered=rendered,
        thread_id=parsed.thread_id,
        in_reply_to=parsed.rfc_message_id,
    )


def tag_with_label(handler_input: HandlerInput) -> HandlerResult:
    return HandlerResult(read_tag_ids(handler_input), (), Action.LABEL_ONLY, State.DONE)


def archive_with_label(handler_input: HandlerInput) -> HandlerResult:
    return HandlerResult(
        read_tag_ids(handler_input),
        (),
        Action.ARCHIVE,
        State.DONE,
        archive=read_archive_changes(handler_input),
    )


def decline_and_archive(handler_input: HandlerInput) -> HandlerResult:
    if not handler_input.send_sales_decline:
        return archive_with_label(handler_input)
    return HandlerResult(
        read_tag_ids(handler_input),
        (),
        Action.DECLINE_AND_ARCHIVE,
        State.DONE,
        sends=(build_sales_decline(handler_input.parsed),),
        archive=read_archive_changes(handler_input),
    )


def file_info_only(handler_input: HandlerInput) -> HandlerResult:
    if not handler_input.triage.is_invoice:
        return tag_with_label(handler_input)
    finance_id = handler_input.label_ids[FINANCE_LABEL]
    return HandlerResult(
        (*read_tag_ids(handler_input), finance_id),
        (),
        Action.FINANCE_AND_ARCHIVE,
        State.DONE,
        archive=read_archive_changes(handler_input),
    )


def move_to_spam(handler_input: HandlerInput) -> HandlerResult:
    label_ids = handler_input.label_ids
    if handler_input.run_mode is RunMode.DEV:
        return HandlerResult((label_ids[DEV_SPAM_LABEL],), (), Action.MOVE_TO_SPAM, State.DONE)
    return HandlerResult(
        (label_ids[Label.SPAM],), (INBOX_LABEL_ID,), Action.MOVE_TO_SPAM, State.DONE
    )


def do_nothing(_handler_input: HandlerInput) -> HandlerResult:
    return HandlerResult((), (), Action.NONE_UNCLASSIFIED, State.DONE)


EXTERNAL_HANDLERS: Mapping[Label, Handler] = MappingProxyType(
    {
        Label.MARKETING: archive_with_label,
        Label.SALES_OUTREACH: decline_and_archive,
        Label.INFO_ONLY: file_info_only,
        Label.SPAM: move_to_spam,
        Label.MEETING_REQUEST: tag_with_label,
        Label.TASK: tag_with_label,
        Label.UNCLASSIFIED: do_nothing,
    }
)

INTERNAL_HANDLERS: Mapping[Label, Handler] = MappingProxyType(
    {
        Label.MEETING_REQUEST: EXTERNAL_HANDLERS[Label.MEETING_REQUEST],
        Label.TASK: EXTERNAL_HANDLERS[Label.TASK],
        Label.UNCLASSIFIED: do_nothing,
    }
)


def find_handler(internal: bool, label: Label) -> Handler:
    if internal:
        # Other labels: unclassified
        return INTERNAL_HANDLERS.get(label, do_nothing)
    return EXTERNAL_HANDLERS[label]
