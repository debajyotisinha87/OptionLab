"""
api_client.py

Dhan API Client
"""

import requests

from app.config.config import (
    DHAN_CLIENT_ID,
    DHAN_ACCESS_TOKEN,
)


class DhanAPI:
    """
    Dhan API Client
    """

    BASE_URL = "https://api.dhan.co/v2"

    def __init__(self):
        self.headers = {
            "access-token": DHAN_ACCESS_TOKEN,
            "client-id": DHAN_CLIENT_ID,
            "Content-Type": "application/json",
        }

    def test_connection(self):
        """
        Test API connection by fetching fund limits.
        """

        endpoint = f"{self.BASE_URL}/fundlimit"

        try:
            response = requests.get(
                endpoint,
                headers=self.headers,
                timeout=30,
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

        except requests.exceptions.RequestException as e:
            print("\n❌ Error connecting to Dhan API")
            print(e)
            return None