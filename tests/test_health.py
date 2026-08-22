import joblib

from app import create_app


def test_health_endpoint_reports_loaded_model_type(tmp_path):
    model_path = tmp_path / "test-model.pkl"
    joblib.dump({"fixture": True}, model_path)
    app = create_app({"TESTING": True, "MODEL_PATH": model_path})

    response = app.test_client().get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "healthy",
        "model_available": True,
        "model_type": "dict",
    }


def test_health_endpoint_reports_missing_model_without_exposing_path(tmp_path):
    missing_model = tmp_path / "missing-model.pkl"
    app = create_app({"TESTING": True, "MODEL_PATH": missing_model})

    response = app.test_client().get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "healthy",
        "model_available": False,
        "model_type": None,
    }
    assert str(missing_model) not in response.get_data(as_text=True)
