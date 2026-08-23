import pytest

from app import create_app
from app.extensions import db


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "JWT_SECRET_KEY": "test-jwt-secret-that-is-at-least-32-bytes-long",
            "UPLOAD_FOLDER": tmp_path / "uploads",
            "MAX_CONTENT_LENGTH": 1024 * 1024,
        }
    )

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
