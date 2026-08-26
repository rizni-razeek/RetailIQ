import importlib

import pytest

import config as config_module
from app import create_app


def test_database_defaults_to_sqlite_when_url_is_absent(monkeypatch):
    with monkeypatch.context() as environment:
        environment.delenv("DATABASE_URL", raising=False)
        reloaded_config = importlib.reload(config_module)

        assert reloaded_config.Config.DATABASE_URL is None
        assert reloaded_config.Config.SQLALCHEMY_DATABASE_URI == "sqlite:///retailiq.db"

    importlib.reload(config_module)


def test_database_url_environment_override(monkeypatch):
    database_url = "postgresql://user:password@database.example/retailiq"

    with monkeypatch.context() as environment:
        environment.setenv("DATABASE_URL", database_url)
        reloaded_config = importlib.reload(config_module)

        assert reloaded_config.Config.DATABASE_URL == database_url
        assert reloaded_config.Config.SQLALCHEMY_DATABASE_URI == database_url

    importlib.reload(config_module)


def test_model_and_upload_paths_are_configurable(monkeypatch, tmp_path):
    model_path = tmp_path / "provisioned" / "retailiq.pkl"
    upload_folder = tmp_path / "persistent-uploads"

    with monkeypatch.context() as environment:
        environment.setenv("MODEL_PATH", str(model_path))
        environment.setenv("UPLOAD_FOLDER", str(upload_folder))
        reloaded_config = importlib.reload(config_module)

        assert reloaded_config.Config.MODEL_PATH == model_path.resolve()
        assert reloaded_config.Config.UPLOAD_FOLDER == upload_folder.resolve()

    importlib.reload(config_module)


@pytest.mark.parametrize(
    "missing_key",
    ["DATABASE_URL", "SECRET_KEY", "JWT_SECRET_KEY"],
)
def test_production_requires_database_and_secrets(missing_key):
    production_config = {
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql://user:password@database.example/retailiq",
        "SQLALCHEMY_DATABASE_URI": (
            "postgresql://user:password@database.example/retailiq"
        ),
        "SECRET_KEY": "production-flask-secret",
        "JWT_SECRET_KEY": "production-jwt-secret",
    }
    production_config[missing_key] = None

    with pytest.raises(RuntimeError, match=missing_key):
        create_app(production_config)


@pytest.mark.parametrize(
    ("secret_name", "placeholder"),
    [
        ("SECRET_KEY", "replace-with-a-random-secret-key"),
        ("JWT_SECRET_KEY", "replace-with-a-different-random-secret-key"),
    ],
)
def test_production_rejects_example_secret_placeholders(secret_name, placeholder):
    production_config = {
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql://user:password@database.example/retailiq",
        "SQLALCHEMY_DATABASE_URI": (
            "postgresql://user:password@database.example/retailiq"
        ),
        "SECRET_KEY": "production-flask-secret",
        "JWT_SECRET_KEY": "production-jwt-secret",
    }
    production_config[secret_name] = placeholder

    with pytest.raises(RuntimeError, match=secret_name):
        create_app(production_config)


def test_production_health_is_safe_and_debug_is_disabled(tmp_path):
    database_url = "postgresql://user:password@database.example/retailiq"
    secret_key = "production-flask-secret"
    jwt_secret = "production-jwt-secret"
    missing_model = tmp_path / "missing-model.pkl"
    app = create_app(
        {
            "APP_ENV": "production",
            "DATABASE_URL": database_url,
            "SQLALCHEMY_DATABASE_URI": database_url,
            "SECRET_KEY": secret_key,
            "JWT_SECRET_KEY": jwt_secret,
            "MODEL_PATH": missing_model,
            "DEBUG": True,
        }
    )

    response = app.test_client().get("/api/health")
    response_text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "healthy",
        "model_available": False,
        "model_type": None,
    }
    assert app.debug is False
    assert database_url not in response_text
    assert secret_key not in response_text
    assert jwt_secret not in response_text
    assert str(missing_model) not in response_text
