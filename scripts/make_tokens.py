import os
import sys
from pathlib import Path
from typing import cast

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow  # pyright: ignore[reportMissingTypeStubs]

SECRETS_DIR = Path(__file__).resolve().parent.parent / "secrets"
CLIENT_SECRET_FILE = SECRETS_DIR / "client_secret.json"

GMAIL_SCOPES = ("https://www.googleapis.com/auth/gmail.modify",)
CALENDAR_SCOPES = (
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
)

TOKENS = (
    ("Gmail", "gmail_token", GMAIL_SCOPES),
    ("Calendar", "calendar_token", CALENDAR_SCOPES),
)


def request_credentials(scopes: tuple[str, ...]) -> Credentials:
    flow = InstalledAppFlow.from_client_secrets_file(  # pyright: ignore[reportUnknownMemberType]
        str(CLIENT_SECRET_FILE), scopes=list(scopes)
    )
    return cast(Credentials, flow.run_local_server(port=0, prompt="consent"))  # pyright: ignore[reportUnknownMemberType]


def main() -> int:
    if not CLIENT_SECRET_FILE.is_file():
        print(
            "Missing secrets/client_secret.json. Download the Desktop OAuth client JSON "
            "from Google Cloud Console > APIs & Services > Credentials and save it there."
        )
        return 1
    agent_email = os.environ.get("AGENT_EMAIL", "").strip()
    if not agent_email:
        print("Missing AGENT_EMAIL. Run: uv run --env-file .env scripts/make_tokens.py")
        return 1
    for service, file_name, scopes in TOKENS:
        print(f"Sign in as {agent_email} to grant {service} access.")
        credentials = request_credentials(scopes)
        token_json = credentials.to_json()  # pyright: ignore[reportUnknownMemberType]
        (SECRETS_DIR / file_name).write_text(token_json, encoding="utf-8")
        print(f"Wrote secrets/{file_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
