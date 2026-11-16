"""Base exception for expected, user-facing failures."""

from src.utils import error_codes


class AppException(Exception):
    """Raised anywhere in the service/route layers. `code` is mapped to an HTTP
    status by error_mappers; `message` is shown to the user; `details` carries
    any extra payload (e.g. the validation result)."""

    def __init__(self, code=error_codes.INTERNAL_ERROR, message="", details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
