"""Letter text: the filled template content, its block structure, and validation."""

import re

from src.constants.constants import COMPANY_NAME, TEMPLATE_DATE_PATTERN
from src.repositories.template_repository import _is_it_asset_form, _template_path, load_template_document
from src.services.document_service import (
    _apply_edited_blocks, _document_blocks, _document_paragraphs, _render_it_asset_form, _render_source_template,
)
from src.utils.letter_text import (
    _candidate, _certificate_pronoun, _duration_text, _end_date_text, _joining_text, _location_text, _salary_text,
)


def _content_paragraphs(details):
    letter_type = details.get("letter_type", "")
    candidate = _candidate(details)
    role = details.get("role", "").strip() or "the assigned role"
    joining_date = _joining_text(details)
    location = _location_text(details)
    salary = _salary_text(details)
    duration = _duration_text(details)

    if letter_type == "internship_offer":
        return [
            f"We are pleased to offer you an internship with {COMPANY_NAME} as {role}.",
            f"Your internship will commence on {joining_date}{location}.",
            duration,
            salary,
            "During the internship, you are expected to follow company policies, maintain confidentiality, and complete the responsibilities assigned to you by your reporting manager.",
            "Please confirm your acceptance of this internship offer within 5 days so we can complete the joining formalities.",
            f"We look forward to welcoming you to {COMPANY_NAME}.",
        ]

    if letter_type == "internship_certificate":
        return [
            f"This is to certify that {candidate} has completed Internship in our organization as a {role} from {joining_date} to {_end_date_text(details)}.",
            f"We appreciate {_certificate_pronoun(details.get('title'))} work and contributions.",
        ]

    if letter_type == "completion":
        return [
            "To Whom It May Concern,",
            f"This is to certify that {candidate} has successfully completed the assigned {role} engagement with {COMPANY_NAME}.",
            f"The engagement commenced on {joining_date}{location}.",
            duration,
            "During this period, the work assigned was completed responsibly and with professional conduct.",
            f"We appreciate the contribution made by {candidate} and wish them success in future assignments.",
        ]

    if letter_type == "it_asset_return_clearance":
        return [
            "To Whom It May Concern,",
            f"This letter confirms that {candidate}, who was engaged as {role} with {COMPANY_NAME}, has returned all company-issued IT assets and equipment.",
            f"The association commenced on {joining_date}{location}.",
            "The returned assets have been verified and accepted in good working condition, and no dues remain against the equipment issued.",
            f"{candidate} is hereby cleared of all IT asset-related responsibilities and formalities with {COMPANY_NAME}.",
        ]

    if letter_type == "it_asset_issuance_onboarding":
        return [
            "To Whom It May Concern,",
            f"This letter confirms that {candidate}, joining {COMPANY_NAME} as {role}, has been issued the company IT assets and resources required to perform the assigned role.",
            f"The assets were issued on {joining_date}{location}.",
            "The recipient is responsible for maintaining the assets in good condition and must return them to the company whenever requested or at the end of the engagement.",
            "Any loss, damage, or misuse of company assets must be reported to the HR or administration team immediately.",
        ]

    if letter_type == "relieving":
        return [
            "To Whom It May Concern,",
            f"This is to confirm that {candidate} was associated with {COMPANY_NAME} as {role}.",
            f"The association commenced on {joining_date}{location}.",
            "The employee has been relieved from the assigned duties as per the company's internal process.",
            f"We thank {candidate} for the contribution made during the association with {COMPANY_NAME} and wish them all the best for future endeavors.",
        ]

    if letter_type == "experience":
        return [
            "To Whom It May Concern,",
            f"This is to certify that {candidate} has worked with {COMPANY_NAME} as {role}.",
            f"The employment commenced on {joining_date}{location}.",
            duration,
            "During the association, the employee handled assigned responsibilities with professionalism and discipline.",
            f"We wish {candidate} continued success in their professional career.",
        ]

    return [
        f"We are pleased to offer you the position of {role} at {COMPANY_NAME}.",
        f"Your joining date is {joining_date}{location}.",
        salary,
        "This offer is subject to completion of joining formalities and acceptance of the company's policies.",
        "Please confirm your acceptance of this offer within 7 days from the date of receiving this letter.",
        f"We look forward to having you as part of {COMPANY_NAME}.",
    ]


