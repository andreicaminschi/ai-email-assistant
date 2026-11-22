from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport import Request as TransportRequest
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


class TokenError(Exception):
    def __init__(self, service_name: str) -> None:
        super().__init__(service_name)
        self.service_name = service_name


class TokenMissing(TokenError):
    pass


class TokenRejected(TokenError):
    pass


class ServiceCredentials(Credentials):
    """Refresh failures raise TokenRejected, mid-run too."""

    service_name: str = ""

    def refresh(self, request: TransportRequest) -> None:
        try:
            super().refresh(request)  # pyright: ignore[reportUnknownMemberType]
        except RefreshError:
            raise TokenRejected(self.service_name) from None


def load_credentials(token_file: Path, service_name: str) -> ServiceCredentials:
    if not token_file.is_file():
        raise TokenMissing(service_name)
    try:
        credentials = ServiceCredentials.from_authorized_user_file(str(token_file))  # pyright: ignore[reportUnknownMemberType]
    except (PermissionError, ValueError):
        raise TokenRejected(service_name) from None
    credentials.service_name = service_name
    credentials.refresh(Request())
    return credentials
