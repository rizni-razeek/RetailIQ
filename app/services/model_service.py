import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_model(model_path: str) -> Any | None:
    path = Path(model_path)

    if not path.is_file():
        logger.warning("Forecasting model is unavailable because the model file is missing.")
        return None

    try:
        model = joblib.load(path)
    except Exception:
        logger.exception("Forecasting model could not be loaded.")
        return None

    logger.info("Forecasting model loaded successfully.")
    return model


def get_model(model_path: str | Path) -> Any | None:
    return _load_model(str(Path(model_path).resolve()))


def get_model_status(model_path: str | Path) -> dict[str, bool | str | None]:
    model = get_model(model_path)
    return {
        "available": model is not None,
        "type": type(model).__name__ if model is not None else None,
    }
