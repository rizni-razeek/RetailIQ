from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import numpy as np
import pytest

from app.extensions import db
from app.models import Forecast, ForecastRun, Inventory, SalesRecord, Upload
from app.routes import analytics as analytics_routes
from app.services.feature_service import FEATURE_COLUMNS


class AnalyticsModel:
    feature_names_in_ = np.array(FEATURE_COLUMNS, dtype=object)

    def __init__(self, outputs=(10.0,), supported_families=("BEVERAGES", "DAIRY")):
        self.outputs = list(outputs)
        self.calls = 0
        encoder = type(
            "FittedEncoder",
            (),
            {"categories_": [np.array(supported_families, dtype=object)]},
        )()
        preprocessing = type(
            "FittedPreprocessing",
            (),
            {"transformers_": [("categorical", encoder, ["family"])]},
        )()
        self.named_steps = {"preprocessing": preprocessing}

    def predict(self, _features):
        value = self.outputs[self.calls % len(self.outputs)]
        self.calls += 1
        return np.array([value], dtype=float)


@pytest.fixture
def analytics_model(monkeypatch):
    model = AnalyticsModel()
    monkeypatch.setattr(analytics_routes, "get_model", lambda _path: model)
    return model


def register_and_login(client, email="owner@example.com", business_name="Corner Shop"):
    registration = client.post(
        "/api/auth/register",
        json={
            "business_name": business_name,
            "name": "Shop Owner",
            "email": email,
            "password": "securepass123",
        },
    )
    token = client.post(
        "/api/auth/login",
        json={"email": email, "password": "securepass123"},
    ).get_json()["access_token"]
    return registration.get_json()["user"], token


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def create_upload(business_id, rows, uploaded_at=None):
    upload = Upload(
        business_id=business_id,
        original_filename="history.csv",
        stored_filename=f"{uuid4().hex}.csv",
        row_count=len(rows),
        status="completed",
        uploaded_at=uploaded_at or datetime.now(timezone.utc),
    )
    db.session.add(upload)
    for sales_date, family, sales in rows:
        db.session.add(
            SalesRecord(
                business_id=business_id,
                upload=upload,
                date=sales_date,
                family=family,
                sales=float(sales),
                onpromotion=0,
            )
        )
    db.session.commit()
    return upload


def daily_rows(family="BEVERAGES", count=33, sales=10):
    start = date(2024, 1, 1)
    return [(start + timedelta(days=offset), family, sales) for offset in range(count)]


def create_forecast_run(
    business_id,
    upload,
    family_predictions,
    generated_at=None,
):
    all_dates = [
        forecast_date
        for predictions in family_predictions.values()
        for forecast_date, _value in predictions
    ]
    forecast_run = ForecastRun(
        business_id=business_id,
        upload=upload,
        horizon_days=7,
        forecast_start_date=min(all_dates),
        forecast_end_date=max(all_dates),
        family_count=len(family_predictions),
        future_onpromotion=0,
        excluded_families=[],
        generated_at=generated_at or datetime.now(timezone.utc),
    )
    for family, predictions in family_predictions.items():
        for forecast_date, predicted_sales in predictions:
            forecast_run.forecasts.append(
                Forecast(
                    business_id=business_id,
                    family=family,
                    forecast_date=forecast_date,
                    predicted_sales=float(predicted_sales),
                )
            )
    db.session.add(forecast_run)
    db.session.commit()
    return forecast_run


@pytest.mark.parametrize(
    "path",
    [
        "/api/analytics/overview",
        "/api/analytics/sales-trends",
        "/api/analytics/categories",
        "/api/analytics/forecast-summary",
        "/api/analytics/stock-summary",
        "/api/analytics/anomaly-summary",
    ],
)
def test_analytics_endpoints_reject_unauthenticated_requests(client, path):
    assert client.get(path).status_code == 401


def test_overview_with_no_data_returns_safe_defaults(client, analytics_model):
    _, token = register_and_login(client)

    response = client.get("/api/analytics/overview", headers=auth_headers(token))

    assert response.status_code == 200
    overview = response.get_json()["overview"]
    assert overview["total_uploads"] == 0
    assert overview["total_historical_sales_records"] == 0
    assert overview["total_historical_sales"] == 0
    assert overview["distinct_families"] == 0
    assert overview["latest_upload_id"] is None
    assert overview["total_forecast_runs"] == 0
    assert overview["latest_forecast_run_id"] is None
    assert overview["inventory_category_count"] == 0
    assert sum(overview["stock_status_counts"].values()) == 0
    assert overview["anomaly_summary"]["upload_id"] is None


