from datetime import date

import pandas as pd


FEATURE_COLUMNS = (
    "onpromotion",
    "year",
    "month",
    "day_of_month",
    "day_of_week",
    "week_number",
    "sales_lag_7",
    "sales_lag_14",
    "sales_lag_28",
    "rolling_mean_7",
    "rolling_mean_28",
    "family",
)


def validate_model_features(model):
    model_columns = getattr(model, "feature_names_in_", None)
    if model_columns is None or tuple(model_columns) != FEATURE_COLUMNS:
        raise ValueError("The forecasting model feature schema is incompatible.")


def get_supported_model_families(model):
    preprocessing = getattr(model, "named_steps", {}).get("preprocessing")
    transformers = getattr(preprocessing, "transformers_", ())

    for _name, transformer, columns in transformers:
        transformer_columns = [columns] if isinstance(columns, str) else list(columns)
        if "family" not in transformer_columns:
            continue

        categories = getattr(transformer, "categories_", None)
        family_index = transformer_columns.index("family")
        if categories is not None and family_index < len(categories):
            return {str(category) for category in categories[family_index]}

    raise ValueError(
        "The forecasting model's supported family categories are unavailable."
    )


def build_model_features(
    family: str,
    observation_date: date,
    sales_history: list[float],
    onpromotion: float,
) -> pd.DataFrame:
    if len(sales_history) < 28:
        raise ValueError("At least 28 prior daily sales values are required.")

    feature_values = {
        "onpromotion": float(onpromotion),
        "year": observation_date.year,
        "month": observation_date.month,
        "day_of_month": observation_date.day,
        "day_of_week": observation_date.weekday(),
        "week_number": observation_date.isocalendar().week,
        "sales_lag_7": float(sales_history[-7]),
        "sales_lag_14": float(sales_history[-14]),
        "sales_lag_28": float(sales_history[-28]),
        "rolling_mean_7": float(sum(sales_history[-7:]) / 7),
        "rolling_mean_28": float(sum(sales_history[-28:]) / 28),
        "family": family,
    }

    features = pd.DataFrame([feature_values], columns=FEATURE_COLUMNS)
    integer_columns = ["year", "month", "day_of_month", "day_of_week", "week_number"]
    features[integer_columns] = features[integer_columns].astype("int64")
    features["family"] = features["family"].astype("object")
    return features


def build_forecast_features(
    family: str,
    forecast_date: date,
    sales_history: list[float],
    future_onpromotion: float,
) -> pd.DataFrame:
    return build_model_features(
        family,
        forecast_date,
        sales_history,
        future_onpromotion,
    )
