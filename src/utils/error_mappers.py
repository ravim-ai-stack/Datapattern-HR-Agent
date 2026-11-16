"""Map AppException error codes to an HTTP status and JSON body."""

from src.constants.constants import HTTP_BAD_REQUEST, HTTP_INTERNAL_ERROR, HTTP_UNPROCESSABLE
from src.utils import error_codes

_STATUS_BY_CODE = {
    error_codes.LETTER_VALIDATION_FAILED: HTTP_UNPROCESSABLE,
    error_codes.DOWNLOAD_FAILED: HTTP_INTERNAL_ERROR,
    error_codes.CHAT_FAILED: HTTP_INTERNAL_ERROR,
    error_codes.INTERNAL_ERROR: HTTP_INTERNAL_ERROR,
}


def map_error(exc):
    """Return (body, status). The text is exposed as both `error` (letter APIs)
    and `message` (email API) because the frontend reads one or the other."""
    status = _STATUS_BY_CODE.get(exc.code, HTTP_BAD_REQUEST)
    body = {"success": False, "error": exc.message, "message": exc.message, "code": exc.code}
    body.update(exc.details)
    return body, status
