from __future__ import annotations


class OAuthTokenError(Exception):
    """Raised when an IdP token cannot be verified (safe to show a generic message to clients)."""

    def __init__(self, message: str, *, status_code: int = 401) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class OAuthAccountConflictError(Exception):
    """Raised when linking would violate uniqueness / integrity rules."""

    def __init__(self, message: str, *, status_code: int = 409) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
