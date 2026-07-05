from __future__ import annotations

from unittest.mock import MagicMock, patch
import httpx
import pytest

from cloudblueprint.frontend.api_client import (
    APIClient,
    APIClientError,
    APIConnectionError,
    APIHTTPError,
)


def test_api_client_health() -> None:
    client = APIClient()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "ok"}

    with patch.object(client.client, "request", return_value=mock_response) as mock_request:
        result = client.health()
        assert result == {"status": "ok"}
        mock_request.assert_called_once_with("GET", "http://localhost:8000/health")


def test_api_client_list_architectures() -> None:
    client = APIClient()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"id": "arch1", "name": "Architecture 1", "resources": {}, "relationships": [], "created_at": "", "updated_at": ""}
    ]

    with patch.object(client.client, "request", return_value=mock_response) as mock_request:
        result = client.list_architectures()
        assert len(result) == 1
        assert result[0]["id"] == "arch1"
        mock_request.assert_called_once_with("GET", "http://localhost:8000/architectures")


def test_api_client_create_architecture() -> None:
    client = APIClient()
    mock_response = MagicMock()
    mock_response.status_code = 201
    payload = {"id": "new-arch", "name": "New Architecture"}
    mock_response.json.return_value = {**payload, "resources": {}, "relationships": [], "created_at": "", "updated_at": ""}

    with patch.object(client.client, "request", return_value=mock_response) as mock_request:
        result = client.create_architecture(payload)
        assert result["id"] == "new-arch"
        mock_request.assert_called_once_with("POST", "http://localhost:8000/architectures", json=payload)


def test_api_client_validate_architecture() -> None:
    client = APIClient()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"architecture_id": "arch1", "is_valid": True, "results": []}

    with patch.object(client.client, "request", return_value=mock_response) as mock_request:
        result = client.validate_architecture("arch1")
        assert result["is_valid"] is True
        mock_request.assert_called_once_with("POST", "http://localhost:8000/architectures/arch1/validate")


def test_api_client_generate_terraform() -> None:
    client = APIClient()
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "id": "gen-1",
        "architecture_id": "arch1",
        "files": [{"filename": "provider.tf", "content": "provider block"}],
        "created_at": ""
    }

    with patch.object(client.client, "request", return_value=mock_response) as mock_request:
        result = client.generate_terraform("arch1")
        assert result["id"] == "gen-1"
        assert len(result["files"]) == 1
        mock_request.assert_called_once_with("POST", "http://localhost:8000/architectures/arch1/terraform")


def test_api_client_http_error_handling() -> None:
    client = APIClient()
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"detail": "Invalid resource configuration"}

    with patch.object(client.client, "request", return_value=mock_response):
        with pytest.raises(APIHTTPError) as excinfo:
            client.create_architecture({"id": "invalid"})
        assert excinfo.value.status_code == 400
        assert "Invalid resource configuration" in str(excinfo.value)


def test_api_client_connection_error_handling() -> None:
    client = APIClient()

    with patch.object(client.client, "request", side_effect=httpx.RequestError("Connection refused")):
        with pytest.raises(APIConnectionError) as excinfo:
            client.health()
        assert "Could not connect to backend" in str(excinfo.value)
