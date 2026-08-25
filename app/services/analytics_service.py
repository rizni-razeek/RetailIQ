from sqlalchemy import func

from app.extensions import db
from app.models import Forecast, ForecastRun, Inventory, SalesRecord, Upload
from app.services.anomaly_service import NoEligibleFamiliesError, analyse_anomalies
from app.services.stock_service import (
    INVENTORY_REQUIRED,
    OVERSTOCK,
    SUFFICIENT,
    UNDERSTOCK,
    build_stock_intelligence,
)


STOCK_STATUSES = (UNDERSTOCK, SUFFICIENT, OVERSTOCK, INVENTORY_REQUIRED)


def _empty_anomaly_summary(z_threshold):
    return {
        "upload_id": None,
        "method": "residual_z_score",
        "z_score_threshold": float(z_threshold),
        "total_observations_analysed": 0,
        "total_anomalies": 0,
        "anomaly_rate": 0.0,
        "excluded_families": [],
        "family_summaries": [],
    }


def _latest_forecast_run(business_id, require_forecasts=False):
    query = db.select(ForecastRun).where(ForecastRun.business_id == business_id)
    if require_forecasts:
        query = query.where(ForecastRun.forecasts.any())
    return db.session.scalar(
        query.order_by(ForecastRun.generated_at.desc(), ForecastRun.id.desc())
    )


def build_sales_trends(business_id, upload_id=None, family=None):
    filters = [SalesRecord.business_id == business_id]
    if upload_id is not None:
        filters.append(SalesRecord.upload_id == upload_id)
    if family is not None:
        filters.append(SalesRecord.family == family)

    rows = db.session.execute(
        db.select(SalesRecord.date, func.sum(SalesRecord.sales))
        .where(*filters)
        .group_by(SalesRecord.date)
        .order_by(SalesRecord.date)
    ).all()
    data = [{"date": sales_date.isoformat(), "sales": float(sales)} for sales_date, sales in rows]

    return {
        "upload_id": upload_id,
        "family": family,
        "date_from": data[0]["date"] if data else None,
        "date_to": data[-1]["date"] if data else None,
        "total_sales": float(sum(item["sales"] for item in data)),
        "data": data,
    }


def build_category_summaries(business_id, upload_id=None):
    filters = [SalesRecord.business_id == business_id]
    if upload_id is not None:
        filters.append(SalesRecord.upload_id == upload_id)

    daily_sales = (
        db.select(
            SalesRecord.family.label("family"),
            SalesRecord.date.label("sales_date"),
            func.sum(SalesRecord.sales).label("daily_sales"),
        )
        .where(*filters)
        .group_by(SalesRecord.family, SalesRecord.date)
        .subquery()
    )
    rows = db.session.execute(
        db.select(
            daily_sales.c.family,
            func.sum(daily_sales.c.daily_sales).label("total_sales"),
            func.avg(daily_sales.c.daily_sales).label("average_daily_sales"),
            func.count().label("observation_count"),
            func.min(daily_sales.c.sales_date).label("date_from"),
            func.max(daily_sales.c.sales_date).label("date_to"),
        )
        .group_by(daily_sales.c.family)
        .order_by(func.sum(daily_sales.c.daily_sales).desc(), daily_sales.c.family)
    ).all()

    return {
        "upload_id": upload_id,
        "categories": [
            {
                "family": row.family,
                "total_sales": float(row.total_sales),
                "average_daily_sales": float(row.average_daily_sales),
                "observation_count": row.observation_count,
                "date_from": row.date_from.isoformat(),
                "date_to": row.date_to.isoformat(),
            }
            for row in rows
        ],
    }


def build_forecast_summary(business_id, forecast_run=None):
    forecast_run = forecast_run or _latest_forecast_run(business_id)
    if forecast_run is None:
        return {
            "forecast_run_id": None,
            "horizon": None,
            "forecast_start_date": None,
            "forecast_end_date": None,
            "families_forecast": 0,
            "total_predicted_demand": 0.0,
            "families": [],
        }

    rows = db.session.execute(
        db.select(
            Forecast.family,
            func.sum(Forecast.predicted_sales).label("total"),
            func.avg(Forecast.predicted_sales).label("average"),
            func.min(Forecast.predicted_sales).label("minimum"),
            func.max(Forecast.predicted_sales).label("maximum"),
        )
        .where(
            Forecast.business_id == business_id,
            Forecast.forecast_run_id == forecast_run.id,
        )
        .group_by(Forecast.family)
        .order_by(func.sum(Forecast.predicted_sales).desc(), Forecast.family)
    ).all()
    families = [
        {
            "family": row.family,
            "total_predicted_sales": float(row.total),
            "average_daily_predicted_sales": float(row.average),
            "minimum_daily_prediction": float(row.minimum),
            "maximum_daily_prediction": float(row.maximum),
        }
        for row in rows
    ]

    return {
        "forecast_run_id": forecast_run.id,
        "horizon": forecast_run.horizon_days,
        "forecast_start_date": forecast_run.forecast_start_date.isoformat(),
        "forecast_end_date": forecast_run.forecast_end_date.isoformat(),
        "families_forecast": forecast_run.family_count,
        "total_predicted_demand": float(
            sum(family["total_predicted_sales"] for family in families)
        ),
        "families": families,
    }


