from datetime import date, timedelta
from uuid import uuid4

import numpy as np

from app.extensions import db
from app.models import SalesRecord, Upload
from app.routes import anomalies as anomaly_routes
from app.services.feature_service import FEATURE_COLUMNS


class RecordingModel:
    feature_names_in_ = np.array(FEATURE_COLUMNS, dtype=object)

    def __init__(self, outputs=10.0, supported_families=("BEVERAGES",)):
        self.outputs = outputs
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
        index = len(self.frames) - 1
        value = self.outputs[index] if isinstance(self.outputs, list) else self.outputs
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


def create_historical_upload(business_id, family_sales):
    row_count = sum(len(sales_values) for sales_values in family_sales.values())
    upload = Upload(
        business_id=business_id,
        original_filename="history.csv",
        stored_filename=f"{uuid4().hex}.csv",
        row_count=row_count,
        status="completed",
    )
    db.session.add(upload)

    start_date = date(2024, 1, 1)
    for family, sales_values in family_sales.items():
        for offset, sales in enumerate(sales_values):
            db.session.add(
                SalesRecord(
                    business_id=business_id,
                    upload=upload,
                    date=start_date + timedelta(days=offset),
                    family=family,
                    sales=float(sales),
                    onpromotion=offset % 3,
                )
            )

    db.session.commit()
    return upload


def install_model(monkeypatch, model=None):
    model = model or RecordingModel()
    monkeypatch.setattr(anomaly_routes, "get_model", lambda _path: model)
    return model


def analyse(client, token, upload_id):
    return client.post(
        "/api/anomalies",
        json={"upload_id": upload_id},
        headers={"Authorization": f"Bearer {token}"},
    )


def anomaly_history():
    return [10.0] * 33


def test_unauthenticated_anomaly_request_is_rejected(client):
    response = client.post("/api/anomalies", json={"upload_id": 1})

    assert response.status_code == 401


def test_nonexistent_upload_is_rejected(client):
    _, token = register_and_login(client)

    response = analyse(client, token, 999)

    assert response.status_code == 404


def test_cross_tenant_upload_is_rejected(client):
    first_user, _ = register_and_login(client, "first@example.com", "First Shop")
    upload = create_historical_upload(
        first_user["business_id"], {"BEVERAGES": anomaly_history()}
    )
    _, second_token = register_and_login(client, "second@example.com", "Second Shop")

    response = analyse(client, second_token, upload.id)

    assert response.status_code == 404


