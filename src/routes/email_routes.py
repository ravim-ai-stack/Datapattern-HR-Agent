"""Endpoint that emails the finalized letter."""

from flask import Blueprint, jsonify, request

from src.constants.constants import MAX_UPLOAD_BYTES
from src.services import email_service
from src.utils import error_codes
from src.utils.custom_app_exception import AppException

email_bp = Blueprint("email", __name__, url_prefix="/api")


@email_bp.route("/send-email", methods=["POST"])
def send_email():
    uploads = [f for f in request.files.getlist("attachment") if f.filename]
    if not uploads:
        raise AppException(error_codes.ATTACHMENT_REQUIRED, "Please upload the final document.")
    attachments = [(f.filename, f.read()) for f in uploads]
    if sum(len(data) for _, data in attachments) > MAX_UPLOAD_BYTES:
        raise AppException(error_codes.ATTACHMENTS_TOO_LARGE, "Files exceed the 10MB limit.")
    message = email_service.dispatch_offer_email(
        recipient_email=request.form.get("recipient_email", ""),
        cc_email=request.form.get("cc_email", ""),
        candidate_name=request.form.get("receiver_name", ""),
        role=request.form.get("role", ""),
        attachments=attachments,
        sender_email=request.form.get("sender_email", ""),
        subject=request.form.get("email_subject", ""),
        custom_message=request.form.get("welcome_message", ""),
    )
    return jsonify(success=True, message=message)
