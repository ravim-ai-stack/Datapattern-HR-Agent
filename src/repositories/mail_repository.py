"""Data access for outgoing mail: the only place that talks to Microsoft Graph."""

import base64
import os

from src.database.database import get_database
from src.settings.settings import LOGO_PATH


def read_logo_attachment():
    """The inline DataPattern logo as a Graph fileAttachment, or None if the file is missing."""
    if not os.path.exists(LOGO_PATH):
        return None
    with open(LOGO_PATH, "rb") as logo_file:
        return {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": "datapattern-logo.png",
            "contentType": "image/png",
            "contentBytes": base64.b64encode(logo_file.read()).decode("utf-8"),
            "isInline": True,
            "contentId": "datapattern-logo",
        }


def send_mail(sender_email, payload):
    get_database().request("POST", f"users/{sender_email}/sendMail", json=payload)
