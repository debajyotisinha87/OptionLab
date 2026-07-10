"""
Normalize Dhan API response into the OptionLab standard format.
"""

from datetime import datetime

import pandas as pd

from app.config.logging_config import get_logger

logger = get_logger()


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

        df = DataNormalizer._drop_stale_duplicate_timestamps(df)

        return df

    @staticmethod
    def _drop_stale_duplicate_timestamps(df: pd.DataFrame) -> pd.DataFrame:
        """DhanHQ's rolling option endpoint stitches together whichever
        contract is "nearest expiry" as it rolls week to week, and
        during an expiry-day transition (e.g. BSE moving Sensex weekly
        expiry from Tuesday to Thursday in Sep 2025) it has been
        observed to also carry forward a since-inactive contract's
        frozen last-traded-price at every subsequent minute, alongside
        the real, actively-traded contract - producing two rows for
        the same trade_datetime. The stale row is identifiable by
        volume 0 (no real trade), so keep whichever row at each
        timestamp has the higher volume."""

        before = len(df)

        df = df.sort_values(["trade_datetime", "volume"], ascending=[True, False])

        df = df.drop_duplicates(subset=["trade_datetime"], keep="first")

        dropped = before - len(df)

        if dropped:

            logger.warning(
                f"Dropped {dropped} duplicate-timestamp candle(s) "
                "(kept the higher-volume row per timestamp)."
            )

        return df.sort_values("trade_datetime").reset_index(drop=True)