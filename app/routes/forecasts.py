from flask import current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import ForecastRun, Upload, User
from app.routes import api_blueprint
from app.services.forecasting_service import (
    ForecastingError,
    InsufficientHistoryError,
    generate_forecast,
    serialize_forecast_run,
)
from app.services.model_service import get_model


ALLOWED_HORIZONS = {7, 14, 30}


def _authenticated_user():
    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return None
    return db.session.get(User, user_id)


@api_blueprint.post("/forecasts")
@jwt_required()
def create_forecast():
    user = _authenticated_user()
    if user is None:
        return jsonify({"error": "Authenticated user no longer exists."}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON request body is required."}), 400

    upload_id = data.get("upload_id")
    horizon = data.get("horizon")
    if isinstance(upload_id, bool) or not isinstance(upload_id, int) or upload_id < 1:
        return jsonify({"error": "upload_id must be a positive integer."}), 400
    if isinstance(horizon, bool) or horizon not in ALLOWED_HORIZONS:
        return jsonify({"error": "horizon must be exactly 7, 14, or 30."}), 400

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
        forecast_run = generate_forecast(
            business_id=user.business_id,
            upload_id=upload.id,
            horizon=horizon,
            model=model,
            future_onpromotion=current_app.config["FORECAST_FUTURE_ONPROMOTION"],
        )
        db.session.commit()
    except InsufficientHistoryError as error:
        db.session.rollback()
        return jsonify(
            {
                "error": str(error),
                "excluded_families": error.excluded_families,
            }
        ), 422
    except ForecastingError as error:
        db.session.rollback()
        current_app.logger.error("Forecast generation failed: %s", error)
        return jsonify({"error": str(error)}), 503
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Forecast results could not be stored.")
        return jsonify({"error": "Forecast results could not be stored."}), 500

    return jsonify(
        {"forecast_run": serialize_forecast_run(forecast_run, include_predictions=True)}
    ), 201


@api_blueprint.get("/forecasts")
@jwt_required()
def list_forecasts():
    user = _authenticated_user()
    if user is None:
        return jsonify({"error": "Authenticated user no longer exists."}), 401

    forecast_runs = db.session.scalars(
        db.select(ForecastRun)
        .where(ForecastRun.business_id == user.business_id)
        .order_by(ForecastRun.generated_at.desc(), ForecastRun.id.desc())
    ).all()
    return jsonify(
        {
            "forecast_runs": [
                serialize_forecast_run(forecast_run) for forecast_run in forecast_runs
            ]
        }
    ), 200


@api_blueprint.get("/forecasts/<int:forecast_run_id>")
@jwt_required()
def get_forecast(forecast_run_id):
    user = _authenticated_user()
    if user is None:
        return jsonify({"error": "Authenticated user no longer exists."}), 401

    forecast_run = db.session.scalar(
        db.select(ForecastRun).where(
            ForecastRun.id == forecast_run_id,
            ForecastRun.business_id == user.business_id,
        )
    )
    if forecast_run is None:
        return jsonify({"error": "Forecast run not found."}), 404

    return jsonify(
        {"forecast_run": serialize_forecast_run(forecast_run, include_predictions=True)}
    ), 200
