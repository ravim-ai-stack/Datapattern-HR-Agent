"""Small text helpers shared by the letter services."""

import os

from src.constants.constants import CUSTOM_LETTER_TYPE, SIGNOFF_LINES
from src.settings.settings import LOGO_PATH


def _candidate(details):
    title = details.get("title", "").strip()
    name = details.get("name", "").strip()
    return f"{title} {name}".strip()


def _line_if(value, text):
    return text.format(value=value) if value else ""


def _location_text(details):
    location = details.get("location", "").strip()
    return f" at {location}" if location else ""


def _joining_text(details):
    return details.get("joining_date", "").strip() or "the agreed joining date"


def _end_date_text(details):
    return details.get("end_date", "").strip() or _joining_text(details)


def _salary_text(details):
    salary = details.get("salary", "").strip()
    return _line_if(salary, "The salary/stipend for this engagement is {value}.")


def _duration_text(details):
    duration = details.get("duration", "").strip()
    return _line_if(duration, "The expected duration for this engagement is {value}.")


def _certificate_pronoun(title):
    normalized = (title or "").strip().lower()
    if normalized == "mr.":
        return "his"
    if normalized in ("ms.", "mrs."):
        return "her"
    return "their"


def _uses_split_footer(details):
    return details.get("letter_type") in {"offer", "internship_offer", "appraisal"}


def _footer_left_text(details):
    letter_type = details.get("letter_type")
    if letter_type == "internship_offer":
        return "Internship Offer letter"
    if letter_type == "appraisal":
        return "Appraisal letter - DataPattern"
    return "Appointment letter - DataPattern"


def _paragraphs_from_content(content):
    return [part.strip() for part in (content or "").split("\n\n") if part.strip()]


def _is_custom_letter(details):
    return details.get("letter_type") == CUSTOM_LETTER_TYPE


def _signoff_lines():
    # The brand name is represented by the supplied logo in exported letters.
    return SIGNOFF_LINES[:-1] if os.path.exists(LOGO_PATH) else SIGNOFF_LINES
