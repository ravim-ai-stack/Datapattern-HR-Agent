"""HTML previews of the generated letter (full preview and editable body)."""

import base64
from html import escape

from src.constants.constants import COMPANY_ADDRESS, CUSTOM_SIGNATORY_NAME, CUSTOM_SIGNATORY_TITLE, CUSTOM_SIGNOFF_CLOSING
from src.repositories.template_repository import _template_path
from src.services.certificate_service import _certificate_image_bytes
from src.services.letter_service import _template_blocks, letter_content
from src.utils.letter_text import _footer_left_text, _is_custom_letter, _paragraphs_from_content, _signoff_lines, _uses_split_footer


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
    custom = _is_custom_letter(details)
    if custom:
        signoff = (
            f"<p>{escape(CUSTOM_SIGNOFF_CLOSING)}</p>"
            '<img class="letter-signature" src="/static/img/indhirajith-signature.jpeg" alt="Signature">'
            f"<p><strong>{escape(CUSTOM_SIGNATORY_NAME)}</strong></p><p><strong>{escape(CUSTOM_SIGNATORY_TITLE)}</strong></p>"
        )
    else:
        signoff = "" if is_template else "".join(f"<p>{escape(line)}</p>" if line else "<br>" for line in _signoff_lines())
    logo = '<img src="/static/img/datapattern-logo.png" alt="DataPattern">'
    title_html = f"<h1>{heading}</h1>" if heading else ""
    signoff_logo = "" if custom or details.get("letter_type") == "appraisal" else '<img src="/static/img/datapattern-logo.png" alt="DataPattern">'
    signature = ""
    if _uses_split_footer(details):
        footer_left = escape(_footer_left_text(details))
        footer_html = f'<span class="letter-footer-left">{footer_left}</span><span class="letter-footer-right">Private &amp; confidential</span>'
        footer_style = "display:flex;justify-content:space-between;"
    else:
        footer_html = escape(COMPANY_ADDRESS)
        footer_style = "text-align:center;"
    return f'<article><div class="letter-header">{logo}</div>{title_html}{body_html}<div class="letter-signoff">{signoff}{signature}{signoff_logo}</div><div class="letter-footer" style="{footer_style}">{footer_html}</div></article>'
