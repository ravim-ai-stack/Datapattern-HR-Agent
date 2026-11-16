"""Builds and dispatches the HR letter email."""

import base64
from html import escape

from src.repositories import mail_repository
from src.settings.settings import settings
from src.utils import error_codes
from src.utils.custom_app_exception import AppException
from src.utils.logger import get_logger
from src.utils.validators import is_valid_email

logger = get_logger(__name__)


def _html_paragraphs(message):
    blocks = []
    for paragraph in (message or "").split("\n\n"):
        paragraph = paragraph.strip()
        if paragraph:
            blocks.append(f"<p>{escape(paragraph).replace(chr(10), '<br>')}</p>")
    return "\n".join(blocks)


def _default_body(candidate_name, role):
    return (
        f"Dear {candidate_name},\n\n"
        f"Please find the attached letter for the position of {role} at DataPattern.\n\n"
        "Kindly review the document and contact the HR team if any clarification is required."
    )


def build_email_html(candidate_name, role, custom_message=None):
    body_content = custom_message.strip() if custom_message and custom_message.strip() else _default_body(candidate_name, role)
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


def build_email_plain(candidate_name, role, custom_message=None):
    if custom_message and custom_message.strip():
        return custom_message.strip()
    return _default_body(candidate_name, role)


def _attachment_content_type(filename):
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _parse_cc(cc_email):
    recipients = []
    for cc in (e.strip() for e in (cc_email or "").replace(";", ",").split(",") if e.strip()):
        if not is_valid_email(cc):
            raise AppException(error_codes.INVALID_CC_EMAIL, f"Invalid CC email format detected: {cc}")
        recipients.append({"emailAddress": {"address": cc}})
    return recipients


def dispatch_offer_email(recipient_email, cc_email, candidate_name, role, attachments, sender_email,
                         subject=None, custom_message=None):
    """Send the finalized letter. Raises AppException for invalid input or a failed send;
    returns the success message otherwise."""
    sender_email = (sender_email or "").strip() or settings.system_sender_email.strip()
    if not sender_email or not is_valid_email(sender_email):
        raise AppException(error_codes.INVALID_SENDER_EMAIL, "Missing or Invalid Sender Email. Please check your .env file.")
    if not is_valid_email(recipient_email):
        raise AppException(error_codes.INVALID_RECIPIENT_EMAIL, "Invalid recipient email address format.")
    cc_recipients = _parse_cc(cc_email)

    file_attachments = [
        {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": filename,
            "contentType": _attachment_content_type(filename),
            "contentBytes": base64.b64encode(data).decode("utf-8"),
        }
        for filename, data in attachments
    ]
    logo = mail_repository.read_logo_attachment()
    if logo:
        file_attachments.append(logo)

    payload = {
        "message": {
            "subject": (subject or f"{role} Letter - DataPattern").strip(),
            "body": {"contentType": "HTML", "content": build_email_html(candidate_name, role, custom_message=custom_message)},
            "toRecipients": [{"emailAddress": {"address": recipient_email.strip()}}],
            "ccRecipients": cc_recipients,
            "attachments": file_attachments,
        },
        "saveToSentItems": "true",
    }
    try:
        mail_repository.send_mail(sender_email, payload)
    except Exception as exc:
        logger.exception("Email dispatch to %s failed", recipient_email)
        raise AppException(error_codes.EMAIL_SEND_FAILED, f"Microsoft Graph API Error: {exc}")
    logger.info("Email dispatched to %s", recipient_email)
    return f"Email dispatched successfully to **{recipient_email}**"
