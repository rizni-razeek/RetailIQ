import os
from datetime import timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEVELOPMENT_SECRET_KEY = "development-only-key"
DEVELOPMENT_JWT_SECRET_KEY = "development-only-jwt-key-change-before-production"


def _configured_path(variable_name, default):
    configured_path = Path(os.getenv(variable_name, default))
    if not configured_path.is_absolute():
        configured_path = BASE_DIR / configured_path
    return configured_path.resolve()


class Config:
    APP_ENV = os.getenv(
        "APP_ENV", os.getenv("FLASK_ENV", "development")
    ).strip().lower()
    SECRET_KEY = os.getenv("SECRET_KEY", DEVELOPMENT_SECRET_KEY)
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", DEVELOPMENT_JWT_SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    DATABASE_URL = os.getenv("DATABASE_URL")
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or "sqlite:///retailiq.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10")) * 1024 * 1024
    UPLOAD_FOLDER = _configured_path("UPLOAD_FOLDER", "uploads")
    MODEL_PATH = _configured_path(
        "MODEL_PATH", "model/retailiq_final_model.pkl"
    )
    HF_MODEL_REPO = os.getenv("HF_MODEL_REPO", "").strip()
    HF_MODEL_FILENAME = os.getenv("HF_MODEL_FILENAME", "").strip()
    HF_TOKEN = os.getenv("HF_TOKEN", "").strip()
    FORECAST_FUTURE_ONPROMOTION = 0.0
    STOCK_OVERSTOCK_MULTIPLIER = float(
        os.getenv("STOCK_OVERSTOCK_MULTIPLIER", "1.5")
    )
    ANOMALY_Z_THRESHOLD = float(os.getenv("ANOMALY_Z_THRESHOLD", "2.0"))


def validate_production_config(app):
    app_environment = str(app.config.get("APP_ENV", "development")).strip().lower()
    app.config["APP_ENV"] = app_environment
    if app_environment != "production":
        return

    def insecure_secret(value, development_value):
        return (
            not value
            or value == development_value
            or str(value).startswith("replace-with-")
        )

    missing = []
    if not app.config.get("DATABASE_URL"):
        missing.append("DATABASE_URL")
    if insecure_secret(app.config.get("SECRET_KEY"), DEVELOPMENT_SECRET_KEY):
        missing.append("SECRET_KEY")
    if insecure_secret(
        app.config.get("JWT_SECRET_KEY"), DEVELOPMENT_JWT_SECRET_KEY
    ):
        missing.append("JWT_SECRET_KEY")

    if missing:
        names = ", ".join(missing)
        raise RuntimeError(f"Missing required production configuration: {names}")

    app.config["DEBUG"] = False
