from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


class TokenError(Exception):
    pass


class TokenMissing(TokenError):
    pass


class TokenRejected(TokenError):
    pass


def load_credentials(token_file: Path) -> Credentials:
    if not token_file.is_file():
        raise TokenMissing
    try:
        credentials = Credentials.from_authorized_user_file(str(token_file))  # pyright: ignore[reportUnknownMemberType]
        credentials.refresh(Request())  # pyright: ignore[reportUnknownMemberType]
    except (PermissionError, ValueError, RefreshError):
        raise TokenRejected from None
    return credentials
