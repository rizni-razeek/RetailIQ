from io import BytesIO
from urllib.request import Request

import pytest

import app as app_module
from app.services import model_provisioning_service
from app.services.model_provisioning_service import (
    DOWNLOAD_TIMEOUT_SECONDS,
    ModelProvisioningError,
    _SafeRedirectHandler,
    provision_model,
)


class FakeResponse:
    def __init__(self, content):
        self._stream = BytesIO(content)
        self.headers = {"Content-Length": str(len(content))}

    def __enter__(self):
        return self

    def __exit__(self, _exception_type, _exception, _traceback):
        return False

    def read(self, size=-1):
        return self._stream.read(size)


def test_existing_model_does_not_attempt_remote_download(monkeypatch, tmp_path):
    model_path = tmp_path / "retailiq_final_model.pkl"
    model_path.write_bytes(b"existing model")

    def unexpected_download(*_args, **_kwargs):
        pytest.fail("Remote download should not run for an existing model.")

    monkeypatch.setattr(
        model_provisioning_service, "_open_remote_model", unexpected_download
    )

    assert provision_model(
        model_path,
        repository="owner/private-model",
        filename="model.pkl",
        token="private-token",
    )
    assert model_path.read_bytes() == b"existing model"


def test_missing_model_is_downloaded_with_complete_hugging_face_config(
    monkeypatch, tmp_path
):
    model_path = tmp_path / "nested" / "retailiq_final_model.pkl"
    content = b"downloaded model content"
    captured_request = {}

    def fake_open_remote_model(request, timeout):
        captured_request["request"] = request
        captured_request["timeout"] = timeout
        return FakeResponse(content)

    monkeypatch.setattr(
        model_provisioning_service, "_open_remote_model", fake_open_remote_model
    )

    assert provision_model(
        model_path,
        repository="RRizni/retailiq-demand-forecast-model",
        filename="retailiq_final_model.pkl",
        token="private-token",
    )

    request = captured_request["request"]
    assert model_path.read_bytes() == content
    assert request.full_url == (
        "https://huggingface.co/RRizni/retailiq-demand-forecast-model/"
        "resolve/main/retailiq_final_model.pkl"
    )
    assert request.get_header("Authorization") == "Bearer private-token"
    assert "private-token" not in request.full_url
    assert captured_request["timeout"] == DOWNLOAD_TIMEOUT_SECONDS


def test_missing_model_with_incomplete_config_keeps_unavailable_health_behavior(
    tmp_path,
):
    model_path = tmp_path / "missing-model.pkl"
    app = app_module.create_app(
        {
            "TESTING": True,
            "MODEL_PATH": model_path,
            "HF_MODEL_REPO": "",
            "HF_MODEL_FILENAME": "",
            "HF_TOKEN": "",
        }
    )

    response = app.test_client().get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "healthy",
        "model_available": False,
        "model_type": None,
    }


def test_failed_download_leaves_no_partial_production_model(monkeypatch, tmp_path):
    model_path = tmp_path / "retailiq_final_model.pkl"

    class InterruptedResponse(FakeResponse):
        def __init__(self):
            super().__init__(b"a complete response was expected")
            self._read_count = 0

        def read(self, size=-1):
            self._read_count += 1
            if self._read_count == 1:
                return b"partial"
            raise OSError("connection interrupted")

    monkeypatch.setattr(
        model_provisioning_service,
        "_open_remote_model",
        lambda *_args, **_kwargs: InterruptedResponse(),
    )

    with pytest.raises(ModelProvisioningError, match="could not be provisioned"):
        provision_model(
            model_path,
            repository="owner/private-model",
            filename="model.pkl",
            token="private-token",
        )

    assert not model_path.exists()
    assert list(tmp_path.glob(".*.download")) == []


def test_download_failure_does_not_expose_token(monkeypatch, tmp_path, caplog):
    model_path = tmp_path / "retailiq_final_model.pkl"
    token = "hf_secret_value_that_must_not_leak"

    def failed_download(*_args, **_kwargs):
        raise OSError(f"request rejected for token {token}")

    monkeypatch.setattr(
        model_provisioning_service, "_open_remote_model", failed_download
    )

    with caplog.at_level("ERROR"), pytest.raises(ModelProvisioningError) as error:
        provision_model(
            model_path,
            repository="owner/private-model",
            filename="model.pkl",
            token=token,
        )

    assert token not in str(error.value)
    assert token not in caplog.text
    assert not model_path.exists()


def test_cross_origin_redirect_does_not_forward_token():
    original_request = Request(
        "https://huggingface.co/owner/private-model/resolve/main/model.pkl",
        headers={"Authorization": "Bearer private-token"},
    )

    redirected_request = _SafeRedirectHandler().redirect_request(
        original_request,
        None,
        302,
        "Found",
        {},
        "https://cdn-lfs.example/signed-model-url",
    )

    assert redirected_request.get_header("Authorization") is None


def test_application_startup_invokes_model_provisioning(monkeypatch, tmp_path):
    model_path = tmp_path / "retailiq_final_model.pkl"
    received = {}

    def fake_provision_model(**configuration):
        received.update(configuration)
        model_path.write_bytes(b"provisioned during startup")
        return True

    monkeypatch.setattr(app_module, "provision_model", fake_provision_model)

    app_module.create_app(
        {
            "TESTING": True,
            "MODEL_PATH": model_path,
            "HF_MODEL_REPO": "owner/private-model",
            "HF_MODEL_FILENAME": "model.pkl",
            "HF_TOKEN": "private-token",
        }
    )

    assert received == {
        "model_path": model_path,
        "repository": "owner/private-model",
        "filename": "model.pkl",
        "token": "private-token",
    }
    assert model_path.is_file()
