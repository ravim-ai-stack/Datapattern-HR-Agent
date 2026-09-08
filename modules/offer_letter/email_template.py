"""Builds HTML and plain-text email bodies for HR letter dispatch."""

from html import escape


def _html_paragraphs(message):
    blocks = []
    for paragraph in (message or "").split("\n\n"):
        paragraph = paragraph.strip()
        if paragraph:
            blocks.append(f"<p>{escape(paragraph).replace(chr(10), '<br>')}</p>")
    return "\n".join(blocks)


def build_email_html(candidate_name: str, role: str, custom_message: str = None) -> str:
    body_content = custom_message.strip() if custom_message and custom_message.strip() else (
        f"Dear {candidate_name},\n\n"
        f"Please find the attached letter for the position of {role} at DataPattern.\n\n"
        "Kindly review the document and contact the HR team if any clarification is required."
    )

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DataPattern HR Letter</title>
</head>
<body style="margin:0;padding:0;background:#ffffff;font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#1a1a1a;line-height:1.7;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;padding:32px 24px;">
    <tr>
      <td align="left" style="max-width:680px;">
        {_html_paragraphs(body_content)}
        <p style="margin-top:28px;margin-bottom:0;">
          <img src="cid:datapattern-logo" alt="DataPattern" style="width:140px;max-width:100%;height:auto;display:block;">
        </p>
      </td>
    </tr>
  </table>
</body>
</html>"""


def build_email_plain(candidate_name: str, role: str, custom_message: str = None) -> str:
    if custom_message and custom_message.strip():
        return custom_message.strip()
    return (
        f"Dear {candidate_name},\n\n"
        f"Please find the attached letter for the position of {role} at DataPattern.\n\n"
        "Kindly review the document and contact the HR team if any clarification is required."
    )
