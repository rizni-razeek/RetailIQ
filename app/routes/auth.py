from flask import current_app, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions import db
from app.models import Business, User
from app.routes import api_blueprint


MINIMUM_PASSWORD_LENGTH = 8


def _json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _normalise_email(value):
    return value.strip().casefold() if isinstance(value, str) else ""


def _missing_fields(data, fields):
    return [
        field
        for field in fields
        if not isinstance(data.get(field), str) or not data[field].strip()
    ]


@api_blueprint.post("/auth/register")
def register():
    data = _json_body()
    if data is None:
        return jsonify({"error": "A JSON request body is required."}), 400

    required_fields = ("business_name", "name", "email", "password")
    missing = _missing_fields(data, required_fields)
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}."}), 400

    business_name = data["business_name"].strip()
    name = data["name"].strip()
    email = _normalise_email(data["email"])
    password = data["password"]

    if "@" not in email or email.startswith("@") or email.endswith("@"):
        return jsonify({"error": "A valid email address is required."}), 400

    if len(password) < MINIMUM_PASSWORD_LENGTH:
        return jsonify(
            {"error": f"Password must be at least {MINIMUM_PASSWORD_LENGTH} characters."}
        ), 400

    if db.session.scalar(db.select(User).where(User.email == email)) is not None:
        return jsonify({"error": "An account with this email already exists."}), 409

    try:
        business = Business(name=business_name)
        user = User(name=name, email=email, business=business)
        user.set_password(password)
        db.session.add(business)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "An account with this email already exists."}), 409
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Registration could not be completed.")
        return jsonify({"error": "Registration could not be completed."}), 500

    return jsonify({"message": "Registration successful.", "user": user.to_dict()}), 201


@api_blueprint.post("/auth/login")
def login():
    data = _json_body()
    if data is None:
        return jsonify({"error": "A JSON request body is required."}), 400

    missing = _missing_fields(data, ("email", "password"))
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}."}), 400

    email = _normalise_email(data["email"])
    user = db.session.scalar(db.select(User).where(User.email == email))

    if user is None or not user.check_password(data["password"]):
        return jsonify({"error": "Invalid email or password."}), 401

    access_token = create_access_token(identity=str(user.id))
    return jsonify({"access_token": access_token}), 200


@api_blueprint.get("/auth/me")
@jwt_required()
def current_user():
    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid authentication token."}), 401

    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "Authenticated user no longer exists."}), 401

    return jsonify({"user": user.to_dict()}), 200
