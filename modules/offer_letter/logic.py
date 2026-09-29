"""Letter content, preview, and download generation helpers."""

import base64
import copy
import os
import re
import shutil
import subprocess
import tempfile
from html import escape
from io import BytesIO
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from docx.table import Table
from docx.text.paragraph import Paragraph


COMPANY_NAME = "DataPattern"
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "img", "datapattern-logo.png")
SIGNATURE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "img", "indhirajith-signature.jpeg")
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "letter_templates")
CERTIFICATE_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "img", "DataPattern Internship Certificate_.png")
CERTIFICATE_NAVY = (10, 34, 74)
CERTIFICATE_BLACK = (20, 20, 20)
CERTIFICATE_TEXT_LEFT = 140
CERTIFICATE_TEXT_RIGHT = 1860
# Bounding boxes (matched to the reference certificate) that get whited-out and
# redrawn with the candidate's own details; everything outside them (title,
# border, seal, DataPattern logo, and Indhirajith's signature block) stays as-is.
CERTIFICATE_NAME_BAND = (CERTIFICATE_TEXT_LEFT, 565, CERTIFICATE_TEXT_RIGHT, 692)
CERTIFICATE_SENTENCE_BAND = (CERTIFICATE_TEXT_LEFT, 728, CERTIFICATE_TEXT_RIGHT, 826)
CERTIFICATE_APPRECIATION_BAND = (CERTIFICATE_TEXT_LEFT, 855, CERTIFICATE_TEXT_RIGHT, 895)
SIGNOFF_LINES = [
    "Regards,",
    "Mirthula R,",
    "HR Executive,",
    "9042977445",
    "www.datapattern.ai",
    "",
    "DataPattern",
]
PAGE_WIDTH = 1240
PAGE_HEIGHT = 1754
MARGIN_X = 90
MARGIN_Y = 90

# Matches the date formats baked into the source templates so they can be
# swapped for the candidate's actual joining date: "2 September 2026",
# "Sep 2, 2026", and the numeric "01-08-2026" / "01/08/2026" style.
TEMPLATE_DATE_PATTERN = r"\b(?:\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]{3}\s+\d{1,2},\s+\d{4}|\d{1,2}[-/]\d{1,2}[-/]\d{4})\b"


