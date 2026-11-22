import os
import sqlite3
import sys
import time
from importlib.metadata import version

from email_agent.config import RunMode, SettingsError, load_settings, strip_and_drop_empty
from email_agent.db import database_path, open_database
from email_agent.message import ParsedEmail, fetch_parsed_email
from email_agent.poller import poll_once
from email_agent.startup import (
    SPAM_LABEL_ID,
    StartupError,
    check_connection,
    list_agent_label_names,
    reset_processed_emails,
    set_up_labels,
)


PREVIEW_LENGTH = 120


def print_parsed_email(parsed: ParsedEmail) -> None:
    sender = f"{parsed.from_name} <{parsed.from_address}>" if parsed.from_name else parsed.from_address
    print(
        f"  from {sender}, body {len(parsed.label_body)} chars,"
        f" {len(parsed.links)} links, {len(parsed.attachments)} attachments"
    )
    preview = " ".join(parsed.follow_up_body.split())[:PREVIEW_LENGTH]
    print(f"  follow-up: {preview}")
    for attachment in parsed.attachments:
        print(f"  attachment {attachment.name} {attachment.size} bytes")


def main() -> None:
    try:
        settings = load_settings(strip_and_drop_empty(os.environ))
    except SettingsError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from None
    print(f"email-agent {version('email-agent')} starting as {settings.agent_email}")
    try:
        gmail, _calendar = check_connection(settings)
        print("Connection ready")
        label_setup = set_up_labels(gmail, list_agent_label_names(settings.run_mode))
    except StartupError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from None
    if label_setup.created_names:
        print(f"Created labels: {', '.join(label_setup.created_names)}")
    else:
        print("Every label exists")
    print(f"Labels ready: {len(label_setup.label_ids)}")
    db_path = database_path(settings.data_dir)
    try:
        connection = open_database(settings.data_dir)
    except (sqlite3.Error, OSError) as error:
        print(f"Could not open database {db_path}: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    print(f"Database ready: {db_path}")
    if settings.run_mode is RunMode.DEV:
        agent_label_ids = [
            label_id for label_id in label_setup.label_ids.values() if label_id != SPAM_LABEL_ID
        ]
        try:
            dev_reset = reset_processed_emails(gmail, connection, agent_label_ids)
        except StartupError as error:
            print(error, file=sys.stderr)
            raise SystemExit(1) from None
        print(f"Dev reset: {len(dev_reset.reset_ids)} emails")
        for message_id in dev_reset.dropped_ids:
            print(f"Dropped {message_id}: gone from Gmail")
    sync_label_ids = ["INBOX"] if settings.run_mode is RunMode.DEV else ["INBOX", "UNREAD"]
    while True:
        result = poll_once(gmail, connection, sync_label_ids)
        for email in result.new_emails:
            print(f"{email.row.state} {email.row.message_id} {email.subject or '(no subject)'}")
            parsed = fetch_parsed_email(gmail, email.row.message_id)
            if parsed is None:
                print(f"Skipped {email.row.message_id}: gone before parse")
                continue
            print_parsed_email(parsed)
        for message_id in result.gone_ids:
            print(f"Skipped {message_id}: gone before fetch")
        time.sleep(settings.poll_seconds)


if __name__ == "__main__":
    main()
