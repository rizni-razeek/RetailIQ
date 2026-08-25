from flask import current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models import ForecastRun, Upload, User
from app.routes import api_blueprint
from app.services.analytics_service import (
    build_anomaly_summary,
    build_category_summaries,
    build_forecast_summary,
    build_overview,
    build_sales_trends,
    build_stock_summary,
)
from app.services.anomaly_service import AnomalyAnalysisError, NoEligibleFamiliesError
from app.services.model_service import get_model


def _authenticated_user():
    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return None
    return db.session.get(User, user_id)


def _optional_positive_integer(name):
    raw_value = request.args.get(name)
    if raw_value is None:
        return None, None
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None, f"{name} must be a positive integer."
    if value < 1:
        return None, f"{name} must be a positive integer."
    return value, None


def _tenant_upload(business_id, upload_id):
    return db.session.scalar(
        db.select(Upload).where(
            Upload.id == upload_id,
            Upload.business_id == business_id,
        )
    )


def _latest_tenant_upload(business_id):
    return db.session.scalar(
        db.select(Upload)
        .where(Upload.business_id == business_id)
        .order_by(Upload.uploaded_at.desc(), Upload.id.desc())
    )


def _tenant_forecast_run(business_id, forecast_run_id):
    return db.session.scalar(
        db.select(ForecastRun).where(
            ForecastRun.id == forecast_run_id,
            ForecastRun.business_id == business_id,
        )
    )


@api_blueprint.get("/analytics/overview")
@jwt_required()
def analytics_overview():
    user = _authenticated_user()
    if user is None:
        return jsonify({"error": "Authenticated user no longer exists."}), 401

    model = get_model(current_app.config["MODEL_PATH"])
    overview = build_overview(
        user.business_id,
        model,
        current_app.config["ANOMALY_Z_THRESHOLD"],
        current_app.config["STOCK_OVERSTOCK_MULTIPLIER"],
    )
    return jsonify({"overview": overview}), 200


@api_blueprint.get("/analytics/sales-trends")
@jwt_required()
def analytics_sales_trends():
    user = _authenticated_user()
    if user is None:
        return jsonify({"error": "Authenticated user no longer exists."}), 401

    upload_id, error = _optional_positive_integer("upload_id")
    if error:
        return jsonify({"error": error}), 400
    if upload_id is not None:
        if _tenant_upload(user.business_id, upload_id) is None:
            return jsonify({"error": "Upload not found."}), 404
    else:
        latest_upload = _latest_tenant_upload(user.business_id)
        upload_id = latest_upload.id if latest_upload else None

    family_value = request.args.get("family")
    family = family_value.strip().upper() if family_value is not None else None
    if family_value is not None and not family:
        return jsonify({"error": "family must be non-empty."}), 400

    result = build_sales_trends(user.business_id, upload_id, family)
    return jsonify({"sales_trends": result}), 200


@api_blueprint.get("/analytics/categories")
@jwt_required()
def analytics_categories():
    user = _authenticated_user()
    if user is None:
        return jsonify({"error": "Authenticated user no longer exists."}), 401

    upload_id, error = _optional_positive_integer("upload_id")
    if error:
        return jsonify({"error": error}), 400
    if upload_id is not None:
        if _tenant_upload(user.business_id, upload_id) is None:
            return jsonify({"error": "Upload not found."}), 404
    else:
        latest_upload = _latest_tenant_upload(user.business_id)
        upload_id = latest_upload.id if latest_upload else None

    result = build_category_summaries(user.business_id, upload_id)
    return jsonify({"category_summary": result}), 200


@api_blueprint.get("/analytics/forecast-summary")
@jwt_required()
def analytics_forecast_summary():
    user = _authenticated_user()
    if user is None:
        return jsonify({"error": "Authenticated user no longer exists."}), 401

    forecast_run_id, error = _optional_positive_integer("forecast_run_id")
    if error:
        return jsonify({"error": error}), 400
    forecast_run = None
    if forecast_run_id is not None:
        forecast_run = _tenant_forecast_run(user.business_id, forecast_run_id)
        if forecast_run is None:
            return jsonify({"error": "Forecast run not found."}), 404

    result = build_forecast_summary(user.business_id, forecast_run)
    return jsonify({"forecast_summary": result}), 200


@api_blueprint.get("/analytics/stock-summary")
@jwt_required()
def analytics_stock_summary():
    user = _authenticated_user()
    if user is None:
        return jsonify({"error": "Authenticated user no longer exists."}), 401

    forecast_run_id, error = _optional_positive_integer("forecast_run_id")
    if error:
        return jsonify({"error": error}), 400
    forecast_run = None
    if forecast_run_id is not None:
        forecast_run = _tenant_forecast_run(user.business_id, forecast_run_id)
        if forecast_run is None:
            return jsonify({"error": "Forecast run not found."}), 404

    result = build_stock_summary(
        user.business_id,
        current_app.config["STOCK_OVERSTOCK_MULTIPLIER"],
        forecast_run,
    )
    return jsonify({"stock_summary": result}), 200


@api_blueprint.get("/analytics/anomaly-summary")
@jwt_required()
def analytics_anomaly_summary():
    user = _authenticated_user()
    if user is None:
        return jsonify({"error": "Authenticated user no longer exists."}), 401

    upload_id, error = _optional_positive_integer("upload_id")
    if error:
        return jsonify({"error": error}), 400
    upload = None
    if upload_id is not None:
        upload = _tenant_upload(user.business_id, upload_id)
        if upload is None:
            return jsonify({"error": "Upload not found."}), 404

    model = get_model(current_app.config["MODEL_PATH"])
    if model is None and upload is not None:
        return jsonify({"error": "The forecasting model is unavailable."}), 503

    try:
        result = build_anomaly_summary(
            user.business_id,
            model,
            current_app.config["ANOMALY_Z_THRESHOLD"],
            upload,
        )
    except NoEligibleFamiliesError as analysis_error:
        return jsonify(
            {
                "error": str(analysis_error),
                "excluded_families": analysis_error.excluded_families,
            }
        ), 422
    except AnomalyAnalysisError as analysis_error:
        current_app.logger.error("Analytics anomaly summary failed: %s", analysis_error)
        return jsonify({"error": str(analysis_error)}), 503

    return jsonify({"anomaly_summary": result}), 200
