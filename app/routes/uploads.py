import logging
from pathlib import Path
from uuid import uuid4

from flask import current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import SalesRecord, Upload, User
from app.routes import api_blueprint
from app.services.csv_service import CsvValidationError, validate_sales_csv


logger = logging.getLogger(__name__)


def _authenticated_user():
    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return None
    return db.session.get(User, user_id)


def _store_validated_file(content, original_filename):
    upload_directory = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    upload_directory.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid4().hex}{Path(original_filename).suffix.casefold()}"
    destination = (upload_directory / stored_filename).resolve()
    if destination.parent != upload_directory:
        raise OSError("Invalid upload destination.")

    with destination.open("xb") as stored_file:
        stored_file.write(content)

    return stored_filename, destination


def _upload_summary(upload):
    summary = db.session.execute(
        db.select(
            func.min(SalesRecord.date),
            func.max(SalesRecord.date),
            func.count(func.distinct(SalesRecord.family)),
            func.sum(SalesRecord.sales),
        ).where(
            SalesRecord.upload_id == upload.id,
            SalesRecord.business_id == upload.business_id,
        )
    ).one()

    return {
        "date_from": summary[0].isoformat() if summary[0] else None,
        "date_to": summary[1].isoformat() if summary[1] else None,
        "family_count": summary[2],
        "total_sales": float(summary[3] or 0),
    }


@api_blueprint.post("/uploads")
@jwt_required()
def create_upload():
    user = _authenticated_user()
    if user is None:
        return jsonify({"error": "Authenticated user no longer exists."}), 401

    try:
        validated = validate_sales_csv(request.files.get("file"))
    except CsvValidationError as error:
        return jsonify({"error": str(error)}), 400

    stored_path = None
    try:
        stored_filename, stored_path = _store_validated_file(
            validated.content, validated.original_filename
        )
        upload = Upload(
            business_id=user.business_id,
            original_filename=validated.original_filename,
            stored_filename=stored_filename,
            row_count=len(validated.data),
            status="completed",
        )
        db.session.add(upload)

        for row in validated.data.itertuples(index=False):
            db.session.add(
                SalesRecord(
                    business_id=user.business_id,
                    upload=upload,
                    date=row.date,
                    family=row.family,
                    sales=float(row.sales),
                    onpromotion=float(row.onpromotion),
                )
            )

        db.session.commit()
    except (OSError, SQLAlchemyError):
        db.session.rollback()
        if stored_path is not None:
            try:
                stored_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Failed to remove an uncommitted upload file.")
        current_app.logger.exception("CSV upload could not be stored.")
        return jsonify({"error": "The CSV upload could not be stored."}), 500

    response = upload.to_dict()
    response["summary"] = _upload_summary(upload)
    return jsonify({"upload": response}), 201


@api_blueprint.get("/uploads")
@jwt_required()
def list_uploads():
    user = _authenticated_user()
    if user is None:
        return jsonify({"error": "Authenticated user no longer exists."}), 401

    uploads = db.session.scalars(
        db.select(Upload)
        .where(Upload.business_id == user.business_id)
        .order_by(Upload.uploaded_at.desc(), Upload.id.desc())
    ).all()

    return jsonify({"uploads": [upload.to_dict() for upload in uploads]}), 200


@api_blueprint.get("/uploads/<int:upload_id>")
@jwt_required()
def get_upload(upload_id):
    user = _authenticated_user()
    if user is None:
        return jsonify({"error": "Authenticated user no longer exists."}), 401

    upload = db.session.scalar(
        db.select(Upload).where(
            Upload.id == upload_id,
            Upload.business_id == user.business_id,
        )
    )
    if upload is None:
        return jsonify({"error": "Upload not found."}), 404

    response = upload.to_dict()
    response["summary"] = _upload_summary(upload)
    return jsonify({"upload": response}), 200
