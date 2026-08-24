from flask import Flask, jsonify
from werkzeug.exceptions import RequestEntityTooLarge

from app.extensions import db, jwt, migrate
from app.models import Business, Forecast, ForecastRun, SalesRecord, Upload, User  # noqa: F401
from app.routes import api_blueprint
from config import Config


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.from_mapping(test_config)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    app.register_blueprint(api_blueprint, url_prefix="/api")

    @app.errorhandler(RequestEntityTooLarge)
    def handle_upload_too_large(_error):
        return jsonify({"error": "The uploaded file is too large."}), 413

    return app
