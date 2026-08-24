import os
from datetime import timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER_SETTING = Path(os.getenv("UPLOAD_FOLDER", "uploads"))
DEFAULT_UPLOAD_FOLDER = (
    UPLOAD_FOLDER_SETTING
    if UPLOAD_FOLDER_SETTING.is_absolute()
    else BASE_DIR / UPLOAD_FOLDER_SETTING
).resolve()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-key")
    JWT_SECRET_KEY = os.getenv(
        "JWT_SECRET_KEY", "development-only-jwt-key-change-before-production"
    )
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///retailiq.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10")) * 1024 * 1024
    UPLOAD_FOLDER = DEFAULT_UPLOAD_FOLDER
    MODEL_PATH = BASE_DIR / "model" / "retailiq_final_model.pkl"
    FORECAST_FUTURE_ONPROMOTION = 0.0
