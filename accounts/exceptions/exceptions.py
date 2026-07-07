"""Custom exceptions for OAuth / social IdP authentication flows."""


class OAuthTokenError(Exception):
    """Raised when the ID token is invalid, expired, or fails verification."""

    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class OAuthAccountConflictError(Exception):
    """Raised when the Google email is already tied to an account via a different auth method."""
    pass