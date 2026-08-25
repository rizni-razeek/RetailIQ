from flask import current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models import Upload, User
from app.routes import api_blueprint
from app.services.anomaly_service import (
    AnomalyAnalysisError,
    NoEligibleFamiliesError,
    analyse_anomalies,
)
from app.services.model_service import get_model


def _authenticated_user():
    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return None
    return db.session.get(User, user_id)


@api_blueprint.post("/anomalies")
@jwt_required()
def detect_anomalies():
    user = _authenticated_user()
    if user is None:
        return jsonify({"error": "Authenticated user no longer exists."}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON request body is required."}), 400

    upload_id = data.get("upload_id")
    if isinstance(upload_id, bool) or not isinstance(upload_id, int) or upload_id < 1:
        return jsonify({"error": "upload_id must be a positive integer."}), 400

    upload = db.session.scalar(
        db.select(Upload).where(
            Upload.id == upload_id,
            Upload.business_id == user.business_id,
        )
    )
    if upload is None:
        return jsonify({"error": "Upload not found."}), 404

    model = get_model(current_app.config["MODEL_PATH"])
    if model is None:
        return jsonify({"error": "The forecasting model is unavailable."}), 503

    try:
        result = analyse_anomalies(
            business_id=user.business_id,
            upload_id=upload.id,
            model=model,
            z_threshold=current_app.config["ANOMALY_Z_THRESHOLD"],
        )
    except NoEligibleFamiliesError as error:
        return jsonify(
            {"error": str(error), "excluded_families": error.excluded_families}
        ), 422
    except AnomalyAnalysisError as error:
        current_app.logger.error("Anomaly analysis failed: %s", error)
        return jsonify({"error": str(error)}), 503

    return jsonify({"anomaly_analysis": result}), 200
