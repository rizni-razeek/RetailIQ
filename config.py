import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-key")
    MODEL_PATH = BASE_DIR / "model" / "retailiq_final_model.pkl"
