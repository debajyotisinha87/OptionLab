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

        response = self.api.fetch(payload)

        data = response.get("data", {})
        ce = data.get("ce")

        if ce is None:
            print("No data returned.")
            return

        df = DataNormalizer.normalize(
            option_data=ce,
            symbol=payload["symbol"],
            option_type=payload["drvOptionType"],
            strike_type=payload["strike"],
            expiry_flag=payload["expiryFlag"],
            expiry_code=payload["expiryCode"],
        )

        report = DataValidator.validate(df)

        if not report.passed:
            print(report.errors)
            return

        self.repo.insert_option_data(df)

        print(f"✓ Inserted {len(df)} rows")