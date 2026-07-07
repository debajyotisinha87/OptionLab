"""
api_client.py

Base Dhan API client.
"""

from app.api.http_client import HTTPClient
from app.config.config import (
    DHAN_ACCESS_TOKEN,
    DHAN_CLIENT_ID,
)


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

        print("\nStatus Code :", response.status_code)

        if response.status_code == 200:
            print("✅ Connected Successfully")
        else:
            print("❌ Connection Failed")

        try:
            print("\nResponse:")
            print(response.json())
        except Exception:
            print(response.text)

        return response