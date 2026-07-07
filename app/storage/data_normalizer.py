"""
Normalize Dhan API response into the OptionLab standard format.
"""

from datetime import datetime

import pandas as pd


class DataNormalizer:

    @staticmethod
    def normalize(
        option_data,
        symbol,
        option_type,
        strike_type,
        expiry_flag,
        expiry_code,
    ):

        df = pd.DataFrame(
            {
                "timestamp": option_data["timestamp"],
                "open": option_data["open"],
                "high": option_data["high"],
                "low": option_data["low"],
                "close": option_data["close"],
                "volume": option_data["volume"],
                "oi": option_data["oi"],
                "iv": option_data["iv"],
                "spot": option_data["spot"],
            }
        )

        # Convert Unix timestamp to datetime
        df["trade_datetime"] = pd.to_datetime(
            df["timestamp"],
            unit="s"
        )

        df["trade_date"] = df["trade_datetime"].dt.date
        df["trade_time"] = df["trade_datetime"].dt.time

        # Metadata
        df["symbol"] = symbol
        df["option_type"] = option_type
        df["strike_type"] = strike_type
        df["expiry_flag"] = expiry_flag
        df["expiry_code"] = expiry_code

        # Reorder columns to match DuckDB schema
        df = df[
            [
                "symbol",
                "trade_datetime",
                "trade_date",
                "trade_time",
                "option_type",
                "strike_type",
                "expiry_flag",
                "expiry_code",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "oi",
                "iv",
                "spot",
            ]
        ]

        return df