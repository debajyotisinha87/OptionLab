"""
Download one day's historical option data.
"""

from app.api.rolling_option import RollingOptionAPI
from app.storage.data_normalizer import DataNormalizer
from app.storage.csv_writer import CSVWriter
from app.database.duckdb_manager import DuckDBManager


def test_download():

    api = RollingOptionAPI()

    payload = {
        "exchangeSegment": "NSE_FNO",
        "securityId": 13,
        "instrument": "OPTIDX",
        "expiryFlag": "MONTH",
        "expiryCode": 1,
        "fromDate": "2025-07-01",
        "toDate": "2025-07-01",
        "strike": "ATM",
        "drvOptionType": "CALL",
        "interval": 1,
        "requiredData": [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "oi",
            "iv",
            "spot",
        ],
    }

    response = api.fetch(payload)

    data = response.get("data", {})
    ce = data.get("ce")

    print(response.keys())

    if ce is None:
        print("No CE data returned.")
        return

    df = DataNormalizer.normalize(
        option_data=ce,
        symbol="NIFTY",
        option_type="CALL",
        strike_type="ATM",
        expiry_flag="MONTH",
        expiry_code=1,
    )

    db = DuckDBManager()
    db.create_tables()
    db.insert_dataframe(df)

    print(df.head())

    CSVWriter.save(df, "NIFTY_2025-07-01_ATM_CE.csv")


if __name__ == "__main__":
    test_download()