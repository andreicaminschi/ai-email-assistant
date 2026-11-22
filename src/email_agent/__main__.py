import os
import sqlite3
import sys
from importlib.metadata import version

from email_agent.config import SettingsError, load_settings, strip_and_drop_empty
from email_agent.db import database_path, open_database
from email_agent.startup import StartupError, check_connection, set_up_labels


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
        label_setup = set_up_labels(gmail)
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
    connection.close()


if __name__ == "__main__":
    main()
