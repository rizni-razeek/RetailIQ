from app.extensions import db
from app.models import User


def registration_data(email="owner@example.com"):
    return {
        "business_name": "Corner Shop",
        "name": "Shop Owner",
        "email": email,
        "password": "securepass123",
    }


def register(client, email="owner@example.com"):
    return client.post("/api/auth/register", json=registration_data(email))


def login(client, email="owner@example.com", password="securepass123"):
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )


def test_successful_registration(client):
    response = register(client, "  OWNER@Example.COM ")

    assert response.status_code == 201
    user = response.get_json()["user"]
    assert user["email"] == "owner@example.com"
    assert user["business_name"] == "Corner Shop"
    assert "password_hash" not in user


def test_password_is_stored_as_a_hash(app, client):
    register(client)

    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == "owner@example.com"))
        assert user.password_hash != "securepass123"
        assert user.check_password("securepass123")


def test_duplicate_email_is_rejected_case_insensitively(client):
    assert register(client).status_code == 201

    response = register(client, "OWNER@EXAMPLE.COM")

    assert response.status_code == 409


def test_successful_login_returns_access_token(client):
    register(client)

    response = login(client, "OWNER@EXAMPLE.COM")

    assert response.status_code == 200
    assert response.get_json()["access_token"]


def test_invalid_login_does_not_reveal_account_existence(client):
    register(client)

    wrong_password = login(client, password="incorrect-password")
    unknown_email = login(client, email="unknown@example.com")

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.get_json() == unknown_email.get_json()


def test_current_user_rejects_unauthenticated_request(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_current_user_returns_authenticated_user_and_business(client):
    registered_user = register(client).get_json()["user"]
    token = login(client).get_json()["access_token"]

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.get_json()["user"] == registered_user


def test_client_cannot_change_tenant_identity_with_business_id(client):
    first_user = register(client, "first@example.com").get_json()["user"]
    second_user = register(client, "second@example.com").get_json()["user"]
    token = login(client, "first@example.com").get_json()["access_token"]

    response = client.get(
        f"/api/auth/me?business_id={second_user['business_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    authenticated_user = response.get_json()["user"]
    assert authenticated_user["business_id"] == first_user["business_id"]
    assert authenticated_user["business_id"] != second_user["business_id"]
