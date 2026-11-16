"""Downloadable files: Word, PDF (via LibreOffice, with a Pillow fallback) and certificate JPEG."""

import os
import shutil
import subprocess
import tempfile
from io import BytesIO

from PIL import Image, ImageDraw
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from src.constants.constants import (
    COMPANY_ADDRESS, CUSTOM_SIGNATORY_NAME, CUSTOM_SIGNATORY_TITLE, CUSTOM_SIGNOFF_CLOSING, MARGIN_X, MARGIN_Y, PAGE_HEIGHT, PAGE_WIDTH,
)
from src.repositories.template_repository import _is_it_asset_form, _template_path
from src.services.certificate_service import _generate_certificate_docx, _render_certificate_image
from src.services.document_service import _add_footer_content, _apply_edited_blocks, _render_it_asset_form, _render_source_template
from src.services.letter_service import letter_content
from src.settings.settings import LOGO_PATH, SIGNATURE_PATH
from src.utils.fonts import _load_font
from src.utils.letter_text import _footer_left_text, _is_custom_letter, _paragraphs_from_content, _signoff_lines, _uses_split_footer


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
    if _is_custom_letter(details):
        document.add_paragraph(CUSTOM_SIGNOFF_CLOSING)
        if os.path.exists(SIGNATURE_PATH):
            document.add_paragraph().add_run().add_picture(SIGNATURE_PATH, width=Inches(1.8))
        for line in (CUSTOM_SIGNATORY_NAME, CUSTOM_SIGNATORY_TITLE):
            document.add_paragraph().add_run(line).bold = True
    else:
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
    custom = _is_custom_letter(details)
    if custom:
        draw_wrapped(CUSTOM_SIGNOFF_CLOSING, small_font, spacing=7)
        if os.path.exists(SIGNATURE_PATH):
            try:
                signature = Image.open(SIGNATURE_PATH).convert("RGB")
                signature = signature.resize((200, int(signature.height * 200 / signature.width)))
                if y + signature.height > PAGE_HEIGHT - 200:
                    flush_page()
                current.paste(signature, (MARGIN_X, y))
                y += signature.height + 8
            except Exception:
                pass
        bold_font = _load_font(21, bold=True)
        draw_wrapped(CUSTOM_SIGNATORY_NAME, bold_font, spacing=7)
        draw_wrapped(CUSTOM_SIGNATORY_TITLE, bold_font, spacing=7)
    else:
        for line in _signoff_lines():
            if line:
                draw_wrapped(line, small_font, spacing=7)
            else:
                y += 8

    if not custom and os.path.exists(LOGO_PATH):
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
