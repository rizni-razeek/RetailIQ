from flask import Blueprint


api_blueprint = Blueprint("api", __name__)

from app.routes import auth, health, uploads  # noqa: E402, F401
