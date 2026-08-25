import io
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models import Forecast, ForecastRun, Inventory, SalesRecord, Upload
from app.routes import analytics as analytics_routes
from app.routes import anomalies as anomaly_routes
from app.routes import forecasts as forecast_routes
from app.services.feature_service import (
    FEATURE_COLUMNS,
    get_supported_model_families,
)
from app.services.model_service import get_model
from config import Config


class LightweightCompatibleModel:
    feature_names_in_ = np.array(FEATURE_COLUMNS, dtype=object)

    def __init__(self, prediction=10.0, fail_after=None):
        self.prediction = prediction
        self.fail_after = fail_after
        self.calls = 0
        self.frames = []
        encoder = type(
            "FittedEncoder",
            (),
            {"categories_": [np.array(["BEVERAGES"], dtype=object)]},
        )()
        preprocessing = type(
            "FittedPreprocessing",
            (),
            {"transformers_": [("categorical", encoder, ["family"])]},
        )()
        self.named_steps = {"preprocessing": preprocessing}

    def predict(self, features):
        if self.fail_after is not None and self.calls >= self.fail_after:
            raise RuntimeError("Injected model failure")
        self.frames.append(features.copy())
        self.calls += 1
        return np.array([self.prediction], dtype=float)


def install_model(monkeypatch, model):
    monkeypatch.setattr(forecast_routes, "get_model", lambda _path: model)
    monkeypatch.setattr(anomaly_routes, "get_model", lambda _path: model)
    monkeypatch.setattr(analytics_routes, "get_model", lambda _path: model)


def register_and_login(client, email, business_name):
    registration = client.post(
        "/api/auth/register",
        json={
            "business_name": business_name,
            "name": "Shop Owner",
            "email": email,
            "password": "securepass123",
        },
    )
    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "securepass123"},
    )
    return registration.get_json()["user"], login.get_json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def historical_csv(day_count=33, extra_columns=False):
    header = "date,family,sales,onpromotion"
    if extra_columns:
        header += ",store_note"
    lines = [header]
    for day_offset in range(day_count):
        sales_date = (date(2024, 1, 1) + timedelta(days=day_offset)).isoformat()
        line = f"{sales_date},BEVERAGES,10,0"
        if extra_columns:
            line += ",ignored"
        lines.append(line)
    return ("\n".join(lines) + "\n").encode()


def upload_csv(client, token, content=None, filename="history.csv"):
    return client.post(
        "/api/uploads",
        data={"file": (io.BytesIO(content or historical_csv()), filename)},
        headers=auth_headers(token),
        content_type="multipart/form-data",
    )


def test_complete_authenticated_business_workflow(client, monkeypatch):
    model = LightweightCompatibleModel(prediction=10)
    install_model(monkeypatch, model)
    user, token = register_and_login(client, "owner@example.com", "Corner Shop")

    upload_response = upload_csv(client, token)
    assert upload_response.status_code == 201
    upload = upload_response.get_json()["upload"]
    upload_id = upload["id"]
    assert upload["row_count"] == 33
    assert db.session.get(Upload, upload_id).business_id == user["business_id"]
    assert len(
        db.session.scalars(
            db.select(SalesRecord).where(SalesRecord.upload_id == upload_id)
        ).all()
    ) == 33

    forecast_response = client.post(
        "/api/forecasts",
        json={"upload_id": upload_id, "horizon": 7},
        headers=auth_headers(token),
    )
    assert forecast_response.status_code == 201
    forecast_run = forecast_response.get_json()["forecast_run"]
    forecast_run_id = forecast_run["id"]
    assert len(forecast_run["families"][0]["predictions"]) == 7
    assert db.session.get(ForecastRun, forecast_run_id).business_id == user["business_id"]
    assert len(
        db.session.scalars(
            db.select(Forecast).where(Forecast.forecast_run_id == forecast_run_id)
        ).all()
    ) == 7

    inventory_create = client.post(
        "/api/inventory",
        json={"family": " beverages ", "current_stock": 75},
        headers=auth_headers(token),
    )
    inventory_id = inventory_create.get_json()["inventory"]["id"]
    inventory_update = client.post(
        "/api/inventory",
        json={"family": "BEVERAGES", "current_stock": 80},
        headers=auth_headers(token),
    )
    assert inventory_create.status_code == 201
    assert inventory_update.status_code == 200
    assert inventory_update.get_json()["inventory"]["id"] == inventory_id
    assert db.session.get(Inventory, inventory_id).current_stock == 80

    stock = client.post(
        "/api/stock-intelligence",
        json={"forecast_run_id": forecast_run_id},
        headers=auth_headers(token),
    ).get_json()["stock_intelligence"]
    assert stock["families"][0]["forecasted_demand"] == 70
    assert stock["families"][0]["status"] == "SUFFICIENT"

    anomaly = client.post(
        "/api/anomalies",
        json={"upload_id": upload_id},
        headers=auth_headers(token),
    ).get_json()["anomaly_analysis"]
    assert anomaly["total_observations_analysed"] == 5
    assert anomaly["total_anomalies"] == 0

    overview = client.get(
        "/api/analytics/overview", headers=auth_headers(token)
    ).get_json()["overview"]
    assert overview["latest_upload_id"] == upload_id
    assert overview["latest_forecast_run_id"] == forecast_run_id
    assert overview["inventory_category_count"] == 1
    assert overview["stock_status_counts"]["SUFFICIENT"] == 1

    forecast_summary = client.get(
        "/api/analytics/forecast-summary", headers=auth_headers(token)
    ).get_json()["forecast_summary"]
    assert forecast_summary["forecast_run_id"] == forecast_run_id
    assert forecast_summary["total_predicted_demand"] == 70

    stock_summary = client.get(
        "/api/analytics/stock-summary", headers=auth_headers(token)
    ).get_json()["stock_summary"]
    assert stock_summary["forecast_run_id"] == forecast_run_id
    assert stock_summary["status_counts"]["SUFFICIENT"] == 1

    anomaly_summary = client.get(
        "/api/analytics/anomaly-summary", headers=auth_headers(token)
    ).get_json()["anomaly_summary"]
    assert anomaly_summary["upload_id"] == upload_id
    assert anomaly_summary["total_observations_analysed"] == 5
    assert {record.business_id for record in db.session.scalars(db.select(Forecast))} == {
        user["business_id"]
    }


