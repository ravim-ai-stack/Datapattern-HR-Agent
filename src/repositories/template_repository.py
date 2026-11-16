"""Data access for the .docx letter templates stored under src/static/letter_templates."""

import os

from docx import Document

from src.constants.constants import IT_ASSET_FORM_DATE_LABELS, TEMPLATE_FILENAMES
from src.settings.settings import TEMPLATE_DIR


def _template_path(details):
    letter_type = details.get("letter_type", "")
    path = os.path.join(TEMPLATE_DIR, TEMPLATE_FILENAMES.get(letter_type, f"{letter_type}.docx"))
    return path if os.path.exists(path) else ""


def _is_it_asset_form(details):
    return details.get("letter_type") in IT_ASSET_FORM_DATE_LABELS


def load_template_document(path):
    """Open a letter template (.docx) from disk."""
    return Document(path)
