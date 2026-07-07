"""
Data Validator
"""

import pandas as pd


class DataValidator:

    REQUIRED_COLUMNS = [
        "trade_datetime",
        "trade_date",
        "trade_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "oi",
        "iv",
        "spot",
    ]

    @classmethod
    def validate(cls, df: pd.DataFrame):

        cls.check_empty(df)
        cls.check_columns(df)
        cls.check_nulls(df)
        cls.check_duplicates(df)
        cls.check_ohlc(df)

        return True

    @staticmethod
    def check_empty(df):

        if df.empty:
            raise ValueError("Downloaded dataframe is empty.")

    @classmethod
    def check_columns(cls, df):

        missing = [
            c for c in cls.REQUIRED_COLUMNS
            if c not in df.columns
        ]

        if missing:
            raise ValueError(
                f"Missing columns: {missing}"
            )

    @staticmethod
    def check_nulls(df):

        if df.isnull().any().any():
            raise ValueError(
                "Null values detected."
            )

    @staticmethod
    def check_duplicates(df):

        duplicated = df.duplicated(
            subset=["trade_datetime"]
        )

        if duplicated.any():
            raise ValueError(
                "Duplicate timestamps detected."
            )

    @staticmethod
    def check_ohlc(df):

        invalid = (
            (df["high"] < df["open"]) |
            (df["high"] < df["close"]) |
            (df["low"] > df["open"]) |
            (df["low"] > df["close"])
        )

        if invalid.any():
            raise ValueError(
                "Invalid OHLC values detected."
            )