def test_complete_cross_tenant_denial_chain(client, monkeypatch):
    install_model(monkeypatch, LightweightCompatibleModel(prediction=10))
    first_user, first_token = register_and_login(
        client, "first@example.com", "First Shop"
    )
    second_user, second_token = register_and_login(
        client, "second@example.com", "Second Shop"
    )
    second_upload_id = upload_csv(client, second_token).get_json()["upload"]["id"]
    second_forecast_id = client.post(
        "/api/forecasts",
        json={"upload_id": second_upload_id, "horizon": 7},
        headers=auth_headers(second_token),
    ).get_json()["forecast_run"]["id"]
    second_inventory_id = client.post(
        "/api/inventory",
        json={"family": "BEVERAGES", "current_stock": 80},
        headers=auth_headers(second_token),
    ).get_json()["inventory"]["id"]

    denied_requests = [
        client.get(f"/api/uploads/{second_upload_id}", headers=auth_headers(first_token)),
        client.post(
            "/api/forecasts",
            json={"upload_id": second_upload_id, "horizon": 7},
            headers=auth_headers(first_token),
        ),
        client.get(
            f"/api/forecasts/{second_forecast_id}", headers=auth_headers(first_token)
        ),
        client.get(
            f"/api/inventory/{second_inventory_id}", headers=auth_headers(first_token)
        ),
        client.post(
            "/api/stock-intelligence",
            json={"forecast_run_id": second_forecast_id},
            headers=auth_headers(first_token),
        ),
        client.post(
            "/api/anomalies",
            json={"upload_id": second_upload_id},
            headers=auth_headers(first_token),
        ),
        client.get(
            f"/api/analytics/sales-trends?upload_id={second_upload_id}",
            headers=auth_headers(first_token),
        ),
        client.get(
            f"/api/analytics/forecast-summary?forecast_run_id={second_forecast_id}",
            headers=auth_headers(first_token),
        ),
        client.get(
            f"/api/analytics/stock-summary?forecast_run_id={second_forecast_id}",
            headers=auth_headers(first_token),
        ),
        client.get(
            f"/api/analytics/anomaly-summary?upload_id={second_upload_id}",
            headers=auth_headers(first_token),
        ),
    ]
    assert {response.status_code for response in denied_requests} == {404}
    assert all("error" in response.get_json() for response in denied_requests)

    first_overview = client.get(
        "/api/analytics/overview", headers=auth_headers(first_token)
    ).get_json()["overview"]
    assert first_overview["total_uploads"] == 0
    assert first_overview["total_historical_sales_records"] == 0
    assert first_overview["total_forecast_runs"] == 0
    assert first_overview["inventory_category_count"] == 0
    assert db.session.get(Upload, second_upload_id).business_id == second_user["business_id"]
    assert first_user["business_id"] != second_user["business_id"]


@pytest.mark.parametrize("endpoint", ["/api/auth/register", "/api/auth/login"])
def test_authentication_rejects_malformed_json(client, endpoint):
    response = client.post(endpoint, data="{", content_type="application/json")

    assert response.status_code == 400
    assert "error" in response.get_json()


@pytest.mark.parametrize(
    ("endpoint", "payload", "missing_field"),
    [
        (
            "/api/auth/register",
            {"business_name": "Shop", "name": "Owner", "email": "a@example.com"},
            "password",
        ),
        ("/api/auth/login", {"email": "a@example.com"}, "password"),
    ],
)
def test_authentication_reports_missing_required_fields(
    client, endpoint, payload, missing_field
):
    response = client.post(endpoint, json=payload)

    assert response.status_code == 400
    assert missing_field in response.get_json()["error"]


