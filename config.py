import os
from datetime import timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-key")
    JWT_SECRET_KEY = os.getenv(
        "JWT_SECRET_KEY", "development-only-jwt-key-change-before-production"
    )
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///retailiq.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MODEL_PATH = BASE_DIR / "model" / "retailiq_final_model.pkl"
