"""
api_client.py

Base Dhan API client.
"""

from app.api.http_client import HTTPClient
from app.config.config import (
    DHAN_ACCESS_TOKEN,
    DHAN_CLIENT_ID,
)
from app.config.logging_config import get_logger

logger = get_logger()


class DhanAPI:
    """Base client for all Dhan APIs."""

    BASE_URL = "https://api.dhan.co/v2"

    def __init__(self):

        self.http = HTTPClient()

        self.headers = {
            "access-token": DHAN_ACCESS_TOKEN,
            "client-id": DHAN_CLIENT_ID,
            "Content-Type": "application/json",
        }

    def test_connection(self):

        response = self.http.get(
            url=f"{self.BASE_URL}/fundlimit",
            headers=self.headers,
        )

        logger.info(f"Status Code : {response.status_code}")

        if response.status_code == 200:
            logger.info("Connected Successfully")
        else:
            logger.error("Connection Failed")

        try:
            logger.debug(f"Response: {response.json()}")
        except Exception:
            logger.debug(f"Response: {response.text}")

        return response