def _it_asset_form_content(details):
    path = _template_path(details)
    if not path:
        return ""
    try:
        source = _render_it_asset_form(details)
        return "\n\n".join(p.text.strip() for p in _document_paragraphs(source) if p.text.strip())
    except Exception:
        return ""


def _template_content(details):
    path = _template_path(details)
    if not path:
        return ""
    if details.get("letter_type") == "appraisal":
        try:
            return "\n\n".join(p.text.strip() for p in _document_paragraphs(_render_source_template(details)) if p.text.strip())
        except Exception:
            return ""
    try:
        source = load_template_document(path)
        text = "\n\n".join(p.text.strip() for p in _document_paragraphs(source) if p.text.strip())
        name = details.get("name", "").strip()
        role = details.get("role", "").strip()
        joining = _joining_text(details)
        end_date = _end_date_text(details)
        replacements = {
            "Dear[Candidate]": f"Dear {name}", "[Candidate]": name, "[Date]": joining,
            "[Employee Name]": name, "[Candidate Name]": name,
            "[Designation]": role, "[Designation(s)]": role,
            "[Position/Role]": role, "[Candidate Address]": details.get("location", "").strip(),
            "[Start Date]": joining, "[End Date]": end_date,
            "[Last Working Day]": joining, "[Relieving Date]": joining,
            "[Relieving Letter Date]": joining, "[Acceptance Deadline]": joining,
            "[Authorized Name]": "Indhirajith K", "[Authorized Signatory Name]": "Indhirajith K", "[Signatory Designation]": "Head Operations Coimbatore",
            "[Salary]": details.get("salary", "").strip(), "[Monthly Salary]": details.get("salary", "").strip(),
            "Saranya": name, "Deepak kumar": name, "Krishna Priya": name,
            "Harini Ravichandran": name, "Data Engineer": role,
            "Recruitment executive and Learning and development lead": role,
            "Recruitment executive": role,
        }
        # Normalize any literal (non-bracket) dates baked into the template to
        # the joining date, before filling in [Start Date]/[End Date]-style
        # placeholders below -- otherwise this would also catch (and clobber)
        # a distinct end date that was just substituted in.
        if joining:
            text = re.sub(TEMPLATE_DATE_PATTERN, joining, text)
        for old, new in replacements.items():
            if new or old.startswith("["):
                text = text.replace(old, new)
        return text
    except Exception:
        return ""


def _template_blocks(details, edits=None):
    """Same candidate-filled template document as `_template_content`/
    `_it_asset_form_content`, but kept as ('p'|'table', ...) blocks instead of
    flattened text, so tables can be rendered as real HTML tables. If `edits`
    (the editable panel's saved content) is given, it's patched onto the
    document first so the preview/editor reflects the user's own edits."""
    path = _template_path(details)
    if not path:
        return []
    try:
        source = _render_it_asset_form(details) if _is_it_asset_form(details) else _render_source_template(details)
        if edits:
            _apply_edited_blocks(source, edits)
        return list(_document_blocks(source))
    except Exception:
        return []


def letter_content(details):
    if _is_it_asset_form(details):
        form_content = _it_asset_form_content(details)
        if form_content:
            return form_content
    template = _template_content(details)
    if template:
        return template
    paragraphs = [paragraph for paragraph in _content_paragraphs(details) if paragraph]
    return "\n\n".join(paragraphs)


def validate_letter_details(details, content=None):
    """Verify template placeholders were resolved before preview/download."""
    text = content or letter_content(details)
    unresolved = sorted(set(re.findall(r"\[[^\]]+\]", text)))
    errors = []
    if unresolved:
        errors.append("Unresolved template fields: " + ", ".join(unresolved))
    name = (details.get("name") or "").strip()
    role = (details.get("role") or "").strip()
    if name and name.lower() not in text.lower():
        errors.append("Candidate name was not inserted into the letter.")
    # The appraisal letter addresses the employee by name only; no role line.
    if role and details.get("letter_type") != "appraisal" and role.lower() not in text.lower():
        errors.append("Role/designation was not inserted into the letter.")
    return {"valid": not errors, "errors": errors}
