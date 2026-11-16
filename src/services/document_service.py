"""Builds the candidate-specific .docx from a letter template: placeholder
fill, footer/header, layout fixes, and patching of edits from the preview panel."""

import copy
import os
import re

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from docx.table import Table
from docx.text.paragraph import Paragraph

from src.constants.constants import COMPANY_ADDRESS, IT_ASSET_FORM_DATE_LABELS, TEMPLATE_DATE_PATTERN
from src.repositories.template_repository import _template_path, load_template_document
from src.services.appraisal_service import render_appraisal
from src.settings.settings import LOGO_PATH, SIGNATURE_PATH
from src.utils.letter_text import _candidate, _end_date_text, _footer_left_text, _joining_text, _uses_split_footer


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


def _same_text(a, b):
    """Compare ignoring whitespace differences. The editable panel turns a tab
    into a space, so a literal compare would flag untouched paragraphs as
    edited and rewrite them -- e.g. flattening the dotted blank (a tab with a
    dot leader) in "I............, confirm" into plain spaces."""
    return " ".join(a.split()) == " ".join(b.split())


def _patch_paragraphs(paragraphs, edited_texts):
    """`paragraphs` are the rendered template's own (non-blank) Paragraph
    objects in order; `edited_texts` are the corresponding strings from the
    editable panel. Only paragraphs whose text actually changed are
    rewritten, so untouched formatting (e.g. a bold date) survives; extra
    edited entries are appended as new paragraphs, and removed ones are
    cleared rather than deleted (some carry page-layout metadata)."""
    for paragraph, new_text in zip(paragraphs, edited_texts):
        if new_text.strip() and not _same_text(new_text, paragraph.text):
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
                if new_text.strip() and not _same_text(new_text, cell.text):
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
    source = load_template_document(path)
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


def _normalize_offer_annexure_ii(source):
    """The master offer template's Annexure II (Personal Information / IT Act
    declaration) carries a different hand-set indent on nearly every
    paragraph and splits its title across two. Give it one consistent layout:
    centered title, flush-left justified body, evenly hanging a/b/c list."""
    paragraphs = source.paragraphs
    start = next((i for i, p in enumerate(paragraphs) if p.text.strip().upper().startswith("PERSONAL INFORMATION AS REQUIRED")), None)
    if start is None:
        return
    end = next((i for i in range(start + 1, len(paragraphs)) if paragraphs[i].text.strip().upper().startswith("ANNEXURE III")), len(paragraphs))
    for index in range(start, end):
        paragraph = paragraphs[index]
        text = paragraph.text.strip()
        if not text:
            # Empty spacer paragraphs stack unevenly with the spacing set
            # below; drop them unless they carry a page/section break.
            xml = paragraph._p.xml
            if index > start and "w:br" not in xml and "w:sectPr" not in xml and "w:drawing" not in xml:
                paragraph._p.getparent().remove(paragraph._p)
            continue
        fmt = paragraph.paragraph_format
        # Drop the per-paragraph tab stops, right indents, line spacing and
        # per-run character spacing left over from the PDF-to-Word conversion;
        # they are what makes word gaps and line ends uneven.
        p_pr = paragraph._p.find(qn("w:pPr"))
        if p_pr is not None:
            tabs = p_pr.find(qn("w:tabs"))
            if tabs is not None and "	" not in paragraph.text:  # keep the dotted blank's tab leader
                p_pr.remove(tabs)
        for run in paragraph.runs:
            r_pr = run._r.find(qn("w:rPr"))
            if r_pr is not None:
                for char_spacing in r_pr.findall(qn("w:spacing")):
                    r_pr.remove(char_spacing)
        fmt.right_indent = Inches(0)
        fmt.line_spacing = 1.0
        fmt.space_before = Pt(0) if index == start else Pt(8)
        fmt.space_after = Pt(0)
        if index == start or text.upper().startswith("ACT, 2000"):
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            fmt.left_indent = Inches(0)
            fmt.first_line_indent = Inches(0)
        elif paragraph.style.name == "List Paragraph":
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            fmt.left_indent = Inches(0.75)
            fmt.first_line_indent = Inches(-0.25)
        else:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            fmt.left_indent = Inches(0)
            fmt.first_line_indent = Inches(0)


def _render_source_template(details):
    path = _template_path(details)
    if not path:
        return None
    if details.get("letter_type") == "appraisal":
        # Letterpad template: keeps its own header/footer, filled by its own renderer.
        return render_appraisal(details)
    source = load_template_document(path)
    if details.get("letter_type") == "offer":
        _normalize_offer_annexure_ii(source)
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
