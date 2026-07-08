"""
Download Service
"""

from app.api.rolling_option import RollingOptionAPI
from app.database.repository import Repository
from app.storage.data_normalizer import DataNormalizer
from app.validator.data_validator import DataValidator


class DownloadService:

    def __init__(self):

        self.api = RollingOptionAPI()
        self.repo = Repository()

    def download(self, payload):

        try:

            response = self.api.fetch(payload)

            data = response.get("data", {})
            option_data_key = self.get_option_data_key(
                payload["drvOptionType"]
            )
            option_data = data.get(option_data_key)

            if option_data is None:

                return {
                    "success": False,
                    "downloaded_rows": 0,
                    "inserted_rows": 0,
                    "error": "No data returned from API.",
                }

            df = DataNormalizer.normalize(
                option_data=option_data,
                symbol=payload["symbol"],
                option_type=payload["drvOptionType"],
                strike_type=payload["strike"],
                expiry_flag=payload["expiryFlag"],
                expiry_code=payload["expiryCode"],
            )

            report = DataValidator.validate(df)

            if not report.passed:

                return {
                    "success": False,
                    "downloaded_rows": len(df),
                    "inserted_rows": 0,
                    "error": "; ".join(report.errors),
                }

            self.repo.insert_option_data(df)

            print(f"✓ Inserted {len(df)} rows")

            return {
                "success": True,
                "downloaded_rows": len(df),
                "inserted_rows": len(df),
                "error": None,
            }

        except Exception as ex:

            return {
                "success": False,
                "downloaded_rows": 0,
                "inserted_rows": 0,
                "error": str(ex),
            }

    @staticmethod
    def get_option_data_key(option_type: str):

        if option_type == "CALL":

            return "ce"

        if option_type == "PUT":

            return "pe"

        raise ValueError(f"Unsupported option type: {option_type}")
