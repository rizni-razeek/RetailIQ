from flask import Blueprint


api_blueprint = Blueprint("api", __name__)

from app.routes import anomalies, auth, forecasts, health, inventory, uploads  # noqa: E402, F401
