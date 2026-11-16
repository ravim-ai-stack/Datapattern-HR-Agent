"""Internship completion certificate: a fixed-design image with the candidate's details drawn on."""

from io import BytesIO

from PIL import Image, ImageDraw
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from src.constants.constants import (
    CERTIFICATE_APPRECIATION_BAND, CERTIFICATE_BLACK, CERTIFICATE_NAME_BAND, CERTIFICATE_NAVY,
    CERTIFICATE_SENTENCE_BAND, CERTIFICATE_TEXT_LEFT, CERTIFICATE_TEXT_RIGHT,
)
from src.settings.settings import CERTIFICATE_TEMPLATE_PATH
from src.utils.fonts import _fit_certificate_font, _load_certificate_font
from src.utils.letter_text import _candidate, _certificate_pronoun, _end_date_text, _joining_text


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
