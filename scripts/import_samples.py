import base64
import os
import sys
from email import message_from_string, policy
from email.utils import formatdate, make_msgid
from pathlib import Path

from googleapiclient.errors import HttpError

from email_agent.gmail import build_gmail, get_account_email
from email_agent.google_auth import TokenError

REPO_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = REPO_DIR / "samples"
AGENT_EMAIL_PLACEHOLDER = "{{AGENT_EMAIL}}"


def build_raw_sample(sample_text: str, agent_email: str) -> str:
    message = message_from_string(
        sample_text.replace(AGENT_EMAIL_PLACEHOLDER, agent_email), policy=policy.default
    )
    del message["Message-ID"]
    del message["Date"]
    message["Message-ID"] = make_msgid(domain="samples.example.com")
    message["Date"] = formatdate(localtime=True)
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


def main() -> int:
    agent_email = os.environ.get("AGENT_EMAIL", "").strip()
    if not agent_email:
        print("Missing AGENT_EMAIL. Run: uv run --env-file .env scripts/import_samples.py")
        return 1
    secrets_dir = Path(os.environ.get("SECRETS_DIR", "").strip() or REPO_DIR / "secrets")
    try:
        gmail = build_gmail(secrets_dir)
        account_email = get_account_email(gmail)
    except TokenError:
        print(f"Gmail token missing or rejected in {secrets_dir}, rerun the token script")
        return 1
    if account_email.casefold() != agent_email.casefold():
        print(f"Gmail token is for {account_email}, not {agent_email}")
        return 1
    sample_files = sorted(SAMPLES_DIR.glob("*.eml"))
    for sample_file in sample_files:
        raw = build_raw_sample(sample_file.read_text(encoding="utf-8"), agent_email)
        try:
            gmail.users().messages().import_(
                userId="me",
                body={"raw": raw, "labelIds": ["INBOX", "UNREAD"]},
                internalDateSource="dateHeader",
                neverMarkSpam=True,
            ).execute()
        except HttpError as error:
            print(f"Could not import {sample_file.name}: {error.reason}")
            return 1
        print(f"Imported {sample_file.name}")
    print(f"Imported {len(sample_files)} samples into {agent_email}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
