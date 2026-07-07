"""
Repository Layer

All database access goes through this class.
"""

from fileinput import filename
from pathlib import Path

import pandas as pd
from polars import sql

from app.database.duckdb_manager import DuckDBManager
from pathlib import Path


class Repository:

    def __init__(self):

        self.db = DuckDBManager()

    def insert_option_data(self, df: pd.DataFrame):

        self.db.insert_dataframe(df)

    def execute(self, sql: str):

        return self.db.connection.execute(sql)

    def query(self, sql: str):

        return self.db.connection.execute(sql).fetchdf()
    
    def execute_sql_file(self, filename: str):

        sql_path = Path("app/database/schema") / filename

        sql = sql_path.read_text(encoding="utf-8")

        self.execute(sql)