def _load_font(size, bold=False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibribd.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


CERTIFICATE_FONT_CANDIDATES = {
    "bold": ["C:/Windows/Fonts/timesbd.ttf", "C:/Windows/Fonts/georgiab.ttf", "C:/Windows/Fonts/arialbd.ttf"],
    "italic": ["C:/Windows/Fonts/timesi.ttf", "C:/Windows/Fonts/ariali.ttf", "C:/Windows/Fonts/arial.ttf"],
    "regular": ["C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/georgia.ttf", "C:/Windows/Fonts/arial.ttf"],
}


def _load_certificate_font(size, style="regular"):
    for path in CERTIFICATE_FONT_CANDIDATES.get(style, CERTIFICATE_FONT_CANDIDATES["regular"]):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def _fit_certificate_font(draw, text, style, start_size, max_width, min_size=18):
    size = start_size
    while size > min_size:
        font = _load_certificate_font(size, style)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 2
    return _load_certificate_font(min_size, style)


def _render_certificate_image(details):
    """Draw the candidate's name, role, and dates onto the reference
    certificate design, replacing only the sample text baked into that file."""
    image = Image.open(CERTIFICATE_TEMPLATE_PATH).convert("RGB")
    draw = ImageDraw.Draw(image)
    width = image.size[0]
    center_x = width // 2
    max_text_width = CERTIFICATE_TEXT_RIGHT - CERTIFICATE_TEXT_LEFT

    candidate = _candidate(details)
    display_name = details.get("name", "").strip()
    role = details.get("role", "").strip() or "Intern"
    from_date = _joining_text(details)
    end_date = _end_date_text(details)
    pronoun = _certificate_pronoun(details.get("title"))

    name_left, name_top, name_right, name_bottom = CERTIFICATE_NAME_BAND
    draw.rectangle(CERTIFICATE_NAME_BAND, fill="white")
    name_font = _fit_certificate_font(draw, display_name.upper(), "bold", 96, max_text_width)
    name_y = (name_top + name_bottom) // 2 - 8
    draw.text((center_x, name_y), display_name.upper(), font=name_font, fill=CERTIFICATE_NAVY, anchor="mm")

    sentence_left, sentence_top, sentence_right, sentence_bottom = CERTIFICATE_SENTENCE_BAND
    draw.rectangle(CERTIFICATE_SENTENCE_BAND, fill="white")
    line1 = f"This is to certify that {candidate} has completed Internship in our organization"
    line2 = f"as a {role} from {from_date} to {end_date}"
    sentence_size = 34
    for line in (line1, line2):
        font = _load_certificate_font(sentence_size, "italic")
        while sentence_size > 18 and draw.textlength(line, font=font) > max_text_width:
            sentence_size -= 2
            font = _load_certificate_font(sentence_size, "italic")
    sentence_font = _load_certificate_font(sentence_size, "italic")
    draw.text((center_x, sentence_top + 30), line1, font=sentence_font, fill=CERTIFICATE_BLACK, anchor="mm")
    draw.text((center_x, sentence_top + 75), line2, font=sentence_font, fill=CERTIFICATE_BLACK, anchor="mm")

    appreciation_top = CERTIFICATE_APPRECIATION_BAND[1]
    draw.rectangle(CERTIFICATE_APPRECIATION_BAND, fill="white")
    appreciation_text = f"We appreciate {pronoun} work and contributions."
    appreciation_font = _fit_certificate_font(draw, appreciation_text, "regular", 34, max_text_width)
    draw.text((center_x, appreciation_top + 18), appreciation_text, font=appreciation_font, fill=CERTIFICATE_BLACK, anchor="mm")

    return image


def _certificate_image_bytes(details, fmt="PNG"):
    buffer = BytesIO()
    _render_certificate_image(details).save(buffer, format=fmt)
    return buffer.getvalue()


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


def _template_path(details):
    path = os.path.join(TEMPLATE_DIR, f"{details.get('letter_type', '')}.docx")
    return path if os.path.exists(path) else ""


# The two IT asset forms are fillable checkbox forms (all fields live in
# table cells), unlike the other templates which are prose letters with
# `[Bracket]` placeholders in paragraph text. They need their own field-fill
# logic instead of the generic bracket-replacement path.
IT_ASSET_FORM_DATE_LABELS = {
    "it_asset_issuance_onboarding": "Joining Date:",
    "it_asset_return_clearance": "Return Date:",
}


def _is_it_asset_form(details):
    return details.get("letter_type") in IT_ASSET_FORM_DATE_LABELS


COMPANY_ADDRESS = "Address: No. G-1, Door/No: 4/608, V.O.C Street, O.M.R Road, Kottivakkam, Chennai-600041."


def _uses_split_footer(details):
    return details.get("letter_type") in {"offer", "internship_offer"}


def _footer_left_text(details):
    return "Internship Offer letter" if details.get("letter_type") == "internship_offer" else "Appointment letter - DataPattern"


def _strip_table_borders(table):
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "nil")
        borders.append(element)
    tblPr.append(borders)


def _style_footer_run(run):
    run.bold = True
    run.italic = True
    run.font.size = Pt(8)
    return run


def _add_footer_content(footer, section, details):
    """Offer/internship letters get a left/right split footer; other letter types get a centered company address."""
    # We own the whole footer region: drop any pre-existing blank paragraphs
    # or tables from the source template so they don't push our content down
    # or leave stray empty space.
    for table in footer.tables:
        table._tbl.getparent().remove(table._tbl)
    for paragraph in footer.paragraphs[1:]:
        paragraph._p.getparent().remove(paragraph._p)
    for run in footer.paragraphs[0].runs:
        run.text = ""
    if _uses_split_footer(details):
        # Tab-stop alignment is unreliable here: the built-in Footer style
        # carries its own center/right tab stops and LibreOffice merges
        # rather than overrides them, so a single '\t' can land on the wrong
        # stop. A borderless 2-column table gives a real left/right split.
        usable_width = section.page_width - section.left_margin - section.right_margin
        table = footer.add_table(rows=1, cols=2, width=usable_width)
        table.autofit = True
        _strip_table_borders(table)
        left_cell, right_cell = table.rows[0].cells
        left_cell.width = usable_width // 2
        right_cell.width = usable_width // 2
        left_paragraph = left_cell.paragraphs[0]
        left_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        _style_footer_run(left_paragraph.add_run(_footer_left_text(details)))
        right_paragraph = right_cell.paragraphs[0]
        right_paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        _style_footer_run(right_paragraph.add_run("Private & confidential"))
        footer.add_paragraph()
    else:
        paragraph = footer.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _style_footer_run(paragraph.add_run(COMPANY_ADDRESS))


