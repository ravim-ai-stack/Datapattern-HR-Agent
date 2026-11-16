"""DataPattern HR letter generator -- application entry point."""

from flask import Flask, jsonify

from src.constants.constants import HTTP_INTERNAL_ERROR, MAX_UPLOAD_BYTES
from src.routes.chat_routes import chat_bp
from src.routes.email_routes import email_bp
from src.routes.letter_routes import letter_bp
from src.routes.page_routes import page_bp
from src.settings.settings import STATIC_DIR, TEMPLATES_FOLDER, settings
from src.utils.custom_app_exception import AppException
from src.utils.error_codes import INTERNAL_ERROR
from src.utils.error_mappers import map_error
from src.utils.logger import get_logger

logger = get_logger(__name__)


def create_app():
    app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TEMPLATES_FOLDER)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    for blueprint in (page_bp, letter_bp, email_bp, chat_bp):
        app.register_blueprint(blueprint)

    @app.errorhandler(AppException)
    def handle_app_exception(exc):
        body, status = map_error(exc)
        logger.warning("%s: %s", exc.code, exc.message)
        return jsonify(body), status

    @app.errorhandler(Exception)
    def handle_unexpected(exc):
        from werkzeug.exceptions import HTTPException

        if isinstance(exc, HTTPException):
            return exc
        logger.exception("Unhandled error")
        return jsonify(success=False, error=str(exc), message=str(exc), code=INTERNAL_ERROR), HTTP_INTERNAL_ERROR

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=settings.port)
