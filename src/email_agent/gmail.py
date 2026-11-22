from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from googleapiclient.discovery import build  # pyright: ignore[reportUnknownVariableType]
from googleapiclient.errors import HttpError

from email_agent.google_auth import load_credentials

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1 import GmailResource  # pyright: ignore[reportMissingModuleSource]

HTTP_NOT_FOUND = 404

def build_gmail(secrets_dir: Path) -> GmailResource:
    credentials = load_credentials(secrets_dir / "gmail_token")
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def get_account_email(gmail: GmailResource) -> str:
    profile = gmail.users().getProfile(userId="me").execute()
    return profile.get("emailAddress", "")


def list_labels(gmail: GmailResource) -> list[tuple[str, str]]:
    response = gmail.users().labels().list(userId="me").execute()
    return [(label.get("name", ""), label.get("id", "")) for label in response.get("labels", [])]


def create_label(gmail: GmailResource, name: str) -> str:
    label = gmail.users().labels().create(userId="me", body={"name": name}).execute()
    return label.get("id", "")


class HistoryExpired(Exception):
    pass


@dataclass(frozen=True)
class MinimalMessage:
    message_id: str
    thread_id: str
    internal_date: int


def get_history_id(gmail: GmailResource) -> str:
    profile = gmail.users().getProfile(userId="me").execute()
    return profile.get("historyId", "")


def list_added_inbox_ids(gmail: GmailResource, start_history_id: str) -> tuple[list[str], str]:
    message_ids: list[str] = []
    page_token: str | None = None
    while True:
        try:
            response = (
                gmail.users()
                .history()
                .list(
                    userId="me",
                    startHistoryId=start_history_id,
                    labelId="INBOX",
                    historyTypes=["messageAdded"],
                    pageToken=page_token,
                )
                .execute()
            )
        except HttpError as error:
            if error.status_code == HTTP_NOT_FOUND:
                raise HistoryExpired(start_history_id) from None
            raise
        message_ids.extend(
            message_id
            for record in response.get("history", [])
            for added in record.get("messagesAdded", [])
            if (message_id := added.get("message", {}).get("id"))
        )
        page_token = response.get("nextPageToken")
        if page_token is None:
            return list(dict.fromkeys(message_ids)), response.get("historyId", start_history_id)


def list_unread_inbox_ids(gmail: GmailResource) -> list[str]:
    message_ids: list[str] = []
    page_token: str | None = None
    while True:
        response = (
            gmail.users()
            .messages()
            .list(
                userId="me",
                labelIds=["INBOX", "UNREAD"],
                pageToken=page_token,
            )
            .execute()
        )
        message_ids.extend(
            message_id
            for message in response.get("messages", [])
            if (message_id := message.get("id"))
        )
        page_token = response.get("nextPageToken")
        if page_token is None:
            return message_ids


def get_minimal_message(gmail: GmailResource, message_id: str) -> MinimalMessage | None:
    try:
        message = gmail.users().messages().get(userId="me", id=message_id, format="minimal").execute()
    except HttpError as error:
        if error.status_code == HTTP_NOT_FOUND:
            return None
        raise
    return MinimalMessage(
        message_id=message_id,
        thread_id=message.get("threadId", ""),
        internal_date=int(message.get("internalDate", "0")),
    )