def _document_paragraphs(document):
    """Yield paragraphs from the body, tables, headers, and footers."""
    def walk(container):
        for paragraph in getattr(container, "paragraphs", []):
            yield paragraph
        for table in getattr(container, "tables", []):
            for row in table.rows:
                for cell in row.cells:
                    yield from walk(cell)
    yield from walk(document)
    for section in document.sections:
        yield from walk(section.header)
        yield from walk(section.footer)


def _document_blocks(document):
    """Yield ('p', text) for body paragraphs and ('table', rows) for body
    tables, in document order. Keeping tables intact (instead of flattening
    every cell into its own paragraph, as `_document_paragraphs` does) is what
    lets the salary annexure and IT asset checklists render as real tables
    instead of a scrambled list of fragments."""
    for block in document.iter_inner_content():
        if isinstance(block, Table):
            rows = [[cell.text.strip() for cell in row.cells] for row in block.rows]
            if any(any(cell for cell in row) for row in rows):
                yield ("table", rows)
        else:
            text = block.text.strip()
            if text:
                yield ("p", text)


def _set_paragraph_text_preserving_style(paragraph, new_text):
    """Overwrite a paragraph's visible text with `new_text` (which may
    contain '\n' for manual line breaks), writing into its first non-picture
    run instead of replacing the paragraph outright so its original font,
    bold, size, etc. carry over onto the edited text."""
    text_runs = [run for run in paragraph.runs if run._element.find(qn("w:drawing")) is None]
    lines = new_text.split("\n")
    if text_runs:
        target = text_runs[0]
        target.text = ""
        target.add_text(lines[0])
        for line in lines[1:]:
            target.add_break()
            target.add_text(line)
        for run in text_runs[1:]:
            run.text = ""
    else:
        run = paragraph.add_run()
        run.add_text(lines[0])
        for line in lines[1:]:
            run.add_break()
            run.add_text(line)


def _patch_paragraphs(paragraphs, edited_texts):
    """`paragraphs` are the rendered template's own (non-blank) Paragraph
    objects in order; `edited_texts` are the corresponding strings from the
    editable panel. Only paragraphs whose text actually changed are
    rewritten, so untouched formatting (e.g. a bold date) survives; extra
    edited entries are appended as new paragraphs, and removed ones are
    cleared rather than deleted (some carry page-layout metadata)."""
    for paragraph, new_text in zip(paragraphs, edited_texts):
        if new_text.strip() and new_text.strip() != paragraph.text.strip():
            _set_paragraph_text_preserving_style(paragraph, new_text)
    if len(edited_texts) > len(paragraphs):
        anchor = paragraphs[-1] if paragraphs else None
        for extra_text in edited_texts[len(paragraphs):]:
            if anchor is None:
                break
            anchor = _insert_paragraph_after(anchor)
            _set_paragraph_text_preserving_style(anchor, extra_text)
    elif len(paragraphs) > len(edited_texts):
        for paragraph in paragraphs[len(edited_texts):]:
            for run in paragraph.runs:
                if run._element.find(qn("w:drawing")) is None:
                    run.text = ""


def _patch_tables(tables, edited_tables):
    for table, edited_rows in zip(tables, edited_tables):
        for row, edited_row in zip(table.rows, edited_rows or []):
            for cell, new_text in zip(row.cells, edited_row):
                if not cell.paragraphs or not isinstance(new_text, str):
                    continue
                if new_text.strip() and new_text.strip() != cell.text.strip():
                    _set_paragraph_text_preserving_style(cell.paragraphs[0], new_text)
                    for extra_paragraph in cell.paragraphs[1:]:
                        for run in extra_paragraph.runs:
                            run.text = ""


def _apply_edited_blocks(document, edits):
    """Patch the rendered template `document` in place so it reflects the
    user's edits from the editable letter-content panel (`edits`, produced by
    the frontend's block extraction) -- while leaving anything the user
    didn't touch exactly as the template rendered it."""
    if not edits:
        return document
    originals = list(document.iter_inner_content())
    orig_paragraphs = [block for block in originals if not isinstance(block, Table) and block.text.strip()]
    orig_tables = [block for block in originals if isinstance(block, Table)]
    edited_paragraphs = [entry.get("text", "") for entry in edits if entry.get("type") == "p"]
    edited_tables = [entry.get("rows", []) for entry in edits if entry.get("type") == "table"]
    _patch_paragraphs(orig_paragraphs, edited_paragraphs)
    _patch_tables(orig_tables, edited_tables)
    return document


