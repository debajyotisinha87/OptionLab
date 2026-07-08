"""
http_client.py

Shared HTTP client for all Dhan API requests.
"""

from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

RETRY_ATTEMPTS = 3

# Rate-limit and server-side errors are worth retrying; other 4xx codes
# (bad auth, malformed request, ...) will never succeed on retry.
TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


def raise_for_transient_status(response: requests.Response) -> requests.Response:

    if response.status_code in TRANSIENT_STATUS_CODES:

        response.raise_for_status()

    return response


class HTTPClient:
    """
    Reusable HTTP client.

    get()/post() retry automatically on transient network errors and on
    429/5xx responses. Retrying assumes the request is safe to repeat -
    the Dhan endpoints used today are read-only data queries. Don't reuse
    post() for a non-idempotent call without reconsidering this.
    """

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True,
    )
    def get(
        self,
        url: str,
        headers: dict[str, str],
        timeout: int = 30,
    ) -> requests.Response:

        response = requests.get(
            url=url,
            headers=headers,
            timeout=timeout,
        )

        return raise_for_transient_status(response)

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True,
    )
    def post(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: int = 60,
    ) -> requests.Response:

        response = requests.post(
            url=url,
            headers=headers,
            json=payload,
            timeout=timeout,
        )

        return raise_for_transient_status(response)