def test_overview_with_data_returns_correct_counts(client, analytics_model):
    user, token = register_and_login(client)
    upload = create_upload(user["business_id"], daily_rows())
    forecast_run = create_forecast_run(
        user["business_id"],
        upload,
        {"BEVERAGES": [(date(2024, 2, 3), 100)]},
    )
    db.session.add(
        Inventory(
            business_id=user["business_id"],
            family="BEVERAGES",
            current_stock=50,
        )
    )
    db.session.commit()

    overview = client.get(
        "/api/analytics/overview", headers=auth_headers(token)
    ).get_json()["overview"]

    assert overview["total_uploads"] == 1
    assert overview["total_historical_sales_records"] == 33
    assert overview["total_historical_sales"] == 330
    assert overview["distinct_families"] == 1
    assert overview["latest_upload_id"] == upload.id
    assert overview["total_forecast_runs"] == 1
    assert overview["latest_forecast_run_id"] == forecast_run.id
    assert overview["inventory_category_count"] == 1
    assert overview["stock_status_counts"]["UNDERSTOCK"] == 1
    assert overview["anomaly_summary"]["total_observations_analysed"] == 5


def test_sales_trend_aggregation_is_correct(client):
    user, token = register_and_login(client)
    upload = create_upload(
        user["business_id"],
        [
            (date(2024, 1, 1), "BEVERAGES", 10),
            (date(2024, 1, 1), "BEVERAGES", 5),
            (date(2024, 1, 1), "DAIRY", 7),
            (date(2024, 1, 2), "BEVERAGES", 3),
        ],
    )

    response = client.get(
        f"/api/analytics/sales-trends?upload_id={upload.id}",
        headers=auth_headers(token),
    )

    result = response.get_json()["sales_trends"]
    assert result["total_sales"] == 25
    assert result["date_from"] == "2024-01-01"
    assert result["date_to"] == "2024-01-02"
    assert result["data"] == [
        {"date": "2024-01-01", "sales": 22.0},
        {"date": "2024-01-02", "sales": 3.0},
    ]


def test_sales_trend_family_filter_works(client):
    user, token = register_and_login(client)
    upload = create_upload(
        user["business_id"],
        [
            (date(2024, 1, 1), "BEVERAGES", 10),
            (date(2024, 1, 1), "DAIRY", 7),
        ],
    )

    response = client.get(
        f"/api/analytics/sales-trends?upload_id={upload.id}&family=beverages",
        headers=auth_headers(token),
    )

    result = response.get_json()["sales_trends"]
    assert result["family"] == "BEVERAGES"
    assert result["total_sales"] == 10


