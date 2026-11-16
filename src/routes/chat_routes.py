"""JSON/file endpoints for the HR Studio chatbot."""

from io import BytesIO

from flask import Blueprint, jsonify, request, send_file

from src.services import chat_service

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")


@chat_bp.route("", methods=["POST"])
def chat():
    return jsonify(chat_service.chat(request.get_json(force=True) or {}))


@chat_bp.route("/download", methods=["POST"])
def download():
    file_bytes, filename, mimetype = chat_service.build_download(request.get_json(force=True) or {})
    return send_file(BytesIO(file_bytes), as_attachment=True, download_name=filename, mimetype=mimetype)
