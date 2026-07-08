"""
Repository Layer

All database access goes through this class.
"""

from pathlib import Path

import pandas as pd

from app.database.duckdb_manager import DuckDBManager


class Repository:

    def __init__(self):

        self.db = DuckDBManager()

    # ------------------------------------------------------------------
    # Option Data
    # ------------------------------------------------------------------

    def create_option_data_table(self):

        self.execute_sql_file("option_data.sql")

    def insert_option_data(self, df: pd.DataFrame):

        self.db.insert_dataframe(df)

    # ------------------------------------------------------------------
    # Generic SQL
    # ------------------------------------------------------------------

    def execute(self, sql: str):

        return self.db.connection.execute(sql)

    def query(self, sql: str):

        return self.db.connection.execute(sql).fetchdf()

    def execute_sql_file(self, filename: str):

        sql_path = Path("app/database/schema") / filename

        sql = sql_path.read_text(encoding="utf-8")

        self.execute(sql)

    # ------------------------------------------------------------------
    # Download Manifest
    # ------------------------------------------------------------------

    def create_download_manifest_table(self):

        self.execute_sql_file("download_manifest.sql")

    def create_manifest_entry(
        self,
        job_id: str,
        batch_number: int,
        underlying: str,
        instrument: str,
        expiry_type: str,
        option_type: str,
        strike_offset: int,
        interval: int,
        from_date: str,
        to_date: str,
        status: str = "PENDING",
    ):

        self.db.connection.execute(
            """
            INSERT INTO download_manifest (
                job_id,
                batch_number,
                underlying,
                instrument,
                expiry_type,
                option_type,
                strike_offset,
                interval,
                from_date,
                to_date,
                status
            )
            SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1
                FROM download_manifest
                WHERE
                    job_id = ?
                AND
                    batch_number = ?
                AND
                    option_type = ?
                AND
                    strike_offset = ?
            )
            """,
            [
                job_id,
                batch_number,
                underlying,
                instrument,
                expiry_type,
                option_type,
                strike_offset,
                interval,
                from_date,
                to_date,
                status,
                job_id,
                batch_number,
                option_type,
                strike_offset,
            ],
        )

    def get_manifest_status(
        self,
        job_id: str,
        batch_number: int,
        option_type: str,
        strike_offset: int,
    ) -> str | None:

        result = self.db.connection.execute(
            """
            SELECT
                status
            FROM
                download_manifest
            WHERE
                job_id = ?
            AND
                batch_number = ?
            AND
                option_type = ?
            AND
                strike_offset = ?
            LIMIT 1
            """,
            [
                job_id,
                batch_number,
                option_type,
                strike_offset,
            ],
        ).fetchone()

        if result is None:

            return None

        return result[0]

    def mark_batch_started(
        self,
        job_id: str,
        batch_number: int,
        option_type: str,
        strike_offset: int,
    ):

        self.db.connection.execute(
            """
            UPDATE download_manifest
            SET
                status = 'RUNNING',
                started_at = CURRENT_TIMESTAMP,
                completed_at = NULL,
                error_message = NULL
            WHERE
                job_id = ?
            AND
                batch_number = ?
            AND
                option_type = ?
            AND
                strike_offset = ?
            """,
            [
                job_id,
                batch_number,
                option_type,
                strike_offset,
            ],
        )

    def mark_batch_completed(
        self,
        job_id: str,
        batch_number: int,
        downloaded_rows: int,
        inserted_rows: int,
        option_type: str,
        strike_offset: int,
    ):

        self.db.connection.execute(
            """
            UPDATE download_manifest
            SET
                status = 'COMPLETED',
                downloaded_rows = ?,
                inserted_rows = ?,
                completed_at = CURRENT_TIMESTAMP,
                error_message = NULL
            WHERE
                job_id = ?
            AND
                batch_number = ?
            AND
                option_type = ?
            AND
                strike_offset = ?
            """,
            [
                downloaded_rows,
                inserted_rows,
                job_id,
                batch_number,
                option_type,
                strike_offset,
            ],
        )

    def mark_batch_failed(
        self,
        job_id: str,
        batch_number: int,
        error_message: str,
        option_type: str,
        strike_offset: int,
    ):

        self.db.connection.execute(
            """
            UPDATE download_manifest
            SET
                status = 'FAILED',
                retry_count = retry_count + 1,
                error_message = ?,
                completed_at = CURRENT_TIMESTAMP
            WHERE
                job_id = ?
            AND
                batch_number = ?
            AND
                option_type = ?
            AND
                strike_offset = ?
            """,
            [
                error_message,
                job_id,
                batch_number,
                option_type,
                strike_offset,
            ],
        )
