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

    def insert_dataframe(self, df):

        self.connection.register("option_df", df)

        self.connection.execute(
            """
            INSERT INTO option_data
            SELECT *
            FROM option_df
            """
        )