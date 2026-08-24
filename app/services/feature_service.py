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


def build_forecast_features(
    family: str,
    forecast_date: date,
    sales_history: list[float],
    future_onpromotion: float,
) -> pd.DataFrame:
    if len(sales_history) < 28:
        raise ValueError("At least 28 prior daily sales values are required.")

    feature_values = {
        "onpromotion": float(future_onpromotion),
        "year": forecast_date.year,
        "month": forecast_date.month,
        "day_of_month": forecast_date.day,
        "day_of_week": forecast_date.weekday(),
        "week_number": forecast_date.isocalendar().week,
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
