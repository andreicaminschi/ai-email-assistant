import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from googleapiclient.errors import HttpError

from email_agent.calendar import build_calendar, get_primary_calendar_id
from email_agent.config import RunMode, Settings
from email_agent.db import delete_email, read_processed_emails, reset_email
from email_agent.gmail import build_gmail, create_label, get_account_email, list_labels, remove_labels
from email_agent.google_auth import TokenError, TokenMissing

if TYPE_CHECKING:
    from googleapiclient._apis.calendar.v3 import CalendarResource  # pyright: ignore[reportMissingModuleSource]
    from googleapiclient._apis.gmail.v1 import GmailResource  # pyright: ignore[reportMissingModuleSource]


REQUIRED_LABELS = (
    "MEETING_REQUEST",
    "TASK",
    "INFO_ONLY",
    "SALES_OUTREACH",
    "MARKETING",
    "URGENT",
    "Finance",
)
DEV_LABELS = ("This is spam", "This is archived")
SPAM_LABEL_ID = "SPAM"


class StartupError(Exception):
    pass


@dataclass(frozen=True)
class LabelSetup:
    label_ids: Mapping[str, str]
    created_names: tuple[str, ...]


@dataclass(frozen=True)
class DevReset:
    reset_ids: tuple[str, ...]
    dropped_ids: tuple[str, ...]


def list_agent_label_names(run_mode: RunMode) -> tuple[str, ...]:
    if run_mode is RunMode.DEV:
        return REQUIRED_LABELS + DEV_LABELS
    return REQUIRED_LABELS


def format_token_error(service_name: str, error: TokenError) -> str:
    if isinstance(error, TokenMissing):
        return f"{service_name} token missing"
    return f"{service_name} token rejected, rerun token script"


def check_account(service_name: str, account_email: str, agent_email: str) -> None:
    if account_email.casefold() != agent_email.casefold():
        raise StartupError(f"{service_name} token is for another account")


def format_api_error(service_name: str, error: HttpError) -> str:
    return f"{service_name} API refused the call: {error.reason}"


def check_connection(settings: Settings) -> tuple[GmailResource, CalendarResource]:
    try:
        gmail = build_gmail(settings.secrets_dir)
        gmail_email = get_account_email(gmail)
    except TokenError as error:
        raise StartupError(format_token_error("Gmail", error)) from None
    except HttpError as error:
        raise StartupError(format_api_error("Gmail", error)) from None
    check_account("Gmail", gmail_email, settings.agent_email)
    try:
        calendar = build_calendar(settings.secrets_dir)
        calendar_id = get_primary_calendar_id(calendar)
    except TokenError as error:
        raise StartupError(format_token_error("Calendar", error)) from None
    except HttpError as error:
        raise StartupError(format_api_error("Calendar", error)) from None
    check_account("Calendar", calendar_id, settings.agent_email)
    return gmail, calendar


def create_missing_label(gmail: GmailResource, name: str) -> str:
    try:
        return create_label(gmail, name)
    except HttpError as error:
        raise StartupError(f"Could not create Gmail label {name}: {error.reason}") from None


def set_up_labels(gmail: GmailResource, label_names: tuple[str, ...]) -> LabelSetup:
    try:
        existing_labels = list_labels(gmail)
    except HttpError as error:
        raise StartupError(format_api_error("Gmail", error)) from None
    ids_by_folded_name = {name.casefold(): label_id for name, label_id in existing_labels}
    found_ids = {
        name: ids_by_folded_name[name.casefold()]
        for name in label_names
        if name.casefold() in ids_by_folded_name
    }
    created_names = tuple(name for name in label_names if name not in found_ids)
    created_ids = {name: create_missing_label(gmail, name) for name in created_names}
    label_ids = {**found_ids, **created_ids, "SPAM": SPAM_LABEL_ID}
    return LabelSetup(MappingProxyType(label_ids), created_names)


def reset_processed_emails(
    gmail: GmailResource, connection: sqlite3.Connection, agent_label_ids: list[str]
) -> DevReset:
    reset_ids: list[str] = []
    dropped_ids: list[str] = []
    for row in read_processed_emails(connection):
        try:
            still_in_gmail = remove_labels(gmail, row.message_id, agent_label_ids)
        except HttpError as error:
            raise StartupError(format_api_error("Gmail", error)) from None
        if still_in_gmail:
            reset_ids.append(reset_email(connection, row.message_id).message_id)
        else:
            dropped_ids.append(delete_email(connection, row.message_id))
    return DevReset(tuple(reset_ids), tuple(dropped_ids))
