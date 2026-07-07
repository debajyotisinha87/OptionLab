"""
http_client.py

Shared HTTP client for all Dhan API requests.
"""

from typing import Any

import requests


class HTTPClient:
    """Reusable HTTP client."""

    def get(
        self,
        url: str,
        headers: dict[str, str],
        timeout: int = 30,
    ) -> requests.Response:

        return requests.get(
            url=url,
            headers=headers,
            timeout=timeout,
        )

    def post(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: int = 60,
    ) -> requests.Response:

        return requests.post(
            url=url,
            headers=headers,
            json=payload,
            timeout=timeout,
        )