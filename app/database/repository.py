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

    def get_job_progress(self, job_id: str) -> dict:

        result = self.db.connection.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'COMPLETED'),
                COUNT(*) FILTER (WHERE status = 'FAILED'),
                COALESCE(SUM(inserted_rows), 0)
            FROM
                download_manifest
            WHERE
                job_id = ?
            """,
            [job_id],
        ).fetchone()

        return {
            "completed_batches": result[0],
            "failed_batches": result[1],
            "total_rows": result[2],
        }

    # ------------------------------------------------------------------
    # Download Jobs
    # ------------------------------------------------------------------

    def create_download_jobs_table(self):

        self.execute_sql_file("download_jobs.sql")

    def save_job(
        self,
        job_id: str,
        underlying: str,
        instrument: str,
        expiry_type: str,
        option_types: str,
        strike_from: int,
        strike_to: int,
        interval: int,
        start_date: str,
        end_date: str,
        created_at,
    ):

        existing = self.get_job(job_id)

        if existing is not None:

            if (
                existing["underlying"] != underlying
                or existing["expiry_type"] != expiry_type
                or existing["option_types"] != option_types
                or existing["strike_from"] != strike_from
                or existing["strike_to"] != strike_to
                or str(existing["start_date"]) != start_date
                or str(existing["end_date"]) != end_date
            ):

                raise ValueError(
                    f"job_id '{job_id}' already exists with different "
                    "parameters. Use a new job_id, or call resume(job_id) "
                    "to continue the existing job."
                )

            return

        self.db.connection.execute(
            """
            INSERT INTO download_jobs (
                job_id,
                underlying,
                instrument,
                expiry_type,
                option_types,
                strike_from,
                strike_to,
                interval,
                start_date,
                end_date,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
            """,
            [
                job_id,
                underlying,
                instrument,
                expiry_type,
                option_types,
                strike_from,
                strike_to,
                interval,
                start_date,
                end_date,
                created_at,
            ],
        )

    def get_job(self, job_id: str) -> dict | None:

        cursor = self.db.connection.execute(
            """
            SELECT *
            FROM download_jobs
            WHERE job_id = ?
            LIMIT 1
            """,
            [job_id],
        )

        row = cursor.fetchone()

        if row is None:

            return None

        columns = [column[0] for column in cursor.description]

        return dict(zip(columns, row))

    def mark_job_started(self, job_id: str):

        self.db.connection.execute(
            """
            UPDATE download_jobs
            SET
                status = 'RUNNING',
                started_at = COALESCE(started_at, CURRENT_TIMESTAMP)
            WHERE
                job_id = ?
            """,
            [job_id],
        )

    def set_job_total_batches(self, job_id: str, total_batches: int):

        self.db.connection.execute(
            """
            UPDATE download_jobs
            SET
                total_batches = ?
            WHERE
                job_id = ?
            """,
            [total_batches, job_id],
        )

    def mark_job_completed(
        self,
        job_id: str,
        completed_batches: int,
        failed_batches: int,
        total_rows: int,
    ):

        self.db.connection.execute(
            """
            UPDATE download_jobs
            SET
                status = 'COMPLETED',
                completed_at = CURRENT_TIMESTAMP,
                completed_batches = ?,
                failed_batches = ?,
                total_rows = ?
            WHERE
                job_id = ?
            """,
            [completed_batches, failed_batches, total_rows, job_id],
        )

    def mark_job_failed(
        self,
        job_id: str,
        completed_batches: int,
        failed_batches: int,
        total_rows: int,
    ):

        self.db.connection.execute(
            """
            UPDATE download_jobs
            SET
                status = 'FAILED',
                completed_at = CURRENT_TIMESTAMP,
                completed_batches = ?,
                failed_batches = ?,
                total_rows = ?
            WHERE
                job_id = ?
            """,
            [completed_batches, failed_batches, total_rows, job_id],
        )
