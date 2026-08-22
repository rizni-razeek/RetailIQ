from flask import Flask

from config import Config
from app.routes import api_blueprint


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.from_mapping(test_config)

    app.register_blueprint(api_blueprint, url_prefix="/api")

    return app
