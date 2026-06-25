from __future__ import annotations

import httpx


class APIClientError(Exception):
    """Base exception for the API client."""
    pass


class APIConnectionError(APIClientError):
    """Raised when the backend server is unreachable."""
    pass


class APIHTTPError(APIClientError):
    """Raised when the backend returns an error status code."""
    def __init__(self, status_code: int, detail: str, raw_response: dict | None = None) -> None:
        super().__init__(f"HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail
        self.raw_response = raw_response


class APIClient:
    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url
        self.client = httpx.Client()

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            response = self.client.request(method, url, **kwargs)
            if response.status_code == 204:
                return {}
            
            try:
                response_json = response.json()
            except Exception:
                response_json = {}

            if 200 <= response.status_code < 300:
                return response_json

            # Extract detail from validation/error response if possible
            if isinstance(response_json, dict):
                detail = response_json.get("detail", "Unknown backend error")
            else:
                detail = response.text or "Unknown backend error"
            
            raise APIHTTPError(response.status_code, detail, response_json)
        except httpx.RequestError as error:
            raise APIConnectionError(
                f"Could not connect to backend at {self.base_url}. "
                "Please verify that the FastAPI server is running."
            ) from error
        except APIClientError:
            raise
        except Exception as error:
            raise APIClientError(f"An unexpected error occurred: {str(error)}") from error

    def health(self) -> dict:
        return self._request("GET", "/health")

    def list_architectures(self) -> list[dict]:
        res = self._request("GET", "/architectures")
        return res if isinstance(res, list) else []

    def get_architecture(self, architecture_id: str) -> dict:
        return self._request("GET", f"/architectures/{architecture_id}")

    def create_architecture(self, payload: dict) -> dict:
        return self._request("POST", "/architectures", json=payload)

    def update_architecture(self, architecture_id: str, payload: dict) -> dict:
        return self._request("PUT", f"/architectures/{architecture_id}", json=payload)

    def delete_architecture(self, architecture_id: str) -> None:
        self._request("DELETE", f"/architectures/{architecture_id}")

    def add_resource(self, architecture_id: str, payload: dict) -> dict:
        return self._request("POST", f"/architectures/{architecture_id}/resources", json=payload)

    def update_resource(self, architecture_id: str, resource_id: str, payload: dict) -> dict:
        return self._request("PUT", f"/architectures/{architecture_id}/resources/{resource_id}", json=payload)

    def delete_resource(self, architecture_id: str, resource_id: str) -> None:
        self._request("DELETE", f"/architectures/{architecture_id}/resources/{resource_id}")

    def add_relationship(self, architecture_id: str, payload: dict) -> dict:
        return self._request("POST", f"/architectures/{architecture_id}/relationships", json=payload)

    def delete_relationship(self, architecture_id: str, payload: dict) -> None:
        self._request("DELETE", f"/architectures/{architecture_id}/relationships", json=payload)

    def validate_architecture(self, architecture_id: str) -> dict:
        return self._request("POST", f"/architectures/{architecture_id}/validate")

    def generate_terraform(self, architecture_id: str) -> dict:
        return self._request("POST", f"/architectures/{architecture_id}/terraform")

    def get_latest_terraform(self, architecture_id: str) -> dict:
        return self._request("GET", f"/architectures/{architecture_id}/terraform")

    def load_example(self, example_name: str) -> dict:
        return self._request("POST", f"/examples/{example_name}")
