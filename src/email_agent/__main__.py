import os
import sys
from importlib.metadata import version

from email_agent.config import SettingsError, load_settings, strip_and_drop_empty


def main() -> None:
    try:
        settings = load_settings(strip_and_drop_empty(os.environ))
    except SettingsError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from None
    print(f"email-agent {version('email-agent')} starting as {settings.agent_email}")


if __name__ == "__main__":
    main()
