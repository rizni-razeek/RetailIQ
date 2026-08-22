from flask import current_app, jsonify

from app.routes import api_blueprint
from app.services.model_service import get_model_status


@api_blueprint.get("/health")
def health_check():
    model_status = get_model_status(current_app.config["MODEL_PATH"])

    return jsonify(
        {
            "status": "healthy",
            "model_available": model_status["available"],
            "model_type": model_status["type"],
        }
    )