def build_stock_summary(business_id, overstock_multiplier, forecast_run=None):
    forecast_run = forecast_run or _latest_forecast_run(
        business_id, require_forecasts=True
    )
    status_counts = {status: 0 for status in STOCK_STATUSES}
    if forecast_run is None:
        return {
            "forecast_run_id": None,
            "horizon": None,
            "overstock_multiplier": float(overstock_multiplier),
            "status_counts": status_counts,
            "families": [],
        }

    intelligence = build_stock_intelligence(
        business_id,
        forecast_run,
        overstock_multiplier,
    )
    for family in intelligence["families"]:
        status_counts[family["status"]] += 1

    return {
        "forecast_run_id": forecast_run.id,
        "horizon": forecast_run.horizon_days,
        "overstock_multiplier": float(overstock_multiplier),
        "status_counts": status_counts,
        "families": intelligence["families"],
    }


def _summarize_anomaly_analysis(analysis):
    return {
        "upload_id": analysis["upload_id"],
        "method": analysis["method"],
        "z_score_threshold": analysis["z_score_threshold"],
        "total_observations_analysed": analysis["total_observations_analysed"],
        "total_anomalies": analysis["total_anomalies"],
        "anomaly_rate": analysis["anomaly_rate"],
        "excluded_families": analysis["excluded_families"],
        "family_summaries": [
            {
                "family": summary["family"],
                "observations_analysed": summary["observations_analysed"],
                "anomaly_count": summary["anomaly_count"],
                "anomaly_rate": summary["anomaly_rate"],
            }
            for summary in analysis["family_summaries"]
        ],
    }


def build_anomaly_summary(
    business_id,
    model,
    z_threshold,
    upload=None,
):
    if upload is not None:
        analysis = analyse_anomalies(
            business_id,
            upload.id,
            model,
            z_threshold,
        )
        return _summarize_anomaly_analysis(analysis)

    uploads = db.session.scalars(
        db.select(Upload)
        .where(Upload.business_id == business_id)
        .order_by(Upload.uploaded_at.desc(), Upload.id.desc())
    ).all()
    for candidate in uploads:
        try:
            analysis = analyse_anomalies(
                business_id,
                candidate.id,
                model,
                z_threshold,
            )
        except NoEligibleFamiliesError:
            continue
        return _summarize_anomaly_analysis(analysis)

    return _empty_anomaly_summary(z_threshold)


def build_overview(business_id, model, z_threshold, overstock_multiplier):
    sales_totals = db.session.execute(
        db.select(
            func.count(SalesRecord.id),
            func.sum(SalesRecord.sales),
            func.count(func.distinct(SalesRecord.family)),
        ).where(SalesRecord.business_id == business_id)
    ).one()
    latest_upload = db.session.scalar(
        db.select(Upload)
        .where(Upload.business_id == business_id)
        .order_by(Upload.uploaded_at.desc(), Upload.id.desc())
    )
    latest_forecast = _latest_forecast_run(business_id)
    stock_summary = build_stock_summary(business_id, overstock_multiplier)

    anomaly_summary = _empty_anomaly_summary(z_threshold)
    if latest_upload is not None and model is not None:
        anomaly_summary = build_anomaly_summary(business_id, model, z_threshold)

    return {
        "total_uploads": db.session.scalar(
            db.select(func.count(Upload.id)).where(Upload.business_id == business_id)
        ),
        "total_historical_sales_records": sales_totals[0],
        "total_historical_sales": float(sales_totals[1] or 0),
        "distinct_families": sales_totals[2],
        "latest_upload_id": latest_upload.id if latest_upload else None,
        "latest_upload_date": (
            latest_upload.uploaded_at.isoformat() if latest_upload else None
        ),
        "total_forecast_runs": db.session.scalar(
            db.select(func.count(ForecastRun.id)).where(
                ForecastRun.business_id == business_id
            )
        ),
        "latest_forecast_run_id": latest_forecast.id if latest_forecast else None,
        "inventory_category_count": db.session.scalar(
            db.select(func.count(Inventory.id)).where(
                Inventory.business_id == business_id
            )
        ),
        "stock_status_counts": stock_summary["status_counts"],
        "anomaly_summary": {
            "upload_id": anomaly_summary["upload_id"],
            "total_observations_analysed": anomaly_summary[
                "total_observations_analysed"
            ],
            "total_anomalies": anomaly_summary["total_anomalies"],
            "anomaly_rate": anomaly_summary["anomaly_rate"],
        },
    }
