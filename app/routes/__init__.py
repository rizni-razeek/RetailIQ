from flask import Blueprint


api_blueprint = Blueprint("api", __name__)

from app.routes import (  # noqa: E402, F401
    analytics,
    anomalies,
    auth,
    forecasts,
    health,
    inventory,
    uploads,
)
