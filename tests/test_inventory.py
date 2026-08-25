from datetime import date
from uuid import uuid4

import pytest

from app.extensions import db
from app.models import Forecast, ForecastRun, Inventory, Upload


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


def save_inventory(client, token, family="BEVERAGES", current_stock=100):
    return client.post(
        "/api/inventory",
        json={"family": family, "current_stock": current_stock},
        headers={"Authorization": f"Bearer {token}"},
    )


def create_forecast_run(business_id, demands):
    upload = Upload(
        business_id=business_id,
        original_filename="history.csv",
        stored_filename=f"{uuid4().hex}.csv",
        row_count=28,
        status="completed",
    )
    forecast_run = ForecastRun(
        business_id=business_id,
        upload=upload,
        horizon_days=7,
        forecast_start_date=date(2024, 1, 29),
        forecast_end_date=date(2024, 2, 4),
        family_count=len(demands),
        future_onpromotion=0,
        excluded_families=[],
    )
    for family, demand in demands.items():
        forecast_run.forecasts.append(
            Forecast(
                business_id=business_id,
                family=family,
                forecast_date=date(2024, 1, 29),
                predicted_sales=float(demand),
            )
        )
    db.session.add(forecast_run)
    db.session.commit()
    return forecast_run


def get_stock_intelligence(client, token, forecast_run_id):
    return client.post(
        "/api/stock-intelligence",
        json={"forecast_run_id": forecast_run_id},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_unauthenticated_inventory_create_is_rejected(client):
    response = client.post(
        "/api/inventory",
        json={"family": "BEVERAGES", "current_stock": 100},
    )

    assert response.status_code == 401


def test_valid_inventory_create_works(client):
    user, token = register_and_login(client)

    response = save_inventory(client, token, " beverages ", 120000)

    assert response.status_code == 201
    inventory = response.get_json()["inventory"]
    assert inventory["family"] == "BEVERAGES"
    assert inventory["current_stock"] == 120000
    assert db.session.get(Inventory, inventory["id"]).business_id == user["business_id"]


def test_same_business_and_family_updates_instead_of_duplicate(client):
    _, token = register_and_login(client)
    first_id = save_inventory(client, token, "BEVERAGES", 100).get_json()["inventory"][
        "id"
    ]

    response = save_inventory(client, token, "beverages", 150)

    assert response.status_code == 200
    assert response.get_json()["inventory"]["id"] == first_id
    assert response.get_json()["inventory"]["current_stock"] == 150
    assert len(db.session.scalars(db.select(Inventory)).all()) == 1


def test_negative_stock_is_rejected(client):
    _, token = register_and_login(client)

    response = save_inventory(client, token, current_stock=-1)

    assert response.status_code == 400


@pytest.mark.parametrize("invalid_stock", ["many", None, True])
def test_invalid_non_numeric_stock_is_rejected(client, invalid_stock):
    _, token = register_and_login(client)

    response = save_inventory(client, token, current_stock=invalid_stock)

    assert response.status_code == 400


def test_inventory_list_is_tenant_safe(client):
    _, first_token = register_and_login(client, "first@example.com", "First Shop")
    save_inventory(client, first_token, "BEVERAGES", 100)
    _, second_token = register_and_login(client, "second@example.com", "Second Shop")
    save_inventory(client, second_token, "DAIRY", 200)

    response = client.get(
        "/api/inventory",
        headers={"Authorization": f"Bearer {first_token}"},
    )

    assert [item["family"] for item in response.get_json()["inventory"]] == [
        "BEVERAGES"
    ]


def test_inventory_detail_returns_tenant_owned_record(client):
    _, token = register_and_login(client)
    inventory_id = save_inventory(client, token).get_json()["inventory"]["id"]

    response = client.get(
        f"/api/inventory/{inventory_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.get_json()["inventory"]["id"] == inventory_id


def test_cross_tenant_inventory_access_is_rejected(client):
    _, first_token = register_and_login(client, "first@example.com", "First Shop")
    inventory_id = save_inventory(client, first_token).get_json()["inventory"]["id"]
    _, second_token = register_and_login(client, "second@example.com", "Second Shop")

    response = client.get(
        f"/api/inventory/{inventory_id}",
        headers={"Authorization": f"Bearer {second_token}"},
    )

    assert response.status_code == 404


def test_nonexistent_forecast_run_is_rejected(client):
    _, token = register_and_login(client)

    response = get_stock_intelligence(client, token, 999)

    assert response.status_code == 404


def test_cross_tenant_forecast_run_is_rejected(client):
    first_user, _ = register_and_login(client, "first@example.com", "First Shop")
    forecast_run = create_forecast_run(first_user["business_id"], {"BEVERAGES": 100})
    _, second_token = register_and_login(client, "second@example.com", "Second Shop")

    response = get_stock_intelligence(client, second_token, forecast_run.id)

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("current_stock", "expected_status"),
    [
        (99.0, "UNDERSTOCK"),
        (100.0, "SUFFICIENT"),
        (150.0, "SUFFICIENT"),
        (151.0, "OVERSTOCK"),
    ],
)
def test_stock_classification_boundaries(client, current_stock, expected_status):
    user, token = register_and_login(client)
    forecast_run = create_forecast_run(user["business_id"], {"BEVERAGES": 100})
    save_inventory(client, token, current_stock=current_stock)

    response = get_stock_intelligence(client, token, forecast_run.id)

    family = response.get_json()["stock_intelligence"]["families"][0]
    assert family["status"] == expected_status


def test_missing_inventory_is_explicit(client):
    user, token = register_and_login(client)
    forecast_run = create_forecast_run(user["business_id"], {"BEVERAGES": 100})

    response = get_stock_intelligence(client, token, forecast_run.id)

    family = response.get_json()["stock_intelligence"]["families"][0]
    assert family["status"] == "INVENTORY_REQUIRED"
    assert family["current_stock"] is None
    assert family["stock_difference"] is None
    assert family["coverage_ratio"] is None


@pytest.mark.parametrize(
    ("current_stock", "expected_status"),
    [(0.0, "SUFFICIENT"), (1.0, "OVERSTOCK")],
)
def test_zero_forecast_demand_is_handled(
    client, current_stock, expected_status
):
    user, token = register_and_login(client)
    forecast_run = create_forecast_run(user["business_id"], {"BEVERAGES": 0})
    save_inventory(client, token, current_stock=current_stock)

    response = get_stock_intelligence(client, token, forecast_run.id)

    family = response.get_json()["stock_intelligence"]["families"][0]
    assert family["status"] == expected_status
    assert family["coverage_ratio"] is None


def test_coverage_ratio_and_stock_difference_are_correct(client):
    user, token = register_and_login(client)
    forecast_run = create_forecast_run(user["business_id"], {"BEVERAGES": 100})
    save_inventory(client, token, current_stock=120)

    response = get_stock_intelligence(client, token, forecast_run.id)

    result = response.get_json()["stock_intelligence"]
    family = result["families"][0]
    assert family["coverage_ratio"] == 1.2
    assert family["stock_difference"] == 20
    assert result["overstock_multiplier"] == 1.5