def test_sales_trends_default_to_latest_upload_without_overlap(client):
    user, token = register_and_login(client)
    create_upload(
        user["business_id"],
        [(date(2024, 1, 1), "BEVERAGES", 100)],
        datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    latest = create_upload(
        user["business_id"],
        [(date(2024, 1, 1), "BEVERAGES", 25)],
        datetime(2024, 2, 1, tzinfo=timezone.utc),
    )

    response = client.get(
        "/api/analytics/sales-trends", headers=auth_headers(token)
    )

    result = response.get_json()["sales_trends"]
    assert result["upload_id"] == latest.id
    assert result["total_sales"] == 25
    assert result["data"] == [{"date": "2024-01-01", "sales": 25.0}]


def test_sales_trend_upload_is_tenant_safe(client):
    first_user, _ = register_and_login(client, "first@example.com", "First Shop")
    upload = create_upload(first_user["business_id"], daily_rows(count=1))
    _, second_token = register_and_login(client, "second@example.com", "Second Shop")

    response = client.get(
        f"/api/analytics/sales-trends?upload_id={upload.id}",
        headers=auth_headers(second_token),
    )

    assert response.status_code == 404


def test_category_summaries_aggregate_daily_values_correctly(client):
    user, token = register_and_login(client)
    upload = create_upload(
        user["business_id"],
        [
            (date(2024, 1, 1), "BEVERAGES", 10),
            (date(2024, 1, 1), "BEVERAGES", 5),
            (date(2024, 1, 2), "BEVERAGES", 5),
            (date(2024, 1, 1), "DAIRY", 30),
        ],
    )

    response = client.get(
        f"/api/analytics/categories?upload_id={upload.id}",
        headers=auth_headers(token),
    )

    categories = response.get_json()["category_summary"]["categories"]
    beverages = next(item for item in categories if item["family"] == "BEVERAGES")
    assert beverages["total_sales"] == 20
    assert beverages["average_daily_sales"] == 10
    assert beverages["observation_count"] == 2
    assert beverages["date_from"] == "2024-01-01"
    assert beverages["date_to"] == "2024-01-02"


def test_category_sorting_is_deterministic(client):
    user, token = register_and_login(client)
    create_upload(
        user["business_id"],
        [
            (date(2024, 1, 1), "DAIRY", 20),
            (date(2024, 1, 1), "BEVERAGES", 20),
            (date(2024, 1, 1), "AUTOMOTIVE", 30),
        ],
    )

    response = client.get(
        "/api/analytics/categories", headers=auth_headers(token)
    )

    families = [
        item["family"]
        for item in response.get_json()["category_summary"]["categories"]
    ]
    assert families == ["AUTOMOTIVE", "BEVERAGES", "DAIRY"]


def test_categories_default_to_latest_upload_without_overlap(client):
    user, token = register_and_login(client)
    create_upload(
        user["business_id"],
        [(date(2024, 1, 1), "BEVERAGES", 100)],
        datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    latest = create_upload(
        user["business_id"],
        [(date(2024, 1, 1), "DAIRY", 30)],
        datetime(2024, 2, 1, tzinfo=timezone.utc),
    )

    response = client.get(
        "/api/analytics/categories", headers=auth_headers(token)
    )

    result = response.get_json()["category_summary"]
    assert result["upload_id"] == latest.id
    assert [item["family"] for item in result["categories"]] == ["DAIRY"]
    assert result["categories"][0]["total_sales"] == 30


def test_explicit_older_upload_still_works_for_sales_and_categories(client):
    user, token = register_and_login(client)
    older = create_upload(
        user["business_id"],
        [(date(2024, 1, 1), "BEVERAGES", 100)],
        datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    create_upload(
        user["business_id"],
        [(date(2024, 1, 1), "BEVERAGES", 25)],
        datetime(2024, 2, 1, tzinfo=timezone.utc),
    )

    trends = client.get(
        f"/api/analytics/sales-trends?upload_id={older.id}",
        headers=auth_headers(token),
    ).get_json()["sales_trends"]
    categories = client.get(
        f"/api/analytics/categories?upload_id={older.id}",
        headers=auth_headers(token),
    ).get_json()["category_summary"]

    assert trends["upload_id"] == older.id
    assert trends["total_sales"] == 100
    assert categories["upload_id"] == older.id
    assert categories["categories"][0]["total_sales"] == 100


def test_forecast_summary_uses_requested_run(client):
    user, token = register_and_login(client)
    upload = create_upload(user["business_id"], daily_rows(count=1))
    first_run = create_forecast_run(
        user["business_id"],
        upload,
        {"BEVERAGES": [(date(2024, 2, 1), 10), (date(2024, 2, 2), 20)]},
        datetime(2024, 2, 1, tzinfo=timezone.utc),
    )
    create_forecast_run(
        user["business_id"],
        upload,
        {"BEVERAGES": [(date(2024, 3, 1), 100)]},
        datetime(2024, 3, 1, tzinfo=timezone.utc),
    )

    response = client.get(
        f"/api/analytics/forecast-summary?forecast_run_id={first_run.id}",
        headers=auth_headers(token),
    )

    summary = response.get_json()["forecast_summary"]
    assert summary["forecast_run_id"] == first_run.id
    assert summary["total_predicted_demand"] == 30
    assert summary["families"][0]["average_daily_predicted_sales"] == 15
    assert summary["families"][0]["minimum_daily_prediction"] == 10
    assert summary["families"][0]["maximum_daily_prediction"] == 20


def test_forecast_summary_defaults_to_latest_run(client):
    user, token = register_and_login(client)
    upload = create_upload(user["business_id"], daily_rows(count=1))
    create_forecast_run(
        user["business_id"],
        upload,
        {"BEVERAGES": [(date(2024, 2, 1), 10)]},
        datetime(2024, 2, 1, tzinfo=timezone.utc),
    )
    latest = create_forecast_run(
        user["business_id"],
        upload,
        {"BEVERAGES": [(date(2024, 3, 1), 20)]},
        datetime(2024, 3, 1, tzinfo=timezone.utc),
    )

    response = client.get(
        "/api/analytics/forecast-summary", headers=auth_headers(token)
    )

    assert response.get_json()["forecast_summary"]["forecast_run_id"] == latest.id


def test_forecast_summary_is_tenant_safe(client):
    first_user, _ = register_and_login(client, "first@example.com", "First Shop")
    upload = create_upload(first_user["business_id"], daily_rows(count=1))
    forecast_run = create_forecast_run(
        first_user["business_id"],
        upload,
        {"BEVERAGES": [(date(2024, 2, 1), 10)]},
    )
    _, second_token = register_and_login(client, "second@example.com", "Second Shop")

    response = client.get(
        f"/api/analytics/forecast-summary?forecast_run_id={forecast_run.id}",
        headers=auth_headers(second_token),
    )

    assert response.status_code == 404


def test_stock_summary_reuses_stock_classifications(client):
    user, token = register_and_login(client)
    upload = create_upload(user["business_id"], daily_rows(count=1))
    forecast_run = create_forecast_run(
        user["business_id"],
        upload,
        {
            "AUTOMOTIVE": [(date(2024, 2, 1), 100)],
            "BEVERAGES": [(date(2024, 2, 1), 100)],
            "DAIRY": [(date(2024, 2, 1), 100)],
            "DELI": [(date(2024, 2, 1), 100)],
        },
    )
    db.session.add_all(
        [
            Inventory(business_id=user["business_id"], family="AUTOMOTIVE", current_stock=50),
            Inventory(business_id=user["business_id"], family="BEVERAGES", current_stock=100),
            Inventory(business_id=user["business_id"], family="DAIRY", current_stock=151),
        ]
    )
    db.session.commit()

    response = client.get(
        f"/api/analytics/stock-summary?forecast_run_id={forecast_run.id}",
        headers=auth_headers(token),
    )

    summary = response.get_json()["stock_summary"]
    assert summary["status_counts"] == {
        "UNDERSTOCK": 1,
        "SUFFICIENT": 1,
        "OVERSTOCK": 1,
        "INVENTORY_REQUIRED": 1,
    }


def test_stock_summary_is_tenant_safe(client):
    first_user, _ = register_and_login(client, "first@example.com", "First Shop")
    upload = create_upload(first_user["business_id"], daily_rows(count=1))
    forecast_run = create_forecast_run(
        first_user["business_id"],
        upload,
        {"BEVERAGES": [(date(2024, 2, 1), 10)]},
    )
    _, second_token = register_and_login(client, "second@example.com", "Second Shop")

    response = client.get(
        f"/api/analytics/stock-summary?forecast_run_id={forecast_run.id}",
        headers=auth_headers(second_token),
    )

    assert response.status_code == 404


def test_anomaly_summary_is_correct(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_upload(user["business_id"], daily_rows())
    model = AnalyticsModel(outputs=(10, 10, 10, 10, 0))
    monkeypatch.setattr(analytics_routes, "get_model", lambda _path: model)

    response = client.get(
        f"/api/analytics/anomaly-summary?upload_id={upload.id}",
        headers=auth_headers(token),
    )

    summary = response.get_json()["anomaly_summary"]
    assert summary["upload_id"] == upload.id
    assert summary["method"] == "residual_z_score"
    assert summary["total_observations_analysed"] == 5
    assert summary["total_anomalies"] == 1
    assert summary["anomaly_rate"] == 0.2
    assert "anomalies" not in summary


def test_anomaly_summary_defaults_to_latest_suitable_upload(
    client, analytics_model
):
    user, token = register_and_login(client)
    eligible = create_upload(
        user["business_id"],
        daily_rows(),
        datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    create_upload(
        user["business_id"],
        daily_rows(count=10),
        datetime(2024, 2, 1, tzinfo=timezone.utc),
    )

    response = client.get(
        "/api/analytics/anomaly-summary", headers=auth_headers(token)
    )

    assert response.get_json()["anomaly_summary"]["upload_id"] == eligible.id


def test_anomaly_summary_is_tenant_safe(client, analytics_model):
    first_user, _ = register_and_login(client, "first@example.com", "First Shop")
    upload = create_upload(first_user["business_id"], daily_rows())
    _, second_token = register_and_login(client, "second@example.com", "Second Shop")

    response = client.get(
        f"/api/analytics/anomaly-summary?upload_id={upload.id}",
        headers=auth_headers(second_token),
    )

    assert response.status_code == 404


def test_missing_optional_data_returns_safe_empty_responses(client, analytics_model):
    _, token = register_and_login(client)

    trends = client.get(
        "/api/analytics/sales-trends", headers=auth_headers(token)
    ).get_json()["sales_trends"]
    categories = client.get(
        "/api/analytics/categories", headers=auth_headers(token)
    ).get_json()["category_summary"]
    forecast = client.get(
        "/api/analytics/forecast-summary", headers=auth_headers(token)
    ).get_json()["forecast_summary"]
    stock = client.get(
        "/api/analytics/stock-summary", headers=auth_headers(token)
    ).get_json()["stock_summary"]
    anomaly = client.get(
        "/api/analytics/anomaly-summary", headers=auth_headers(token)
    ).get_json()["anomaly_summary"]

    assert trends["data"] == []
    assert trends["upload_id"] is None
    assert trends["date_from"] is None
    assert categories["categories"] == []
    assert categories["upload_id"] is None
    assert forecast["forecast_run_id"] is None
    assert forecast["families"] == []
    assert stock["forecast_run_id"] is None
    assert sum(stock["status_counts"].values()) == 0
    assert anomaly["upload_id"] is None
    assert anomaly["family_summaries"] == []
