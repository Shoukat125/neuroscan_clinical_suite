from dotenv import load_dotenv
load_dotenv()

from flask import Flask

from core.config import UPLOAD_DIR, RESULT_DIR, MAX_CONTENT_LENGTH
from routes.scan import scan_bp
from routes.region_vqa import vqa_bp
from routes.advisory import advisory_bp
from routes.report import report_bp
from routes.document_chat import chat_bp


def create_app():
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
    app.config["UPLOAD_DIR"] = UPLOAD_DIR
    app.config["RESULT_DIR"] = RESULT_DIR

    # Register Blueprints
    app.register_blueprint(scan_bp)
    app.register_blueprint(vqa_bp)
    app.register_blueprint(advisory_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(chat_bp)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
