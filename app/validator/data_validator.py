"""
Data Validator
"""

import pandas as pd

from app.models.validation_report import ValidationReport


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
    def validate(cls, df: pd.DataFrame) -> ValidationReport:

        report = ValidationReport()

        try:
            cls.check_empty(df)
            cls.check_columns(df)
            cls.check_nulls(df)
            cls.check_duplicates(df)
            cls.check_ohlc(df)
        except ValueError as e:
            report.add_error(str(e))

        return report

    @staticmethod
    def check_empty(df: pd.DataFrame):

        if df.empty:
            raise ValueError("Downloaded dataframe is empty.")

    @classmethod
    def check_columns(cls, df: pd.DataFrame):

        missing = [
            column
            for column in cls.REQUIRED_COLUMNS
            if column not in df.columns
        ]

        if missing:
            raise ValueError(f"Missing columns: {missing}")

    @staticmethod
    def check_nulls(df: pd.DataFrame):

        if df.isnull().any().any():
            raise ValueError("Null values detected.")

    @staticmethod
    def check_duplicates(df: pd.DataFrame):

        if df.duplicated(subset=["trade_datetime"]).any():
            raise ValueError("Duplicate timestamps detected.")

    @staticmethod
    def check_ohlc(df: pd.DataFrame):

        invalid = (
            (df["high"] < df["open"])
            | (df["high"] < df["close"])
            | (df["low"] > df["open"])
            | (df["low"] > df["close"])
        )

        if invalid.any():
            raise ValueError("Invalid OHLC values detected.")