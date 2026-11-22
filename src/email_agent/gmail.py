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
