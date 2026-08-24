from datetime import date, timedelta
from uuid import uuid4

import numpy as np

from app.extensions import db
from app.models import Forecast, ForecastRun, SalesRecord, Upload
from app.routes import forecasts as forecast_routes
from app.services.feature_service import FEATURE_COLUMNS


class RecordingModel:
    feature_names_in_ = np.array(FEATURE_COLUMNS, dtype=object)

    def __init__(self, output=10.0, supported_families=("BEVERAGES", "GROCERY")):
        self.output = output
        self.frames = []
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

    def predict(self, features):
        self.frames.append(features.copy())
        prediction_index = len(self.frames) - 1
        value = (
            self.output(prediction_index, features)
            if callable(self.output)
            else self.output
        )
        return np.array([value], dtype=float)


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


def create_historical_upload(
    business_id,
    day_count=28,
    families=("GROCERY",),
    start_date=date(2024, 1, 1),
):
    upload = Upload(
        business_id=business_id,
        original_filename="history.csv",
        stored_filename=f"{uuid4().hex}.csv",
        row_count=day_count * len(families),
        status="completed",
    )
    db.session.add(upload)

    for family in families:
        for offset in range(day_count):
            db.session.add(
                SalesRecord(
                    business_id=business_id,
                    upload=upload,
                    date=start_date + timedelta(days=offset),
                    family=family,
                    sales=float(offset + 1),
                    onpromotion=0,
                )
            )

    db.session.commit()
    return upload


def install_model(monkeypatch, model=None):
    model = model or RecordingModel()
    monkeypatch.setattr(forecast_routes, "get_model", lambda _path: model)
    return model


