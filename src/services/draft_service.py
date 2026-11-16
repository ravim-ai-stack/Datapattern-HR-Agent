"""Letter draft workflow: create a draft, refresh it after edits, and produce downloads."""

from src.constants.constants import DEFAULT_TITLE, MIME_DOCX, MIME_JPEG, MIME_PDF
from src.services.appraisal_service import parse_appraisal_details
from src.services.export_service import generate_letter_docx, generate_letter_jpeg, generate_letter_pdf
from src.services.letter_service import letter_content, validate_letter_details
from src.services.preview_service import build_letter_body_html, build_letter_html
from src.utils import error_codes
from src.utils.custom_app_exception import AppException
from src.utils.logger import get_logger
from src.utils.validators import (
    is_template_backed, require_letter_payload, require_letter_type, require_name_and_role, require_valid_letter,
)

logger = get_logger(__name__)


def _welcome_message(role, letter_name):
    return (
        f"We are pleased to share your {letter_name} for the position of {role} at DataPattern.\n"
        "Please review the attached letter and let us know if you have any questions."
    )


def _field(data, key):
    return (data.get(key) or "").strip()


def _filename(name, letter_name):
    return f"{name.replace(' ', '_')}_{letter_name.replace(' ', '_')}.docx"


def _validate_existing(details, content):
    """Template-backed letters are re-derived from the template; others use the edited text."""
    source = letter_content(details) if is_template_backed(details.get("letter_type")) else content
    validation = validate_letter_details(details, source)
    require_valid_letter(validation)
    return validation


def create_draft(data):
    terms = require_letter_type(data.get("letter_type"))
    name, role = _field(data, "name"), _field(data, "role")
    if data.get("letter_type") == "appraisal":
        if not name:
            raise AppException(error_codes.NAME_AND_ROLE_REQUIRED, "Candidate Name is required.")
    else:
        require_name_and_role(name, role)
    details = {
        "title": _field(data, "title") or DEFAULT_TITLE,
        "name": name,
        "role": role,
        "location": _field(data, "location"),
        "joining_date": _field(data, "joining_date"),
        "end_date": _field(data, "end_date"),
        "letter_type": _field(data, "letter_type"),
        "letter_name": terms["name"],
        "duration": _field(data, "duration"),
        "salary": _field(data, "salary"),
    }
    if details["letter_type"] == "appraisal":
        details.update(parse_appraisal_details(data))
    content = letter_content(details)
    validation = validate_letter_details(details, content)
    require_valid_letter(validation)
    logger.info("Draft created: %s for %s", terms["name"], name)
    return {
        "success": True,
        "filename": _filename(name, terms["name"]),
        "receiver_name": name,
        "welcome_message": _welcome_message(role, terms["name"]),
        "letter_content": content,
        "details": details,
        "validation": validation,
        "preview_html": build_letter_html(details, content),
        "body_html": build_letter_body_html(details, content),
    }


def update_draft(data):
    details, content, edits = _unpack_letter_request(data)
    _validate_existing(details, content)
    return {
        "success": True,
        "preview_html": build_letter_html(details, content, edits),
        "body_html": build_letter_body_html(details, content, edits),
        "filename": _filename(details["name"], details["letter_name"]),
    }


def build_download(data):
    """Return (file_bytes, filename, mimetype) for the requested format."""
    details, content, edits = _unpack_letter_request(data)
    _validate_existing(details, content)
    fmt = (data.get("format") or "word").lower()
    try:
        if fmt == "jpeg":
            jpeg, filename = generate_letter_jpeg(details)
            return jpeg, filename, MIME_JPEG
        docx, filename = generate_letter_docx(details, content, edits)
        if fmt == "pdf":
            return generate_letter_pdf(details, content, edits), filename.replace(".docx", ".pdf"), MIME_PDF
        return docx, filename, MIME_DOCX
    except AppException:
        raise
    except Exception as exc:
        logger.exception("Download generation failed")
        raise AppException(error_codes.DOWNLOAD_FAILED, f"Unable to create the download: {exc}")


def _unpack_letter_request(data):
    details = data.get("details") or {}
    content = (data.get("letter_content") or "").strip()
    edits = data.get("letter_blocks") or []
    require_letter_payload(details, content)
    return details, content, edits
