import os
import sys
from importlib.metadata import version

from email_agent.config import SettingsError, load_settings, strip_and_drop_empty
from email_agent.startup import StartupError, check_connection


def main() -> None:
    try:
        settings = load_settings(strip_and_drop_empty(os.environ))
    except SettingsError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from None
    print(f"email-agent {version('email-agent')} starting as {settings.agent_email}")
    try:
        check_connection(settings)
    except StartupError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from None
    print("Connection ready")


if __name__ == "__main__":
    main()