def create_forecast(client, token, upload_id, horizon=7):
    return client.post(
        "/api/forecasts",
        json={"upload_id": upload_id, "horizon": horizon},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_unauthenticated_forecast_is_rejected(client):
    response = client.post("/api/forecasts", json={"upload_id": 1, "horizon": 7})

    assert response.status_code == 401


def test_invalid_horizon_is_rejected(client):
    _, token = register_and_login(client)

    response = create_forecast(client, token, upload_id=1, horizon=10)

    assert response.status_code == 400


def test_nonexistent_upload_is_rejected(client):
    _, token = register_and_login(client)

    response = create_forecast(client, token, upload_id=999)

    assert response.status_code == 404


def test_cross_tenant_upload_is_rejected(client):
    first_user, _ = register_and_login(client, "first@example.com", "First Shop")
    upload = create_historical_upload(first_user["business_id"])
    _, second_token = register_and_login(client, "second@example.com", "Second Shop")

    response = create_forecast(client, second_token, upload.id)

    assert response.status_code == 404


def test_insufficient_history_is_explained(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(user["business_id"], day_count=27)
    install_model(monkeypatch)

    response = create_forecast(client, token, upload.id)

    assert response.status_code == 422
    body = response.get_json()
    assert body["excluded_families"][0]["family"] == "GROCERY"
    assert "28 consecutive" in body["excluded_families"][0]["reason"]
    assert db.session.scalar(db.select(ForecastRun)) is None


def test_unsupported_category_is_excluded(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(
        user["business_id"], families=("GROCERY", "UNSUPPORTED CATEGORY")
    )
    model = install_model(monkeypatch)

    response = create_forecast(client, token, upload.id)

    assert response.status_code == 201
    forecast_run = response.get_json()["forecast_run"]
    assert forecast_run["excluded_families"] == [
        {
            "family": "UNSUPPORTED CATEGORY",
            "reason": "Category is not supported by the trained forecasting model.",
        }
    ]
    assert {frame.iloc[0]["family"] for frame in model.frames} == {"GROCERY"}


def test_supported_category_continues_to_forecast(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(user["business_id"], families=("GROCERY",))
    install_model(monkeypatch)

    response = create_forecast(client, token, upload.id)

    assert response.status_code == 201
    forecast_run = response.get_json()["forecast_run"]
    assert forecast_run["families_forecast"] == 1
    assert forecast_run["families"][0]["family"] == "GROCERY"
    assert len(forecast_run["families"][0]["predictions"]) == 7


def test_only_unsupported_categories_return_clear_error(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(
        user["business_id"], families=("UNSUPPORTED CATEGORY",)
    )
    model = install_model(monkeypatch)

    response = create_forecast(client, token, upload.id)

    assert response.status_code == 422
    assert response.get_json()["excluded_families"] == [
        {
            "family": "UNSUPPORTED CATEGORY",
            "reason": "Category is not supported by the trained forecasting model.",
        }
    ]
    assert model.frames == []
    assert db.session.scalar(db.select(ForecastRun)) is None


def test_supported_horizons_return_one_prediction_per_future_day(
    client, monkeypatch
):
    user, token = register_and_login(client)
    upload = create_historical_upload(user["business_id"])
    install_model(monkeypatch)

    for horizon in (7, 14, 30):
        response = create_forecast(client, token, upload.id, horizon)

        assert response.status_code == 201
        family = response.get_json()["forecast_run"]["families"][0]
        assert len(family["predictions"]) == horizon


def test_future_dates_start_after_latest_historical_date(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(user["business_id"])
    install_model(monkeypatch)

    response = create_forecast(client, token, upload.id)
    forecast_run = response.get_json()["forecast_run"]

    assert forecast_run["forecast_start_date"] == "2024-01-29"
    assert forecast_run["forecast_end_date"] == "2024-02-04"
    assert forecast_run["families"][0]["predictions"][0]["date"] == "2024-01-29"


def test_recursive_forecast_uses_earlier_predictions(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(user["business_id"])
    model = install_model(
        monkeypatch,
        RecordingModel(output=lambda index, _features: 100 + index),
    )

    response = create_forecast(client, token, upload.id, horizon=14)

    assert response.status_code == 201
    assert model.frames[7].iloc[0]["sales_lag_7"] == 100
    expected_second_rolling_mean = (23 + 24 + 25 + 26 + 27 + 28 + 100) / 7
    assert model.frames[1].iloc[0]["rolling_mean_7"] == expected_second_rolling_mean


def test_negative_predictions_are_clipped_to_zero(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(user["business_id"])
    install_model(monkeypatch, RecordingModel(output=-5))

    response = create_forecast(client, token, upload.id)

    predictions = response.get_json()["forecast_run"]["families"][0]["predictions"]
    assert {prediction["predicted_sales"] for prediction in predictions} == {0.0}
    assert db.session.scalar(db.select(Forecast)).predicted_sales == 0


def test_future_onpromotion_is_zero(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(user["business_id"])
    model = install_model(monkeypatch)

    response = create_forecast(client, token, upload.id)

    assert all(frame.iloc[0]["onpromotion"] == 0 for frame in model.frames)
    assert response.get_json()["forecast_run"]["assumptions"]["future_onpromotion"] == 0


def test_forecasts_are_persisted(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(
        user["business_id"], families=("BEVERAGES", "GROCERY")
    )
    install_model(monkeypatch)

    response = create_forecast(client, token, upload.id, horizon=7)
    forecast_run_id = response.get_json()["forecast_run"]["id"]

    forecast_run = db.session.get(ForecastRun, forecast_run_id)
    forecasts = db.session.scalars(
        db.select(Forecast).where(Forecast.forecast_run_id == forecast_run_id)
    ).all()
    assert forecast_run.business_id == user["business_id"]
    assert forecast_run.family_count == 2
    assert len(forecasts) == 14
    assert {forecast.business_id for forecast in forecasts} == {user["business_id"]}


def test_forecast_list_and_detail_are_tenant_safe(client, monkeypatch):
    first_user, first_token = register_and_login(
        client, "first@example.com", "First Shop"
    )
    upload = create_historical_upload(first_user["business_id"])
    install_model(monkeypatch)
    forecast_run_id = create_forecast(client, first_token, upload.id).get_json()[
        "forecast_run"
    ]["id"]
    _, second_token = register_and_login(client, "second@example.com", "Second Shop")

    first_list = client.get(
        "/api/forecasts",
        headers={"Authorization": f"Bearer {first_token}"},
    )
    second_list = client.get(
        "/api/forecasts",
        headers={"Authorization": f"Bearer {second_token}"},
    )
    cross_tenant_detail = client.get(
        f"/api/forecasts/{forecast_run_id}",
        headers={"Authorization": f"Bearer {second_token}"},
    )

    assert [run["id"] for run in first_list.get_json()["forecast_runs"]] == [
        forecast_run_id
    ]
    assert second_list.get_json()["forecast_runs"] == []
    assert cross_tenant_detail.status_code == 404


def test_model_receives_exact_training_feature_schema(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(user["business_id"])
    model = install_model(monkeypatch)

    response = create_forecast(client, token, upload.id)

    assert response.status_code == 201
    assert list(model.frames[0].columns) == list(FEATURE_COLUMNS)
    assert model.frames[0]["family"].dtype == object
    assert all(
        str(model.frames[0][column].dtype) == "int64"
        for column in ("year", "month", "day_of_month", "day_of_week", "week_number")
    )
