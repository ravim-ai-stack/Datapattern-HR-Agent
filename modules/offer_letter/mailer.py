"""Dispatches finalized HR letters using Microsoft Graph API."""

import base64
import os
import re

from core.graph_api import graph_post
from .email_template import build_email_html, build_email_plain


def is_valid_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-.]+$"
    return bool(re.match(pattern, email.strip()))


def _attachment_content_type(filename):
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _logo_attachment():
    app_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    logo_path = os.path.join(app_root, "static", "img", "datapattern-logo.png")
    if not os.path.exists(logo_path):
        return None
    with open(logo_path, "rb") as logo_file:
        return {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": "datapattern-logo.png",
            "contentType": "image/png",
            "contentBytes": base64.b64encode(logo_file.read()).decode("utf-8"),
            "isInline": True,
            "contentId": "datapattern-logo",
        }


def dispatch_offer_email(recipient_email: str, cc_email: str, candidate_name: str,
                         role: str, attachments: list, sender_email: str,
                         subject: str = None, custom_message: str = None) -> dict:
    if not sender_email or not sender_email.strip():
        sender_email = os.getenv("SYSTEM_SENDER_EMAIL", "")

    if not sender_email.strip() or not is_valid_email(sender_email.strip()):
        return {"success": False, "message": "Missing or Invalid Sender Email. Please check your .env file."}

    if not is_valid_email(recipient_email):
        return {"success": False, "message": "Invalid recipient email address format."}

    cc_recipients = []
    if cc_email.strip():
        raw_ccs = [e.strip() for e in cc_email.replace(";", ",").split(",") if e.strip()]
        for cc in raw_ccs:
            if is_valid_email(cc):
                cc_recipients.append({"emailAddress": {"address": cc}})
            else:
                return {"success": False, "message": f"Invalid CC email format detected: {cc}"}

    file_attachments = [
        {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": filename,
            "contentType": _attachment_content_type(filename),
            "contentBytes": base64.b64encode(data).decode("utf-8"),
        }
        for filename, data in attachments
    ]
    logo = _logo_attachment()
    if logo:
        file_attachments.append(logo)

    email_payload = {
        "message": {
            "subject": (subject or f"{role} Letter - DataPattern").strip(),
            "body": {
                "contentType": "HTML",
                "content": build_email_html(candidate_name, role, custom_message=custom_message),
            },
            "toRecipients": [
                {"emailAddress": {"address": recipient_email.strip()}}
            ],
            "ccRecipients": cc_recipients,
            "attachments": file_attachments,
        },
        "saveToSentItems": "true",
    }

    try:
        endpoint = f"users/{sender_email.strip()}/sendMail"
        graph_post(endpoint, json_data=email_payload)
        return {"success": True, "message": f"Email dispatched successfully to **{recipient_email}**"}
    except Exception as e:
        return {"success": False, "message": f"Microsoft Graph API Error: {str(e)}"}
