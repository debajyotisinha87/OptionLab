"""
Normalize Dhan API response into a Pandas DataFrame.
"""

from typing import Any

import pandas as pd


class DataNormalizer:

    @staticmethod
    def normalize(option_data: dict[str, Any]) -> pd.DataFrame:

        return pd.DataFrame(
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