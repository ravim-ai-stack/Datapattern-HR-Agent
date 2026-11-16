"""JSON/file endpoints for creating, updating and downloading a letter draft."""

from io import BytesIO

from flask import Blueprint, jsonify, request, send_file

from src.services import draft_service

letter_bp = Blueprint("letters", __name__, url_prefix="/api")


@letter_bp.route("/generate-draft", methods=["POST"])
def generate_draft():
    return jsonify(draft_service.create_draft(request.get_json(force=True) or {}))


@letter_bp.route("/update-draft", methods=["POST"])
def update_draft():
    return jsonify(draft_service.update_draft(request.get_json(force=True) or {}))


@letter_bp.route("/download", methods=["POST"])
def download_draft():
    file_bytes, filename, mimetype = draft_service.build_download(request.get_json(force=True) or {})
    return send_file(BytesIO(file_bytes), as_attachment=True, download_name=filename, mimetype=mimetype)
