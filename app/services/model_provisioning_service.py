import logging
import os
import tempfile
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

logger = logging.getLogger(__name__)

DOWNLOAD_CHUNK_SIZE = 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 60


class ModelProvisioningError(RuntimeError):
    """Raised when a configured remote model cannot be provisioned safely."""


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, url):
        if urlsplit(url).scheme.lower() != "https":
            raise ValueError("Remote model download refused an insecure redirect.")

        redirected_request = super().redirect_request(
            request, file_pointer, code, message, headers, url
        )
        if _origin(request.full_url) != _origin(url):
            redirected_request.remove_header("Authorization")
        return redirected_request


def provision_model(model_path, repository=None, filename=None, token=None):
    target_path = Path(model_path)
    if target_path.is_file():
        return True

    if target_path.exists():
        raise ModelProvisioningError(
            "Forecasting model path exists but is not a regular file."
        )

    if not all((repository, filename, token)):
        logger.warning(
            "Forecasting model is missing and remote model configuration is incomplete."
        )
        return False

    download_url = _build_download_url(repository, filename)
    temporary_path = None

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{target_path.name}.",
            suffix=".download",
            dir=target_path.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            request = Request(
                download_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": "RetailIQ-model-provisioner/1.0",
                },
            )

            with _open_remote_model(
                request, timeout=DOWNLOAD_TIMEOUT_SECONDS
            ) as response:
                expected_size = _content_length(response)
                downloaded_size = _stream_response(response, temporary_file)

            if downloaded_size == 0:
                raise ModelProvisioningError(
                    "Remote forecasting model download returned an empty file."
                )
            if expected_size is not None and downloaded_size != expected_size:
                raise ModelProvisioningError(
                    "Remote forecasting model download was incomplete."
                )

            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        temporary_path.replace(target_path)
        logger.info("Forecasting model was provisioned successfully.")
        return True
    except ModelProvisioningError:
        _remove_temporary_file(temporary_path)
        logger.error("Forecasting model could not be provisioned from remote storage.")
        raise
    except Exception:
        _remove_temporary_file(temporary_path)
        logger.error("Forecasting model could not be provisioned from remote storage.")
        raise ModelProvisioningError(
            "Forecasting model could not be provisioned from remote storage."
        ) from None


def _build_download_url(repository, filename):
    repository_parts = repository.split("/")
    filename_parts = filename.split("/")

    if (
        len(repository_parts) != 2
        or any(part in {"", ".", ".."} for part in repository_parts)
        or any(part in {"", ".", ".."} for part in filename_parts)
        or "\\" in repository
        or "\\" in filename
    ):
        raise ModelProvisioningError(
            "Remote forecasting model configuration is invalid."
        )

    encoded_repository = "/".join(quote(part, safe="") for part in repository_parts)
    encoded_filename = "/".join(quote(part, safe="") for part in filename_parts)
    return (
        f"https://huggingface.co/{encoded_repository}/resolve/main/{encoded_filename}"
    )


def _content_length(response):
    value = response.headers.get("Content-Length")
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _open_remote_model(request, timeout):
    opener = build_opener(_SafeRedirectHandler())
    return opener.open(request, timeout=timeout)


def _origin(url):
    parsed_url = urlsplit(url)
    return parsed_url.scheme.lower(), parsed_url.hostname, parsed_url.port


def _stream_response(response, destination):
    downloaded_size = 0
    while True:
        chunk = response.read(DOWNLOAD_CHUNK_SIZE)
        if not chunk:
            return downloaded_size
        destination.write(chunk)
        downloaded_size += len(chunk)


def _remove_temporary_file(temporary_path):
    if temporary_path is not None:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Incomplete temporary model file could not be removed.")
