"""
DuckDB Manager
"""

from pathlib import Path

import duckdb


class DuckDBManager:

    def __init__(self):

        Path("database").mkdir(exist_ok=True)

        self.connection = duckdb.connect(
            "database/optionlab.duckdb"
        )

    def create_tables(self):

        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS option_data (

                symbol VARCHAR,

                trade_datetime TIMESTAMP,

                trade_date DATE,

                trade_time TIME,

                option_type VARCHAR,

                strike_type VARCHAR,

                expiry_flag VARCHAR,

                expiry_code INTEGER,

                open DOUBLE,

                high DOUBLE,

                low DOUBLE,

                close DOUBLE,

                volume BIGINT,

                oi BIGINT,

                iv DOUBLE,

                spot DOUBLE
            )
            """
        )

        print("✓ Database Ready")

    def insert_dataframe(self, df):

        self.connection.register("option_df", df)

        self.connection.execute(
            """
            INSERT INTO option_data
            SELECT *
            FROM option_df
            """
        )

        print(f"✓ Inserted {len(df)} rows")