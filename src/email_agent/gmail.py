from pathlib import Path
from typing import TYPE_CHECKING

from googleapiclient.discovery import build  # pyright: ignore[reportUnknownVariableType]

from email_agent.google_auth import load_credentials

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1 import GmailResource  # pyright: ignore[reportMissingModuleSource]


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
