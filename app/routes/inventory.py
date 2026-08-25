import math
from datetime import datetime, timezone

from flask import current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import ForecastRun, Inventory, User
from app.routes import api_blueprint
from app.services.stock_service import build_stock_intelligence


def _authenticated_user():
    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return None
    return db.session.get(User, user_id)


def _normalise_family(value):
    return value.strip().upper() if isinstance(value, str) else ""


@api_blueprint.post("/inventory")
@jwt_required()
def create_or_update_inventory():
    user = _authenticated_user()
    if user is None:
        return jsonify({"error": "Authenticated user no longer exists."}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON request body is required."}), 400

    family = _normalise_family(data.get("family"))
    if not family:
        return jsonify({"error": "family must be a non-empty string."}), 400
    if len(family) > 150:
        return jsonify({"error": "family must not exceed 150 characters."}), 400

    current_stock = data.get("current_stock")
    if isinstance(current_stock, bool) or not isinstance(current_stock, (int, float)):
        return jsonify({"error": "current_stock must be a finite numeric value."}), 400
    try:
        stock_value = float(current_stock)
    except OverflowError:
        return jsonify({"error": "current_stock must be a finite numeric value."}), 400
    if not math.isfinite(stock_value):
        return jsonify({"error": "current_stock must be a finite numeric value."}), 400
    if stock_value < 0:
        return jsonify({"error": "current_stock cannot be negative."}), 400

    inventory = db.session.scalar(
        db.select(Inventory).where(
            Inventory.business_id == user.business_id,
            Inventory.family == family,
        )
    )
    created = inventory is None
    if created:
        inventory = Inventory(
            business_id=user.business_id,
            family=family,
            current_stock=stock_value,
        )
        db.session.add(inventory)
    else:
        inventory.current_stock = stock_value
        inventory.updated_at = datetime.now(timezone.utc)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Inventory could not be saved.")
        return jsonify({"error": "Inventory could not be saved."}), 500

    return jsonify({"inventory": inventory.to_dict()}), 201 if created else 200


@api_blueprint.get("/inventory")
@jwt_required()
def list_inventory():
    user = _authenticated_user()
    if user is None:
        return jsonify({"error": "Authenticated user no longer exists."}), 401

    inventory = db.session.scalars(
        db.select(Inventory)
        .where(Inventory.business_id == user.business_id)
        .order_by(Inventory.family)
    ).all()
    return jsonify({"inventory": [item.to_dict() for item in inventory]}), 200


@api_blueprint.get("/inventory/<int:inventory_id>")
@jwt_required()
def get_inventory(inventory_id):
    user = _authenticated_user()
    if user is None:
        return jsonify({"error": "Authenticated user no longer exists."}), 401

    inventory = db.session.scalar(
        db.select(Inventory).where(
            Inventory.id == inventory_id,
            Inventory.business_id == user.business_id,
        )
    )
    if inventory is None:
        return jsonify({"error": "Inventory not found."}), 404
    return jsonify({"inventory": inventory.to_dict()}), 200


@api_blueprint.post("/stock-intelligence")
@jwt_required()
def stock_intelligence():
    user = _authenticated_user()
    if user is None:
        return jsonify({"error": "Authenticated user no longer exists."}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON request body is required."}), 400

    forecast_run_id = data.get("forecast_run_id")
    if (
        isinstance(forecast_run_id, bool)
        or not isinstance(forecast_run_id, int)
        or forecast_run_id < 1
    ):
        return jsonify({"error": "forecast_run_id must be a positive integer."}), 400

    forecast_run = db.session.scalar(
        db.select(ForecastRun).where(
            ForecastRun.id == forecast_run_id,
            ForecastRun.business_id == user.business_id,
        )
    )
    if forecast_run is None:
        return jsonify({"error": "Forecast run not found."}), 404

    result = build_stock_intelligence(
        business_id=user.business_id,
        forecast_run=forecast_run,
        overstock_multiplier=current_app.config["STOCK_OVERSTOCK_MULTIPLIER"],
    )
    return jsonify({"stock_intelligence": result}), 200
