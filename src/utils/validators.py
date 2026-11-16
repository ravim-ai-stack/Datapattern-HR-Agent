"""Shared request validation used by the service layer."""

import re

from src.constants.constants import LETTER_TYPES, TEMPLATE_BACKED_LETTER_TYPES
from src.utils import error_codes
from src.utils.custom_app_exception import AppException

_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-.]+$")


def is_valid_email(email):
    return bool(_EMAIL_PATTERN.match((email or "").strip()))


def require_letter_type(letter_type):
    terms = LETTER_TYPES.get((letter_type or "").strip())
    if not terms:
        raise AppException(error_codes.LETTER_TYPE_REQUIRED, "Please select a letter type first.")
    return terms


def require_name_and_role(name, role):
    if not name or not role:
        raise AppException(error_codes.NAME_AND_ROLE_REQUIRED, "Candidate Name and Role are required.")


def require_letter_payload(details, content):
    if not details.get("name") or not details.get("letter_type") or not content:
        raise AppException(error_codes.LETTER_DETAILS_MISSING, "Letter details or content are missing.")


def is_template_backed(letter_type):
    return letter_type in TEMPLATE_BACKED_LETTER_TYPES


def require_valid_letter(validation):
    if not validation["valid"]:
        raise AppException(error_codes.LETTER_VALIDATION_FAILED, " ".join(validation["errors"]), {"validation": validation})
