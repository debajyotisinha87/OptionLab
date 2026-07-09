"""
Rolling Option API

Handles communication with Dhan's Rolling Option endpoint.
"""

from typing import Any

from app.api.api_client import DhanAPI


class RollingOptionAPI(DhanAPI):
    """Rolling Option API client."""

    ENDPOINT = "/charts/rollingoption"

    def endpoint(self) -> str:
        """Return the full API endpoint."""
        return f"{self.BASE_URL}{self.ENDPOINT}"

    def fetch(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Fetch rolling option historical data.
        """

        response = self.http.post(
            url=self.endpoint(),
            headers=self.headers,
            payload=payload,
        )

        try:
            body = response.json()
        except Exception:
            body = {
                "status": "error",
                "message": response.text,
            }

        if isinstance(body, dict):
            body.setdefault("_http_status_code", response.status_code)

        return body