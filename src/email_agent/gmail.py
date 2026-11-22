from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from googleapiclient.discovery import build  # pyright: ignore[reportUnknownVariableType]
from googleapiclient.errors import HttpError

from email_agent.google_auth import load_credentials

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1 import GmailResource  # pyright: ignore[reportMissingModuleSource]
    from googleapiclient._apis.gmail.v1.schemas import Message  # pyright: ignore[reportMissingModuleSource]

HTTP_NOT_FOUND = 404

def build_gmail(secrets_dir: Path) -> GmailResource:
    credentials = load_credentials(secrets_dir / "gmail_token", "Gmail")
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


def remove_labels(gmail: GmailResource, message_id: str, label_ids: list[str]) -> bool:
    try:
        gmail.users().messages().modify(
            userId="me", id=message_id, body={"removeLabelIds": label_ids}
        ).execute()
    except HttpError as error:
        if error.status_code == HTTP_NOT_FOUND:
            return False
        raise
    return True


def modify_labels(
    gmail: GmailResource, message_id: str, add_label_ids: list[str], remove_label_ids: list[str]
) -> str:
    gmail.users().messages().modify(
        userId="me",
        id=message_id,
        body={"addLabelIds": add_label_ids, "removeLabelIds": remove_label_ids},
    ).execute()
    return message_id


class HistoryExpired(Exception):
    pass


@dataclass(frozen=True)
class MessageMetadata:
    message_id: str
    thread_id: str
    internal_date: int
    subject: str


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


def list_message_ids(gmail: GmailResource, label_ids: list[str]) -> list[str]:
    message_ids: list[str] = []
    page_token: str | None = None
    while True:
        response = (
            gmail.users()
            .messages()
            .list(
                userId="me",
                labelIds=label_ids,
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


def get_message_metadata(gmail: GmailResource, message_id: str) -> MessageMetadata | None:
    try:
        message = (
            gmail.users()
            .messages()
            .get(userId="me", id=message_id, format="metadata", metadataHeaders=["Subject"])
            .execute()
        )
    except HttpError as error:
        if error.status_code == HTTP_NOT_FOUND:
            return None
        raise
    subjects = [
        header.get("value", "")
        for header in message.get("payload", {}).get("headers", [])
        if header.get("name", "").casefold() == "subject"
    ]
    return MessageMetadata(
        message_id=message_id,
        thread_id=message.get("threadId", ""),
        internal_date=int(message.get("internalDate", "0")),
        subject=subjects[0] if subjects else "",
    )


def get_full_message(gmail: GmailResource, message_id: str) -> Message | None:
    try:
        return gmail.users().messages().get(userId="me", id=message_id, format="full").execute()
    except HttpError as error:
        if error.status_code == HTTP_NOT_FOUND:
            return None
        raise