def _fill_form_field(document, label, value):
    """Find a `label` cell in any table and write `value` into the cell right
    after it, replacing a blank cell or a "____ / ____ / 20___" style
    placeholder. Leaves the cell untouched if it already holds real text."""
    if not value:
        return False
    for table in document.tables:
        for row in table.rows:
            cells = row.cells
            for index, cell in enumerate(cells):
                if cell.text.strip() != label or index + 1 >= len(cells):
                    continue
                target = cells[index + 1]
                current = target.text.strip()
                if current and "_" not in current:
                    continue
                for paragraph in target.paragraphs:
                    for run in paragraph.runs:
                        run.text = ""
                first_paragraph = target.paragraphs[0] if target.paragraphs else target.add_paragraph()
                if first_paragraph.runs:
                    first_paragraph.runs[0].text = value
                else:
                    first_paragraph.add_run(value)
                return True
    return False


def _render_it_asset_form(details):
    """Fill the candidate's name, role, and date directly into the IT asset
    form's table cells, on top of the DataPattern header/footer used by the
    other letter templates."""
    path = _template_path(details)
    source = Document(path)
    for section in source.sections:
        header = section.header
        header.is_linked_to_previous = False
        hp = header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        hp.paragraph_format.left_indent = Inches(0)
        hp.paragraph_format.right_indent = Inches(0)
        hp.paragraph_format.first_line_indent = Inches(0)
        hp.paragraph_format.space_after = Pt(4)
        if os.path.exists(LOGO_PATH):
            hp.add_run().add_picture(LOGO_PATH, width=Inches(2.4))
        footer = section.footer
        footer.is_linked_to_previous = False
        _add_footer_content(footer, section, details)
    _fill_form_field(source, "Employee Name:", _candidate(details))
    _fill_form_field(source, "Department / Team:", details.get("role", "").strip())
    # The details page doesn't collect a date for these forms -- leave the
    # printed "____ / ____ / 20___" placeholder for manual sign-off instead of
    # filling in the "no date given" fallback text.
    _fill_form_field(source, IT_ASSET_FORM_DATE_LABELS[details.get("letter_type")], details.get("joining_date", "").strip())
    return source


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
    try:
        source = Document(path)
        text = "\n\n".join(p.text.strip() for p in _document_paragraphs(source) if p.text.strip())
        name = details.get("name", "").strip()
        role = details.get("role", "").strip()
        joining = _joining_text(details)
        end_date = _end_date_text(details)
        replacements = {
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
    if role and role.lower() not in text.lower():
        errors.append("Role/designation was not inserted into the letter.")
    return {"valid": not errors, "errors": errors}


def _paragraphs_from_content(content):
    return [part.strip() for part in (content or "").split("\n\n") if part.strip()]


def _signoff_lines():
    # The brand name is represented by the supplied logo in exported letters.
    return SIGNOFF_LINES[:-1] if os.path.exists(LOGO_PATH) else SIGNOFF_LINES


def _letter_blocks(details, content=None, edits=None):
    """('p'|'table', value) blocks for the letter body. Template-backed
    letters (offer, IT asset forms, etc.) read straight from the rendered
    template document -- tables and all -- with any panel `edits` patched on
    top. Everything else falls back to the plain paragraph text."""
    if _template_path(details):
        return _template_blocks(details, edits)
    return [("p", paragraph) for paragraph in _paragraphs_from_content(content or letter_content(details))]


def _body_html_from_blocks(details, blocks):
    body = []
    for kind, value in blocks:
        if kind == "table":
            rows_html = "".join(
                "<tr>" + "".join(f"<td>{escape(cell).replace(chr(10), '<br>')}</td>" for cell in row) + "</tr>"
                for row in value
            )
            body.append(f'<table class="letter-table">{rows_html}</table>')
            continue
        paragraph = value
        safe_paragraph = escape(paragraph).replace("\n", "<br>")
        if _template_path(details) and "Indhirajith" in paragraph:
            body.append('<img class="letter-signature" src="/static/img/indhirajith-signature.jpeg" alt="Indhirajith signature">')
        if "\n" not in paragraph and paragraph.rstrip().endswith(":") and len(paragraph) < 80:
            body.append(f"<h2>{safe_paragraph}</h2>")
        else:
            body.append(f"<p>{safe_paragraph}</p>")
    return "".join(body)


def build_letter_body_html(details, content=None, edits=None):
    """Just the letter's own content (paragraphs/tables) -- no header logo,
    title, signoff, or footer -- for the editable letter-content view."""
    return _body_html_from_blocks(details, _letter_blocks(details, content, edits))


def build_letter_html(details, content=None, edits=None):
    if details.get("letter_type") == "internship_certificate":
        encoded = base64.b64encode(_certificate_image_bytes(details)).decode("ascii")
        return f'<article class="certificate-preview"><img class="certificate-image" src="data:image/png;base64,{encoded}" alt="Internship Certificate"></article>'
    body_html = _body_html_from_blocks(details, _letter_blocks(details, content, edits))
    is_template = bool(_template_path(details))
    heading = "" if is_template else escape(details.get("letter_name", "Letter"))
    signoff = "" if is_template else "".join(f"<p>{escape(line)}</p>" if line else "<br>" for line in _signoff_lines())
    logo = '<img src="/static/img/datapattern-logo.png" alt="DataPattern">'
    title_html = f"<h1>{heading}</h1>" if heading else ""
    signoff_logo = '<img src="/static/img/datapattern-logo.png" alt="DataPattern">'
    signature = ""
    if _uses_split_footer(details):
        footer_left = escape(_footer_left_text(details))
        footer_html = f'<span class="letter-footer-left">{footer_left}</span><span class="letter-footer-right">Private &amp; confidential</span>'
        footer_style = "display:flex;justify-content:space-between;"
    else:
        footer_html = escape(COMPANY_ADDRESS)
        footer_style = "text-align:center;"
    return f'<article><div class="letter-header">{logo}</div>{title_html}{body_html}<div class="letter-signoff">{signoff}{signature}{signoff_logo}</div><div class="letter-footer" style="{footer_style}">{footer_html}</div></article>'


def _insert_paragraph_after(paragraph):
    """Clone paragraph's formatting (font/indent/justify) as a new empty
    paragraph placed right after it, dropping any fixed ("exact") line-height
    so text and pictures placed in it aren't clipped/overlapped."""
    new_p = copy.deepcopy(paragraph._p)
    for run_element in new_p.findall(qn("w:r")):
        new_p.remove(run_element)
    p_pr = new_p.find(qn("w:pPr"))
    if p_pr is not None:
        spacing = p_pr.find(qn("w:spacing"))
        if spacing is not None:
            p_pr.remove(spacing)
    paragraph._p.addnext(new_p)
    return Paragraph(new_p, paragraph._parent)


def _render_source_template(details):
    path = _template_path(details)
    if not path:
        return None
    source = Document(path)
    for section in source.sections:
        for paragraph in section.header.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.left_indent = Inches(0)
            paragraph.paragraph_format.right_indent = Inches(0)
            paragraph.paragraph_format.first_line_indent = Inches(0)
    if details.get("letter_type") == "internship_offer":
        for section in source.sections:
            # Exact page geometry from the supplied internship reference.
            section.top_margin = 895985
            section.bottom_margin = 567055
            section.left_margin = 814070
            section.right_margin = 356870
            section.page_width = Inches(8.27)
            section.page_height = Inches(11.69)
            header = section.header
            hp = header.paragraphs[0]
            hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            hp.paragraph_format.left_indent = Inches(0)
            hp.paragraph_format.right_indent = Inches(0)
            hp.paragraph_format.first_line_indent = Inches(0)
            hp.paragraph_format.space_after = Pt(4)
            if os.path.exists(LOGO_PATH):
                hp.add_run().add_picture(LOGO_PATH, width=Inches(2.2))
    for section in source.sections:
        _add_footer_content(section.footer, section, details)
    name = details.get("name", "").strip()
    role = details.get("role", "").strip()
    joining = _joining_text(details)
    end_date = _end_date_text(details)
    replacements = {
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
    # Replace fields in the document body only. Header/footer runs may contain
    # embedded logos; rewriting those runs would remove the drawings.
    for paragraph in source.paragraphs:
        value = paragraph.text
        if value and "[Authorized" in value and details.get("letter_type") in {"relieving", "experience"}:
            # Signature block for relieving/experience letters: just the
            # signature image, name, and designation. No HR contact details
            # or company logo at the bottom (only the header carries those).
            for run in paragraph.runs:
                run.text = ""
            p_pr = paragraph._p.find(qn("w:pPr"))
            if p_pr is not None:
                spacing = p_pr.find(qn("w:spacing"))
                if spacing is not None:
                    p_pr.remove(spacing)
            if os.path.exists(SIGNATURE_PATH):
                paragraph.add_run().add_picture(SIGNATURE_PATH, width=Inches(1.8))
            anchor = paragraph
            for line in ("Indhirajith K", "Head Operations Coimbatore"):
                anchor = _insert_paragraph_after(anchor)
                anchor.add_run(line)
            continue
        if value.strip() == "[Signatory Designation]" and details.get("letter_type") in {"relieving", "experience"}:
            # Already folded into the signature block above; drop the duplicate paragraph.
            paragraph._p.getparent().remove(paragraph._p)
            continue
        if details.get("letter_type") == "internship_offer" and value.strip() == "[Candidate Address]":
            for run in paragraph.runs:
                run.text = ""
            continue
        if details.get("letter_type") == "internship_offer" and "private & confidential" in value.lower():
            # The reference template bakes this line into the body; the footer
            # (added below) already carries the left/right "Internship Offer
            # letter" / "Private & confidential" line, so drop the duplicate.
            for run in paragraph.runs:
                run.text = ""
            continue
        # Most fields are contained in one run in the supplied templates.
        # Editing run text (instead of assigning paragraph.text) preserves all
        # original font, bold, underline, color, and character spacing.
        original_text = paragraph.text
        original_run_spans = []
        pos = 0
        for run in paragraph.runs:
            run_len = len(run.text or "")
            original_run_spans.append((pos, pos + run_len, bool(run.bold)))
            pos += run_len
        for run in paragraph.runs:
            if run._element.find(qn("w:drawing")) is not None:
                # run.text = ... wipes any embedded picture; leave image runs alone.
                continue
            updated = run.text or ""
            for old, new in replacements.items():
                if new or old.startswith("["):
                    updated = updated.replace(old, new)
            run.text = updated
        # If a field was split across multiple runs (common for dates), apply
        # the replacement to the combined paragraph while keeping the
        # paragraph's original style and layout. Dates are substituted here
        # only, against the pre-mutation text -- doing it per-run above would
        # corrupt any date split mid-token across two runs. It also runs
        # before the [Start Date]/[End Date]-style bracket replacements so it
        # only normalizes literal dates baked into the template, rather than
        # clobbering a just-substituted, distinct end date back to the
        # joining date.
        combined = "".join(run.text or "" for run in paragraph.runs)
        target = original_text
        date_match = re.search(TEMPLATE_DATE_PATTERN, original_text) if joining else None
        if date_match:
            target = re.sub(TEMPLATE_DATE_PATTERN, joining, target)
        for old, new in replacements.items():
            if new or old.startswith("["):
                target = target.replace(old, new)
        if target != combined and paragraph.runs:
            # If the literal date being replaced was itself bold in the
            # template (e.g. the "reporting for duty on <date>"
            # acknowledgement line), keep the new joining date bold too
            # instead of collapsing it into the (non-bold) first run.
            date_was_bold = date_match is not None and any(
                bold and start < date_match.end() and end > date_match.start()
                for start, end, bold in original_run_spans
            )
            if date_match and date_was_bold:
                prefix = original_text[:date_match.start()]
                suffix = original_text[date_match.end():]
                for old, new in replacements.items():
                    if new or old.startswith("["):
                        prefix = prefix.replace(old, new)
                        suffix = suffix.replace(old, new)
                paragraph.runs[0].text = prefix
                for run in paragraph.runs[1:]:
                    run.text = ""
                date_run = paragraph.add_run(joining)
                date_run.bold = True
                if suffix:
                    paragraph.add_run(suffix)
            else:
                paragraph.runs[0].text = target
                for run in paragraph.runs[1:]:
                    run.text = ""
    return source


def _generate_certificate_docx(details):
    image = _render_certificate_image(details)
    image_buffer = BytesIO()
    image.save(image_buffer, format="PNG")
    image_buffer.seek(0)
    image_width, image_height = image.size

    document = Document()
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width = Inches(11.69)
    section.page_height = Inches(8.27)
    section.top_margin = section.bottom_margin = section.left_margin = section.right_margin = Inches(0)

    picture_width = Inches(11.69)
    picture_height = picture_width * image_height / image_width
    document.add_picture(image_buffer, width=picture_width, height=picture_height)
    picture_paragraph = document.paragraphs[-1]
    picture_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    picture_paragraph.paragraph_format.space_before = Pt(0)
    picture_paragraph.paragraph_format.space_after = Pt(0)
    picture_paragraph.paragraph_format.line_spacing = 1

    buffer = BytesIO()
    document.save(buffer)
    filename = f"{details.get('name', 'Candidate').replace(' ', '_')}_Internship_Certificate.docx"
    return buffer.getvalue(), filename


def generate_letter_jpeg(details):
    """JPEG export, offered only for the internship completion certificate
    since it's a fixed-design image rather than a prose letter."""
    if details.get("letter_type") != "internship_certificate":
        raise ValueError("JPEG download is only available for the internship completion certificate.")
    buffer = BytesIO()
    _render_certificate_image(details).save(buffer, format="JPEG", quality=95)
    filename = f"{details.get('name', 'Candidate').replace(' ', '_')}_Internship_Certificate.jpg"
    return buffer.getvalue(), filename


def generate_letter_docx(details, content=None, edits=None):
    if details.get("letter_type") == "internship_certificate":
        return _generate_certificate_docx(details)
    if _is_it_asset_form(details) and _template_path(details):
        source = _render_it_asset_form(details)
        if edits:
            _apply_edited_blocks(source, edits)
        buffer = BytesIO()
        source.save(buffer)
        filename = f"{details.get('name', 'Candidate').replace(' ', '_')}_{details.get('letter_name', 'Letter').replace(' ', '_')}.docx"
        return buffer.getvalue(), filename
    if _template_path(details):
        source = _render_source_template(details)
        if edits:
            _apply_edited_blocks(source, edits)
        buffer = BytesIO()
        source.save(buffer)
        filename = f"{details.get('name', 'Candidate').replace(' ', '_')}_{details.get('letter_name', 'Letter').replace(' ', '_')}.docx"
        return buffer.getvalue(), filename
    document = Document()
    sections = document.sections
    for section in sections:
        # Match the supplied reference document's compact A4 layout.
        section.top_margin = Inches(0.98)
        section.bottom_margin = Inches(0.62)
        section.left_margin = Inches(0.89)
        section.right_margin = Inches(0.39)
        section.page_width = Inches(8.27)
        section.page_height = Inches(11.69)
        if os.path.exists(LOGO_PATH):
            header = section.header
            header.is_linked_to_previous = False
            hp = header.paragraphs[0]
            hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            hp.paragraph_format.left_indent = Inches(0)
            hp.paragraph_format.right_indent = Inches(0)
            hp.paragraph_format.first_line_indent = Inches(0)
            hp.paragraph_format.space_after = Pt(4)
            hp.add_run().add_picture(LOGO_PATH, width=Inches(3.6))
        footer = section.footer
        footer.is_linked_to_previous = False
        _add_footer_content(footer, section, details)

    heading = document.add_heading(details.get("letter_name", "Letter").upper(), level=2)
    heading.alignment = WD_ALIGN_PARAGRAPH.LEFT
    heading.paragraph_format.space_after = Pt(16)

    for paragraph_text in _paragraphs_from_content(content or letter_content(details)):
        is_section = "\n" not in paragraph_text and paragraph_text.rstrip().endswith(":") and len(paragraph_text) < 80
        paragraph = document.add_paragraph(style="Heading 3" if is_section else "Body Text")
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.paragraph_format.space_after = Pt(8)
        paragraph.paragraph_format.line_spacing = 1.08
        lines = paragraph_text.split("\n")
        for index, line in enumerate(lines):
            if index:
                paragraph.add_run().add_break()
            run = paragraph.add_run(line)
            run.font.name = "Arial"
            run.font.size = Pt(10.5)

    document.add_paragraph("")
    for line in _signoff_lines():
        document.add_paragraph(line)
    if os.path.exists(LOGO_PATH):
        document.add_picture(LOGO_PATH, width=Inches(1.8))
    buffer = BytesIO()
    document.save(buffer)
    filename = f"{details.get('name', 'Candidate').replace(' ', '_')}_{details.get('letter_name', 'Letter').replace(' ', '_')}.docx"
    return buffer.getvalue(), filename


def _pdf_escape(text):
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def generate_letter_pdf(details, content=None, edits=None):
    if details.get("letter_type") == "internship_certificate":
        # The certificate is a fixed-design image, so render it straight to
        # PDF instead of going through the docx/LibreOffice conversion path.
        buffer = BytesIO()
        _render_certificate_image(details).save(buffer, format="PDF", resolution=150.0)
        return buffer.getvalue()
    # Prefer a real office conversion so the PDF preserves the uploaded
    # template's exact pagination, alignment, fonts, headers, and footers.
    converter = shutil.which("soffice") or shutil.which("libreoffice")
    if not converter:
        for candidate in (
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ):
            if os.path.exists(candidate):
                converter = candidate
                break
    if converter:
        temp_dir = tempfile.mkdtemp(prefix="datapattern-letter-")
        try:
            docx_bytes, filename = generate_letter_docx(details, content, edits)
            source = os.path.join(temp_dir, filename)
            profile_dir = os.path.join(temp_dir, "lo-profile")
            with open(source, "wb") as handle:
                handle.write(docx_bytes)
            result = subprocess.run(
                [converter, "--headless", "--nologo", "--nofirststartwizard", "--norestore",
                 f"-env:UserInstallation=file:///{profile_dir.replace(os.sep, '/')}",
                 "--convert-to", "pdf", "--outdir", temp_dir, source],
                capture_output=True,
                timeout=30,  # Reduced from 45 to 30 seconds
                check=False,
            )
            output = os.path.splitext(source)[0] + ".pdf"
            if result.returncode == 0 and os.path.exists(output):
                with open(output, "rb") as handle:
                    return handle.read()
        except Exception:
            pass
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # Fallback for hosts without LibreOffice (for example minimal serverless
    # environments). The fallback keeps all text and dynamic values intact,
    # but cannot preserve the source DOCX layout exactly.
    title_font = _load_font(34, bold=True)
    body_font = _load_font(24)
    small_font = _load_font(21)

    paragraphs = _paragraphs_from_content(content or letter_content(details))
    pages = []
    current = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), "white")
    draw = ImageDraw.Draw(current)
    y = MARGIN_Y

    def draw_page_chrome():
        """Render the reference document's logo header and confidential footer."""
        nonlocal y
        if os.path.exists(LOGO_PATH):
            try:
                logo = Image.open(LOGO_PATH).convert("RGB")
                target_width = 540
                ratio = target_width / logo.width
                logo = logo.resize((target_width, int(logo.height * ratio)))
                current.paste(logo, (MARGIN_X, 36))
                y = max(y, 150)
            except Exception:
                pass
        footer_font = _load_font(16, bold=True)
        footer_y = PAGE_HEIGHT - 40
        if _uses_split_footer(details):
            draw.text((MARGIN_X, footer_y), _footer_left_text(details), fill="black", font=footer_font)
            right_text = "Private & confidential"
            right_width = draw.textbbox((0, 0), right_text, font=footer_font)[2]
            draw.text((PAGE_WIDTH - MARGIN_X - right_width, footer_y), right_text, fill="black", font=footer_font)
        else:
            text_width = draw.textbbox((0, 0), COMPANY_ADDRESS, font=footer_font)[2]
            draw.text(((PAGE_WIDTH - text_width) / 2, footer_y), COMPANY_ADDRESS, fill="black", font=footer_font)

    draw_page_chrome()

    def flush_page():
        nonlocal current, draw, y
        pages.append(current)
        current = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), "white")
        draw = ImageDraw.Draw(current)
        y = MARGIN_Y
        draw_page_chrome()

    def draw_wrapped(text, font, spacing=10):
        nonlocal y
        if not text:
            y += spacing
            return
        max_width = PAGE_WIDTH - (MARGIN_X * 2)
        words = text.split()
        lines = []
        line = ""
        for word in words:
            trial = f"{line} {word}".strip()
            if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
                line = trial
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        for wrapped in lines:
            if y > PAGE_HEIGHT - 260:
                flush_page()
            draw.text((MARGIN_X, y), wrapped, fill="black", font=font)
            bbox = draw.textbbox((0, 0), wrapped, font=font)
            y += (bbox[3] - bbox[1]) + spacing

    draw.text((MARGIN_X, y), details.get("letter_name", "Letter").upper(), fill="black", font=title_font)
    y += 70
    for paragraph in paragraphs:
        for line in paragraph.split("\n"):
            draw_wrapped(line, body_font)
        y += 14

    if y > PAGE_HEIGHT - 340:
        flush_page()

    y += 12
    for line in _signoff_lines():
        if line:
            draw_wrapped(line, small_font, spacing=7)
        else:
            y += 8

    if os.path.exists(LOGO_PATH):
        try:
            logo = Image.open(LOGO_PATH).convert("RGB")
            target_width = 220
            ratio = target_width / logo.width
            logo = logo.resize((target_width, int(logo.height * ratio)))
            if y + logo.height > PAGE_HEIGHT - 90:
                flush_page()
            current.paste(logo, (MARGIN_X, y))
        except Exception:
            pass

    pages.append(current)
    buffer = BytesIO()
    pages[0].save(buffer, format="PDF", save_all=True, append_images=pages[1:], resolution=150.0)
    return buffer.getvalue()
