from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from email_agent.audit import Action
from email_agent.classify.models import Label, Triage
from email_agent.config import RunMode
from email_agent.db import State
from email_agent.message import ParsedEmail

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


@dataclass(frozen=True)
class HandlerResult:
    add_label_ids: tuple[str, ...]
    remove_label_ids: tuple[str, ...]
    action: Action
    state: State


type Handler = Callable[[HandlerInput], HandlerResult]


def read_tag_ids(handler_input: HandlerInput) -> tuple[str, ...]:
    """The email's label, plus URGENT when flagged."""
    label_ids = handler_input.label_ids
    label_id = label_ids[handler_input.triage.label]
    if handler_input.triage.urgent:
        return (label_id, label_ids[URGENT_LABEL])
    return (label_id,)


def read_archive_changes(handler_input: HandlerInput) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """
    @example
    read_archive_changes(dev_input)   # → (("<This is archived id>",), ())
    read_archive_changes(prod_input)  # → ((), ("INBOX",))
    """
    if handler_input.run_mode is RunMode.DEV:
        return (handler_input.label_ids[DEV_ARCHIVE_LABEL],), ()
    return (), (INBOX_LABEL_ID,)


def tag_with_label(handler_input: HandlerInput) -> HandlerResult:
    return HandlerResult(read_tag_ids(handler_input), (), Action.LABEL_ONLY, State.DONE)


def file_info_only(handler_input: HandlerInput) -> HandlerResult:
    if not handler_input.triage.is_invoice:
        return tag_with_label(handler_input)
    finance_id = handler_input.label_ids[FINANCE_LABEL]
    archive_add, archive_remove = read_archive_changes(handler_input)
    add_ids = (*read_tag_ids(handler_input), finance_id, *archive_add)
    return HandlerResult(add_ids, archive_remove, Action.FINANCE_AND_ARCHIVE, State.DONE)


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
        Label.MARKETING: tag_with_label,
        Label.SALES_OUTREACH: tag_with_label,
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