def test_insufficient_history_is_reported_explicitly(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(
        user["business_id"], {"BEVERAGES": [10.0] * 28}
    )
    install_model(monkeypatch)

    response = analyse(client, token, upload.id)

    assert response.status_code == 422
    exclusion = response.get_json()["excluded_families"][0]
    assert exclusion["family"] == "BEVERAGES"
    assert "29 daily observations" in exclusion["reason"]


def test_unsupported_category_is_excluded_while_supported_is_analysed(
    client, monkeypatch
):
    user, token = register_and_login(client)
    upload = create_historical_upload(
        user["business_id"],
        {
            "BEVERAGES": anomaly_history(),
            "UNSUPPORTED CATEGORY": anomaly_history(),
        },
    )
    install_model(monkeypatch)

    response = analyse(client, token, upload.id)

    assert response.status_code == 200
    result = response.get_json()["anomaly_analysis"]
    assert result["family_summaries"][0]["family"] == "BEVERAGES"
    assert result["excluded_families"] == [
        {
            "family": "UNSUPPORTED CATEGORY",
            "reason": "Category is not supported by the trained forecasting model.",
        }
    ]


def test_only_unsupported_categories_return_clear_error(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(
        user["business_id"], {"UNSUPPORTED CATEGORY": anomaly_history()}
    )
    model = install_model(monkeypatch)

    response = analyse(client, token, upload.id)

    assert response.status_code == 422
    assert response.get_json()["excluded_families"][0]["family"] == (
        "UNSUPPORTED CATEGORY"
    )
    assert model.frames == []


def test_residual_z_score_and_positive_threshold_anomaly(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(
        user["business_id"], {"BEVERAGES": anomaly_history()}
    )
    install_model(monkeypatch, RecordingModel(outputs=[10, 10, 10, 10, 0]))

    response = analyse(client, token, upload.id)

    result = response.get_json()["anomaly_analysis"]
    anomaly = result["anomalies"][0]
    assert anomaly["actual_sales"] == 10
    assert anomaly["predicted_sales"] == 0
    assert anomaly["residual"] == 10
    assert anomaly["z_score"] == 2
    assert result["total_anomalies"] == 1
    assert result["anomaly_rate"] == 0.2


def test_values_below_threshold_are_not_anomalies(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(
        user["business_id"], {"BEVERAGES": anomaly_history()}
    )
    install_model(monkeypatch, RecordingModel(outputs=[11, 10.5, 10, 9.5, 9]))

    response = analyse(client, token, upload.id)

    result = response.get_json()["anomaly_analysis"]
    assert result["total_anomalies"] == 0
    assert result["anomalies"] == []


def test_negative_outlier_is_detected(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(
        user["business_id"], {"BEVERAGES": anomaly_history()}
    )
    install_model(monkeypatch, RecordingModel(outputs=[20, 10, 10, 10, 10]))

    response = analyse(client, token, upload.id)

    anomaly = response.get_json()["anomaly_analysis"]["anomalies"][0]
    assert anomaly["residual"] == -10
    assert anomaly["z_score"] == -2


def test_zero_residual_standard_deviation_is_handled_safely(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(
        user["business_id"], {"BEVERAGES": anomaly_history()}
    )
    install_model(monkeypatch, RecordingModel(outputs=10))

    response = analyse(client, token, upload.id)

    result = response.get_json()["anomaly_analysis"]
    summary = result["family_summaries"][0]
    assert result["total_anomalies"] == 0
    assert summary["residual_std"] == 0
    assert "zero" in summary["z_score_note"].lower()


def test_per_family_summary_is_correct(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(
        user["business_id"], {"BEVERAGES": anomaly_history()}
    )
    install_model(monkeypatch, RecordingModel(outputs=[10, 10, 10, 10, 0]))

    response = analyse(client, token, upload.id)

    summary = response.get_json()["anomaly_analysis"]["family_summaries"][0]
    assert summary["family"] == "BEVERAGES"
    assert summary["observations_analysed"] == 5
    assert summary["anomaly_count"] == 1
    assert summary["anomaly_rate"] == 0.2
    assert summary["residual_mean"] == 2
    assert summary["residual_std"] == 4


def test_response_is_scoped_to_requested_tenant_upload(client, monkeypatch):
    user, token = register_and_login(client)
    selected_upload = create_historical_upload(
        user["business_id"], {"BEVERAGES": anomaly_history()}
    )
    create_historical_upload(user["business_id"], {"DAIRY": anomaly_history()})
    install_model(monkeypatch, RecordingModel(outputs=[10, 10, 10, 10, 0]))

    response = analyse(client, token, selected_upload.id)

    result = response.get_json()["anomaly_analysis"]
    assert result["upload_id"] == selected_upload.id
    assert {item["family"] for item in result["family_summaries"]} == {"BEVERAGES"}
    assert {item["family"] for item in result["anomalies"]} == {"BEVERAGES"}


def test_response_exposes_configured_threshold_and_method(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(
        user["business_id"], {"BEVERAGES": anomaly_history()}
    )
    install_model(monkeypatch)

    response = analyse(client, token, upload.id)

    result = response.get_json()["anomaly_analysis"]
    assert result["z_score_threshold"] == 2.0
    assert result["method"] == "residual_z_score"
    assert result["total_observations_analysed"] == 5


def test_historical_predictions_use_actual_prior_sales_not_predictions(
    client, monkeypatch
):
    user, token = register_and_login(client)
    actual_sales = [float(value) for value in range(1, 34)]
    upload = create_historical_upload(
        user["business_id"], {"BEVERAGES": actual_sales}
    )
    model = install_model(monkeypatch, RecordingModel(outputs=1000))

    response = analyse(client, token, upload.id)

    assert response.status_code == 200
    assert model.frames[0].iloc[0]["rolling_mean_7"] == 25
    assert model.frames[1].iloc[0]["rolling_mean_7"] == 26
    assert model.frames[1].iloc[0]["rolling_mean_7"] != 1000


def test_model_receives_exact_forecasting_feature_columns(client, monkeypatch):
    user, token = register_and_login(client)
    upload = create_historical_upload(
        user["business_id"], {"BEVERAGES": anomaly_history()}
    )
    model = install_model(monkeypatch)

    response = analyse(client, token, upload.id)

    assert response.status_code == 200
    assert list(model.frames[0].columns) == list(FEATURE_COLUMNS)
    assert model.frames[0]["family"].dtype == object
    assert model.frames[0].iloc[0]["onpromotion"] == 1
