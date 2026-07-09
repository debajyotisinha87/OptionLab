"""
End-to-End Web GUI Test (TASK-024)

Exercises the web GUI's full, real download pipeline - HTTP POST ->
JobRunner -> DownloadEngine -> ... -> the real database/optionlab.duckdb
- the same real pipeline test_e2e_cli.py exercises via the CLI, but
through the FastAPI routes and a background thread instead of argparse
and a synchronous call, proving the GUI is a genuine thin layer over
the same pipeline rather than a separate implementation. Only the
outermost network boundary (RollingOptionAPI.fetch) is stubbed.
"""

import time
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

import app.web.server as server_module
from app.api.rolling_option import RollingOptionAPI
from app.builders.payload_builder import PayloadBuilder

JOB_ID = "JOB-E2E-WEB-TEST-FULLRANGE"
PARQUET_JOB_ID = "JOB-E2E-WEB-PARQUET-TEST-FULLRANGE"

# Every download always covers the full ATM-10..ATM+10 range (21
# strike offsets); with a single option type, that's 21 units in 1 batch.
UNITS_PER_OPTION_TYPE = PayloadBuilder.MAX_STRIKE_OFFSET - PayloadBuilder.MIN_STRIKE_OFFSET + 1

# Fixed, not per-run-random: check_job_reusable() locks
# parquet_output_dir as part of a job_id's identity, and a completed
# unit is skipped (never re-downloaded/re-written) on rerun, so this
# path must stay identical - and the file left behind untouched -
# across repeated runs for this test to remain idempotent.
PARQUET_OUTPUT_DIR = Path("data") / "test_e2e_parquet_web"


def fake_fetch(self, payload):

    option_data = {
        "timestamp": [1735707000],
        "open": [100.0],
        "high": [105.0],
        "low": [95.0],
        "close": [102.5],
        "volume": [1200],
        "oi": [4500],
        "iv": [14.2],
        "spot": [21050.25],
    }

    key = "ce" if payload["drvOptionType"] == "CALL" else "pe"

    return {"data": {key: option_data}}


def _wait_for_terminal_status(client, job_id, timeout=10):
    """Polls until the job is BOTH terminal and not running - checking
    status alone races a rerun: right after POST returns, is_running
    is already True for the new run while status can still show the
    PREVIOUS run's COMPLETED/FAILED, since mark_job_started() hasn't
    landed in the background thread yet."""

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:

        response = client.get(f"/api/jobs/{job_id}")
        body = response.json()

        if body["status"] in ("COMPLETED", "FAILED") and not body["is_running"]:

            return body

        time.sleep(0.1)

    raise AssertionError(f"Job {job_id} did not reach a terminal status in {timeout}s")


def test_web_download_runs_the_real_pipeline_end_to_end():

    original_fetch = RollingOptionAPI.fetch
    RollingOptionAPI.fetch = fake_fetch

    try:

        with TestClient(server_module.app) as client:

            response = client.post(
                "/api/jobs",
                json={
                    "underlying": "NIFTY",
                    "expiry_type": "MONTH",
                    "option_types": ["CALL"],
                    "start_date": "2025-01-01",
                    "end_date": "2025-01-01",
                    "job_id": JOB_ID,
                },
            )

            assert response.status_code == 202

            body = _wait_for_terminal_status(client, JOB_ID)

            assert body["status"] == "COMPLETED"
            assert body["completed_batches"] == UNITS_PER_OPTION_TYPE
            assert body["failed_batches"] == 0
            assert body["total_rows"] == UNITS_PER_OPTION_TYPE
            assert body["percent_complete"] == 100.0
            assert body["is_running"] is False

            repo = server_module.app.state.job_runner.engine.repo

            rows = repo.query(
                "SELECT close FROM option_data WHERE symbol = 'NIFTY' "
                "AND trade_date = DATE '2025-01-01' AND option_type = 'CALL' "
                "AND close = 102.5 LIMIT 1"
            )

            assert len(rows) == 1

    finally:

        RollingOptionAPI.fetch = original_fetch


def test_web_download_with_parquet_output_dir_writes_the_partitioned_file():

    original_fetch = RollingOptionAPI.fetch
    RollingOptionAPI.fetch = fake_fetch

    try:

        with TestClient(server_module.app) as client:

            response = client.post(
                "/api/jobs",
                json={
                    "underlying": "NIFTY",
                    "expiry_type": "MONTH",
                    "option_types": ["CALL"],
                    "start_date": "2025-01-01",
                    "end_date": "2025-01-01",
                    "job_id": PARQUET_JOB_ID,
                    "parquet_output_dir": str(PARQUET_OUTPUT_DIR),
                },
            )

            assert response.status_code == 202

            body = _wait_for_terminal_status(client, PARQUET_JOB_ID)

            assert body["status"] == "COMPLETED"

            repo = server_module.app.state.job_runner.engine.repo

            job = repo.get_job(PARQUET_JOB_ID)
            assert job["parquet_output_dir"] == str(PARQUET_OUTPUT_DIR)

    finally:

        RollingOptionAPI.fetch = original_fetch

    partition_path = (
        PARQUET_OUTPUT_DIR / "underlying=NIFTY" / "year=2025" / "month=01"
        / "option_data.parquet"
    )

    assert partition_path.exists()

    result = pd.read_parquet(partition_path, engine="pyarrow")

    assert (result["close"] == 102.5).any()


if __name__ == "__main__":

    test_web_download_runs_the_real_pipeline_end_to_end()
    test_web_download_with_parquet_output_dir_writes_the_partitioned_file()

    print("Web end-to-end test passed")