def test_invalid_and_expired_jwts_return_structured_json(app, client):
    invalid = client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
    )
    with app.app_context():
        expired_token = create_access_token(
            identity="1", expires_delta=timedelta(seconds=-1)
        )
    expired = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert invalid.status_code == 422
    assert expired.status_code == 401
    assert "msg" in invalid.get_json()
    assert "msg" in expired.get_json()


def test_upload_extra_columns_are_ignored_and_duplicates_aggregate(client):
    _, token = register_and_login(client, "owner@example.com", "Corner Shop")
    content = (
        b"date,family,sales,onpromotion,store_note\n"
        b"2024-01-01,BEVERAGES,10,1,ignored\n"
        b"2024-01-01,BEVERAGES,5,2,ignored-too\n"
    )

    upload = upload_csv(client, token, content).get_json()["upload"]
    trend = client.get(
        f"/api/analytics/sales-trends?upload_id={upload['id']}",
        headers=auth_headers(token),
    ).get_json()["sales_trends"]

    records = db.session.scalars(
        db.select(SalesRecord).where(SalesRecord.upload_id == upload["id"])
    ).all()
    assert len(records) == 2
    assert trend["data"] == [{"date": "2024-01-01", "sales": 15.0}]


def test_upload_size_limit_returns_json_without_persistence(app, client):
    _, token = register_and_login(client, "owner@example.com", "Corner Shop")
    app.config["MAX_CONTENT_LENGTH"] = 128

    response = upload_csv(client, token, b"x" * 512)

    assert response.status_code == 413
    assert response.get_json() == {"error": "The uploaded file is too large."}
    assert db.session.scalar(db.select(Upload)) is None


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"upload_id": "1", "horizon": 7},
        {"upload_id": 1, "horizon": "7"},
    ],
)
def test_forecast_rejects_malformed_bodies_and_types(client, payload):
    _, token = register_and_login(client, "owner@example.com", "Corner Shop")
    if payload is None:
        response = client.post(
            "/api/forecasts",
            data="{",
            content_type="application/json",
            headers=auth_headers(token),
        )
    else:
        response = client.post(
            "/api/forecasts", json=payload, headers=auth_headers(token)
        )

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_failed_forecast_rolls_back_all_forecast_rows(client, monkeypatch):
    model = LightweightCompatibleModel(prediction=10, fail_after=1)
    install_model(monkeypatch, model)
    _, token = register_and_login(client, "owner@example.com", "Corner Shop")
    upload_id = upload_csv(client, token).get_json()["upload"]["id"]

    response = client.post(
        "/api/forecasts",
        json={"upload_id": upload_id, "horizon": 7},
        headers=auth_headers(token),
    )

    assert response.status_code == 503
    assert "error" in response.get_json()
    assert db.session.scalar(db.select(ForecastRun)) is None
    assert db.session.scalar(db.select(Forecast)) is None


def test_forecast_list_and_detail_remain_consistent(client, monkeypatch):
    install_model(monkeypatch, LightweightCompatibleModel(prediction=10))
    _, token = register_and_login(client, "owner@example.com", "Corner Shop")
    upload_id = upload_csv(client, token).get_json()["upload"]["id"]
    created = client.post(
        "/api/forecasts",
        json={"upload_id": upload_id, "horizon": 7},
        headers=auth_headers(token),
    ).get_json()["forecast_run"]

    listed = client.get("/api/forecasts", headers=auth_headers(token)).get_json()[
        "forecast_runs"
    ][0]
    detail = client.get(
        f"/api/forecasts/{created['id']}", headers=auth_headers(token)
    ).get_json()["forecast_run"]

    for field in (
        "id",
        "upload_id",
        "horizon",
        "forecast_start_date",
        "forecast_end_date",
        "families_forecast",
    ):
        assert listed[field] == detail[field] == created[field]
    assert len(detail["families"][0]["predictions"]) == 7


@pytest.mark.parametrize("endpoint", ["/api/anomalies", "/api/stock-intelligence"])
def test_analysis_endpoints_reject_malformed_json(client, endpoint):
    _, token = register_and_login(client, "owner@example.com", "Corner Shop")

    response = client.post(
        endpoint,
        data="{",
        content_type="application/json",
        headers=auth_headers(token),
    )

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_real_model_exposes_expected_feature_schema_and_categories():
    model_path = Path(Config.MODEL_PATH)
    if not model_path.is_file():
        pytest.skip("The Git-ignored trained model artifact is not available.")

    model = get_model(model_path)

    assert model is not None
    assert tuple(model.feature_names_in_) == FEATURE_COLUMNS
    assert "BEVERAGES" in get_supported_model_families(model)
