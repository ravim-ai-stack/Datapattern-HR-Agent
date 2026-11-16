"""Appraisal letter: validates the appraisal inputs and fills the letterpad
template (letter date, salutation, rating, revised CTC, effective date and the
Annexure A salary table). The header logo and footer come from the template."""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from src.constants.constants import APPRAISAL_FIELD_LABELS, APPRAISAL_ROWS
from src.repositories.template_repository import _template_path, load_template_document
from src.utils import error_codes
from src.utils.custom_app_exception import AppException

_CENTS = Decimal("0.01")
_AMOUNT_KEYS = [f"{key}_{column}" for key, _ in APPRAISAL_ROWS for column in ("month", "year")]


def _to_amount(value):
    try:
        amount = Decimal(str(value).replace(",", "").strip())
    except InvalidOperation:
        return None
    return amount if amount >= 0 else None


def _effective_date_text(value):
    """ISO date from the form -> the template's dd.mm.yyyy style."""
    value = (value or "").strip()
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return value


def parse_appraisal_details(data):
    """Pick the appraisal fields out of a request, or raise listing what's
    missing/invalid. Amounts (every Per Month / Per Annum cell of Annexure A)
    are stored as plain numeric strings, exactly as entered."""
    fields, problems = {}, []
    for key in ("rating", "effective_date", *_AMOUNT_KEYS):
        raw = (data.get(key) or "").strip() if isinstance(data.get(key), str) else str(data.get(key) or "").strip()
        if not raw:
            problems.append(APPRAISAL_FIELD_LABELS[key])
        elif key in _AMOUNT_KEYS:
            amount = _to_amount(raw)
            if amount is None:
                problems.append(f"{APPRAISAL_FIELD_LABELS[key]} (must be a non-negative number)")
            else:
                fields[key] = str(amount)
        elif key == "effective_date":
            fields[key] = _effective_date_text(raw)
        else:
            fields[key] = raw
    if problems:
        raise AppException(error_codes.APPRAISAL_DETAILS_REQUIRED, "Please fill in: " + ", ".join(problems) + ".")
    return fields


def _indian_number(amount):
    """1234567.8 -> '12,34,567.80' (lakh/crore grouping used in the template)."""
    whole, _, fraction = f"{amount.quantize(_CENTS):.2f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        whole = f"{head},{tail}"
    return f"{whole}.{fraction}"


def appraisal_figures(details):
    """Annexure A rows keyed by label -> (per month, per annum)."""
    return {
        label: (_to_amount(details.get(f"{key}_month")) or Decimal("0"), _to_amount(details.get(f"{key}_year")) or Decimal("0"))
        for key, label in APPRAISAL_ROWS
    }


def _letters(text):
    """Compare table labels ignoring case, spacing and stray characters
    (the template has "Employer <odd dash> PF Contribution")."""
    return re.sub(r"[^a-z]", "", text.lower())


def _set_runs(paragraph, text):
    """Put `text` in the first run (keeping its font) and blank the rest."""
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(text)
        return
    runs[0].text = text
    for run in runs[1:]:
        run.text = ""


def _fill_paragraphs(source, details, figures):
    name = details.get("name", "").strip()
    annual_ctc = _indian_number(figures["Total CTC"][1])
    for paragraph in source.paragraphs:
        text = paragraph.text.strip()
        if re.fullmatch(TEMPLATE_LETTER_DATE, text):
            _set_runs(paragraph, details.get("joining_date", "").strip() or text)
        elif text.startswith("Dear"):
            _set_runs(paragraph, f"Dear {name},")
        elif "your appraisal rating is" in text:
            runs = paragraph.runs
            # Fill by landmark run so the paragraph's mixed formatting survives.
            rating = next(i for i, r in enumerate(runs) if r.text.strip() == "3")
            money_start = next(i for i, r in enumerate(runs) if r.text.strip() == "Rs.")
            money_end = next(i for i, r in enumerate(runs) if r.text.strip() == "278.12")
            date_run = next(i for i, r in enumerate(runs) if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", r.text.strip()))
            runs[rating].text = details["rating"]
            runs[money_start].text = f"Rs.{annual_ctc}"
            for run in runs[money_start + 1:money_end + 1]:
                run.text = ""
            runs[date_run].text = details["effective_date"]
            # The template highlights its sample figures; the filled-in values shouldn't be.
            for run in runs:
                run.font.highlight_color = None


# "27 June 2024" -- the letter date baked into the template.
TEMPLATE_LETTER_DATE = r"\d{1,2}\s+[A-Za-z]+\s+\d{4}"


def _fill_annexure(source, figures):
    table = source.tables[0]
    for row in table.rows:
        label = row.cells[0].text.strip()
        key = next((k for k in figures if _letters(k) == _letters(label)), None)
        if key is None:
            continue
        monthly, annual = figures[key]
        for cell, value in zip(row.cells[1:], (monthly, annual)):
            _set_runs(cell.paragraphs[0], _indian_number(value))
            for extra in cell.paragraphs[1:]:
                _set_runs(extra, "")


def render_appraisal(details):
    """The appraisal template filled with this employee's details (docx Document)."""
    path = _template_path(details)
    if not path:
        return None
    source = load_template_document(path)
    figures = appraisal_figures(details)
    _fill_paragraphs(source, details, figures)
    _fill_annexure(source, figures)
    return source
