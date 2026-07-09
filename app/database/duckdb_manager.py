"""
DuckDB Manager
"""

import threading
from pathlib import Path

import duckdb


class DuckDBManager:

    def __init__(self):
        """DuckDB allows only one connection to a database file per
        process (verified empirically on this platform: opening a
        second connection, same or cross-process, raises a
        ConnectionException/IOException while the first is held open).
        So every Repository in a process must share this single
        connection, and self.lock (an RLock, so a synchronized method
        calling another synchronized method on the same instance
        doesn't deadlock) is what makes sharing it safely across
        threads possible - e.g. a background download job plus a web
        server's request-handler threads."""

        Path("database").mkdir(exist_ok=True)

        self.lock = threading.RLock()

        self.connection = duckdb.connect("database/optionlab.duckdb")

    def insert_dataframe(self, df):

        self.connection.register("option_df", df)

        self.connection.execute(
            """
            INSERT INTO option_data
            SELECT *
            FROM option_df
            """
        )