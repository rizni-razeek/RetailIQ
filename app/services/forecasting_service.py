from collections import defaultdict
from datetime import timedelta

import numpy as np
from sqlalchemy import func

from app.extensions import db
from app.models import Forecast, ForecastRun, SalesRecord
from app.services.feature_service import (
    build_forecast_features,
    get_supported_model_families,
    validate_model_features,
)


MINIMUM_HISTORY_DAYS = 28


class ForecastingError(Exception):
    pass


class InsufficientHistoryError(ForecastingError):
    def __init__(self, excluded_families):
        super().__init__("No family has sufficient history for forecasting.")
        self.excluded_families = excluded_families


def _load_aggregated_history(business_id, upload_id):
    rows = db.session.execute(
        db.select(
            SalesRecord.date,
            SalesRecord.family,
            func.sum(SalesRecord.sales),
        )
        .where(
            SalesRecord.business_id == business_id,
            SalesRecord.upload_id == upload_id,
        )
        .group_by(SalesRecord.date, SalesRecord.family)
        .order_by(SalesRecord.family, SalesRecord.date)
    ).all()

    history_by_family = defaultdict(list)
    for sales_date, family, sales in rows:
        history_by_family[family].append((sales_date, float(sales)))
    return history_by_family


def _eligible_histories(history_by_family, supported_families):
    latest_date = max(
        sales_date
        for family_history in history_by_family.values()
        for sales_date, _sales in family_history
    )
    required_dates = {
        latest_date - timedelta(days=offset)
        for offset in range(MINIMUM_HISTORY_DAYS)
    }

    eligible = {}
    excluded = []
    for family, family_history in sorted(history_by_family.items()):
        if family not in supported_families:
            excluded.append(
                {
                    "family": family,
                    "reason": "Category is not supported by the trained forecasting model.",
                }
            )
            continue

        values_by_date = dict(family_history)
        available_required_dates = required_dates.intersection(values_by_date)
        if len(available_required_dates) < MINIMUM_HISTORY_DAYS:
            excluded.append(
                {
                    "family": family,
                    "reason": (
                        "At least 28 consecutive daily observations ending on the "
                        f"latest upload date are required; found {len(available_required_dates)}."
                    ),
                }
            )
            continue

        ordered_dates = sorted(values_by_date)
        eligible[family] = [values_by_date[sales_date] for sales_date in ordered_dates]

    return latest_date, eligible, excluded


def generate_forecast(
    business_id,
    upload_id,
    horizon,
    model,
    future_onpromotion=0.0,
):
    try:
        validate_model_features(model)
        supported_families = get_supported_model_families(model)
    except ValueError as error:
        raise ForecastingError(str(error)) from error
    history_by_family = _load_aggregated_history(business_id, upload_id)
    if not history_by_family:
        raise InsufficientHistoryError([])

    latest_date, eligible_histories, excluded_families = _eligible_histories(
        history_by_family, supported_families
    )
    if not eligible_histories:
        raise InsufficientHistoryError(excluded_families)

    forecast_start = latest_date + timedelta(days=1)
    forecast_end = latest_date + timedelta(days=horizon)
    forecast_run = ForecastRun(
        business_id=business_id,
        upload_id=upload_id,
        horizon_days=horizon,
        forecast_start_date=forecast_start,
        forecast_end_date=forecast_end,
        family_count=len(eligible_histories),
        future_onpromotion=float(future_onpromotion),
        excluded_families=excluded_families,
    )
    db.session.add(forecast_run)

    for family, historical_sales in eligible_histories.items():
        working_history = list(historical_sales)
        for day_offset in range(1, horizon + 1):
            forecast_date = latest_date + timedelta(days=day_offset)
            features = build_forecast_features(
                family,
                forecast_date,
                working_history,
                future_onpromotion,
            )
            try:
                prediction_values = np.asarray(model.predict(features)).reshape(-1)
            except Exception as error:
                raise ForecastingError(
                    "The forecasting model could not generate a prediction."
                ) from error
            if len(prediction_values) != 1 or not np.isfinite(prediction_values[0]):
                raise ForecastingError("The forecasting model returned an invalid prediction.")

            predicted_sales = max(0.0, float(prediction_values[0]))
            working_history.append(predicted_sales)
            forecast_run.forecasts.append(
                Forecast(
                    business_id=business_id,
                    family=family,
                    forecast_date=forecast_date,
                    predicted_sales=predicted_sales,
                )
            )

    return forecast_run


def serialize_forecast_run(forecast_run, include_predictions=False):
    result = {
        "id": forecast_run.id,
        "upload_id": forecast_run.upload_id,
        "horizon": forecast_run.horizon_days,
        "forecast_start_date": forecast_run.forecast_start_date.isoformat(),
        "forecast_end_date": forecast_run.forecast_end_date.isoformat(),
        "families_forecast": forecast_run.family_count,
        "excluded_families": forecast_run.excluded_families,
        "generated_at": forecast_run.generated_at.isoformat(),
        "assumptions": {
            "future_onpromotion": forecast_run.future_onpromotion,
            "method": "recursive",
        },
    }

    if include_predictions:
        forecasts_by_family = defaultdict(list)
        for forecast in forecast_run.forecasts:
            forecasts_by_family[forecast.family].append(forecast)

        result["families"] = [
            {
                "family": family,
                "total_predicted_sales": float(
                    sum(item.predicted_sales for item in family_forecasts)
                ),
                "predictions": [
                    {
                        "date": item.forecast_date.isoformat(),
                        "predicted_sales": item.predicted_sales,
                    }
                    for item in family_forecasts
                ],
            }
            for family, family_forecasts in sorted(forecasts_by_family.items())
        ]

    return result
