from flask import Flask, jsonify
from werkzeug.exceptions import RequestEntityTooLarge

from app.extensions import db, jwt, migrate
from app.models import (  # noqa: F401
    Business,
    Forecast,
    ForecastRun,
    Inventory,
    SalesRecord,
    Upload,
    User,
)
from app.routes import api_blueprint
from app.routes.pages import pages_blueprint
from app.services.model_provisioning_service import provision_model
from config import Config, validate_production_config


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.from_mapping(test_config)

    validate_production_config(app)
    provision_model(
        model_path=app.config["MODEL_PATH"],
        repository=app.config.get("HF_MODEL_REPO"),
        filename=app.config.get("HF_MODEL_FILENAME"),
        token=app.config.get("HF_TOKEN"),
    )

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    app.register_blueprint(pages_blueprint)
    app.register_blueprint(api_blueprint, url_prefix="/api")

    @app.errorhandler(RequestEntityTooLarge)
    def handle_upload_too_large(_error):
        return jsonify({"error": "The uploaded file is too large."}), 413

    return app
