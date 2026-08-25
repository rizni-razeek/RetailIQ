from collections import defaultdict
from datetime import timedelta

import numpy as np
from sqlalchemy import func

from app.extensions import db
from app.models import SalesRecord
from app.services.feature_service import (
    build_model_features,
    get_supported_model_families,
    validate_model_features,
)


PRIOR_HISTORY_DAYS = 28
UNSUPPORTED_CATEGORY_REASON = (
    "Category is not supported by the trained forecasting model."
)


class AnomalyAnalysisError(Exception):
    pass


class NoEligibleFamiliesError(AnomalyAnalysisError):
    def __init__(self, excluded_families):
        super().__init__("No family has sufficient supported history for anomaly analysis.")
        self.excluded_families = excluded_families


def _load_aggregated_history(business_id, upload_id):
    rows = db.session.execute(
        db.select(
            SalesRecord.date,
            SalesRecord.family,
            func.sum(SalesRecord.sales),
            func.sum(SalesRecord.onpromotion),
        )
        .where(
            SalesRecord.business_id == business_id,
            SalesRecord.upload_id == upload_id,
        )
        .group_by(SalesRecord.date, SalesRecord.family)
        .order_by(SalesRecord.family, SalesRecord.date)
    ).all()

    history_by_family = defaultdict(list)
    for sales_date, family, sales, onpromotion in rows:
        history_by_family[family].append(
            (sales_date, float(sales), float(onpromotion or 0))
        )
    return history_by_family


def _predict_historical_observations(family, family_history, model):
    values_by_date = {
        sales_date: (sales, onpromotion)
        for sales_date, sales, onpromotion in family_history
    }
    observations = []

    for observation_date in sorted(values_by_date):
        prior_dates = [
            observation_date - timedelta(days=offset)
            for offset in range(PRIOR_HISTORY_DAYS, 0, -1)
        ]
        if not all(prior_date in values_by_date for prior_date in prior_dates):
            continue

        actual_sales, onpromotion = values_by_date[observation_date]
        sales_history = [values_by_date[prior_date][0] for prior_date in prior_dates]
        features = build_model_features(
            family,
            observation_date,
            sales_history,
            onpromotion,
        )
        try:
            prediction_values = np.asarray(model.predict(features)).reshape(-1)
        except Exception as error:
            raise AnomalyAnalysisError(
                "The forecasting model could not generate a historical prediction."
            ) from error
        if len(prediction_values) != 1 or not np.isfinite(prediction_values[0]):
            raise AnomalyAnalysisError(
                "The forecasting model returned an invalid historical prediction."
            )

        predicted_sales = float(prediction_values[0])
        observations.append(
            {
                "date": observation_date,
                "family": family,
                "actual_sales": actual_sales,
                "predicted_sales": predicted_sales,
                "residual": actual_sales - predicted_sales,
            }
        )

    return observations


def analyse_anomalies(business_id, upload_id, model, z_threshold):
    if not np.isfinite(z_threshold) or z_threshold <= 0:
        raise AnomalyAnalysisError("The anomaly Z-score threshold is invalid.")

    try:
        validate_model_features(model)
        supported_families = get_supported_model_families(model)
    except ValueError as error:
        raise AnomalyAnalysisError(str(error)) from error

    history_by_family = _load_aggregated_history(business_id, upload_id)
    excluded_families = []
    family_summaries = []
    anomalies = []
    total_observations = 0

    for family, family_history in sorted(history_by_family.items()):
        if family not in supported_families:
            excluded_families.append(
                {"family": family, "reason": UNSUPPORTED_CATEGORY_REASON}
            )
            continue

        observations = _predict_historical_observations(family, family_history, model)
        if not observations:
            excluded_families.append(
                {
                    "family": family,
                    "reason": (
                        "At least 29 daily observations with 28 consecutive prior "
                        "days are required."
                    ),
                }
            )
            continue

        residuals = np.array(
            [observation["residual"] for observation in observations], dtype=float
        )
        residual_mean = float(np.mean(residuals))
        residual_std = float(np.std(residuals, ddof=0))
        variation_is_zero = not np.isfinite(residual_std) or np.isclose(
            residual_std, 0.0, atol=1e-12
        )

        family_anomalies = []
        if not variation_is_zero:
            for observation in observations:
                z_score = (observation["residual"] - residual_mean) / residual_std
                if abs(z_score) >= z_threshold or np.isclose(
                    abs(z_score), z_threshold
                ):
                    family_anomalies.append(
                        {
                            "date": observation["date"].isoformat(),
                            "family": family,
                            "actual_sales": observation["actual_sales"],
                            "predicted_sales": observation["predicted_sales"],
                            "residual": observation["residual"],
                            "z_score": float(z_score),
                        }
                    )

        observation_count = len(observations)
        anomaly_count = len(family_anomalies)
        summary = {
            "family": family,
            "observations_analysed": observation_count,
            "anomaly_count": anomaly_count,
            "anomaly_rate": anomaly_count / observation_count,
            "residual_mean": residual_mean,
            "residual_std": residual_std,
        }
        if variation_is_zero:
            summary["z_score_note"] = (
                "Residual variation is zero; meaningful Z-scores could not be calculated."
            )

        family_summaries.append(summary)
        anomalies.extend(family_anomalies)
        total_observations += observation_count

    if not family_summaries:
        raise NoEligibleFamiliesError(excluded_families)

    total_anomalies = len(anomalies)
    return {
        "upload_id": upload_id,
        "z_score_threshold": float(z_threshold),
        "method": "residual_z_score",
        "total_observations_analysed": total_observations,
        "total_anomalies": total_anomalies,
        "anomaly_rate": total_anomalies / total_observations,
        "excluded_families": excluded_families,
        "family_summaries": family_summaries,
        "anomalies": anomalies,
    }
