import io

from sqlalchemy import func

from app.extensions import db
from app.models import SalesRecord, Upload


VALID_CSV = b"date,family,sales,onpromotion\n2024-01-01,GROCERY,10.5,2\n2024-01-02,BEVERAGES,7,1\n"


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


def upload_csv(client, token, content=VALID_CSV, filename="sales.csv", **form_fields):
    data = {"file": (io.BytesIO(content), filename), **form_fields}
    return client.post(
        "/api/uploads",
        data=data,
        headers={"Authorization": f"Bearer {token}"},
        content_type="multipart/form-data",
    )


def test_valid_authenticated_csv_upload(client):
    user, token = register_and_login(client)

    response = upload_csv(
        client,
        token,
        filename="../../daily sales.csv",
        business_id="999999",
    )

    assert response.status_code == 201
    upload = response.get_json()["upload"]
    assert upload["original_filename"] == "daily_sales.csv"
    assert upload["row_count"] == 2
    assert upload["status"] == "completed"
    assert upload["summary"]["family_count"] == 2
    assert "stored_filename" not in upload
    assert "business_id" not in upload
    assert str(client.application.config["UPLOAD_FOLDER"]) not in response.get_data(
        as_text=True
    )

    records = db.session.scalars(db.select(SalesRecord)).all()
    assert {record.business_id for record in records} == {user["business_id"]}


def test_unauthenticated_upload_is_rejected(client):
    response = client.post(
        "/api/uploads",
        data={"file": (io.BytesIO(VALID_CSV), "sales.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 401


def test_missing_file_is_rejected(client):
    _, token = register_and_login(client)

    response = client.post(
        "/api/uploads",
        data={},
        headers={"Authorization": f"Bearer {token}"},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_invalid_extension_is_rejected(client):
    _, token = register_and_login(client)

    response = upload_csv(client, token, filename="sales.txt")

    assert response.status_code == 400


def test_missing_required_columns_are_rejected(client):
    _, token = register_and_login(client)

    response = upload_csv(client, token, b"date,family\n2024-01-01,GROCERY\n")

    assert response.status_code == 400
    assert "sales" in response.get_json()["error"]


def test_invalid_date_values_are_rejected(client):
    _, token = register_and_login(client)

    response = upload_csv(client, token, b"date,family,sales\nnot-a-date,GROCERY,5\n")

    assert response.status_code == 400
    assert "date" in response.get_json()["error"].lower()


def test_non_numeric_sales_are_rejected(client):
    _, token = register_and_login(client)

    response = upload_csv(client, token, b"date,family,sales\n2024-01-01,GROCERY,many\n")

    assert response.status_code == 400
    assert "numeric" in response.get_json()["error"]


def test_negative_sales_are_rejected(client):
    _, token = register_and_login(client)

    response = upload_csv(client, token, b"date,family,sales\n2024-01-01,GROCERY,-1\n")

    assert response.status_code == 400
    assert "negative" in response.get_json()["error"]


def test_missing_onpromotion_defaults_to_zero(client):
    _, token = register_and_login(client)

    response = upload_csv(client, token, b"date,family,sales\n2024-01-01,GROCERY,5\n")

    assert response.status_code == 201
    record = db.session.scalar(db.select(SalesRecord))
    assert record.onpromotion == 0


def test_upload_metadata_row_count_is_correct(client):
    _, token = register_and_login(client)

    upload_csv(client, token)

    upload = db.session.scalar(db.select(Upload))
    assert upload.row_count == 2


def test_sales_records_are_persisted_correctly(client):
    _, token = register_and_login(client)

    response = upload_csv(client, token)
    upload_id = response.get_json()["upload"]["id"]
    records = db.session.scalars(
        db.select(SalesRecord)
        .where(SalesRecord.upload_id == upload_id)
        .order_by(SalesRecord.date)
    ).all()

    assert len(records) == 2
    assert records[0].date.isoformat() == "2024-01-01"
    assert records[0].family == "GROCERY"
    assert records[0].sales == 10.5
    assert records[0].onpromotion == 2


def test_upload_list_returns_only_current_tenant_uploads(client):
    first_user, first_token = register_and_login(client, "first@example.com", "First Shop")
    upload_csv(client, first_token, filename="first.csv")
    _, second_token = register_and_login(client, "second@example.com", "Second Shop")
    upload_csv(client, second_token, filename="second.csv")

    response = client.get(
        "/api/uploads",
        headers={"Authorization": f"Bearer {first_token}"},
    )

    assert response.status_code == 200
    uploads = response.get_json()["uploads"]
    assert [upload["original_filename"] for upload in uploads] == ["first.csv"]
    stored_upload = db.session.scalar(
        db.select(Upload).where(Upload.original_filename == "first.csv")
    )
    assert stored_upload.business_id == first_user["business_id"]


def test_upload_detail_enforces_tenant_isolation(client):
    _, first_token = register_and_login(client, "first@example.com", "First Shop")
    first_upload_id = upload_csv(client, first_token).get_json()["upload"]["id"]
    _, second_token = register_and_login(client, "second@example.com", "Second Shop")

    response = client.get(
        f"/api/uploads/{first_upload_id}",
        headers={"Authorization": f"Bearer {second_token}"},
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "Upload not found."}


def test_invalid_upload_leaves_no_partial_database_rows(app, client):
    _, token = register_and_login(client)

    response = upload_csv(
        client,
        token,
        b"date,family,sales\n2024-01-01,GROCERY,5\n2024-01-02,BEVERAGES,-1\n",
    )

    assert response.status_code == 400
    assert db.session.scalar(db.select(func.count(Upload.id))) == 0
    assert db.session.scalar(db.select(func.count(SalesRecord.id))) == 0
    assert not list(app.config["UPLOAD_FOLDER"].glob("*"))


def test_empty_and_malformed_csv_files_are_rejected(client):
    _, token = register_and_login(client)

    empty_response = upload_csv(client, token, b"")
    malformed_response = upload_csv(
        client,
        token,
        b"date,family,sales\n2024-01-01,GROCERY,5,unexpected\n",
    )

    assert empty_response.status_code == 400
    assert malformed_response.status_code == 400


def test_blank_family_and_header_only_files_are_rejected(client):
    _, token = register_and_login(client)

    blank_family = upload_csv(
        client,
        token,
        b"date,family,sales\n2024-01-01, ,5\n",
    )
    header_only = upload_csv(client, token, b"date,family,sales\n")

    assert blank_family.status_code == 400
    assert "family" in blank_family.get_json()["error"].lower()
    assert header_only.status_code == 400


def test_invalid_onpromotion_values_are_rejected(client):
    _, token = register_and_login(client)

    non_numeric = upload_csv(
        client,
        token,
        b"date,family,sales,onpromotion\n2024-01-01,GROCERY,5,many\n",
    )
    negative = upload_csv(
        client,
        token,
        b"date,family,sales,onpromotion\n2024-01-01,GROCERY,5,-1\n",
    )

    assert non_numeric.status_code == 400
    assert negative.status_code == 400


def test_column_names_are_normalised(client):
    _, token = register_and_login(client)
    content = b" Date , FAMILY , Sales , ONPROMOTION \n2024-01-01,GROCERY,5,1\n"

    response = upload_csv(client, token, content)

    assert response.status_code == 201
