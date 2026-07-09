"""
End-to-End CLI Test (TASK-024)

Exercises the CLI's full, real download pipeline - argv parsing ->
DownloadJob -> DownloadPlanner -> PayloadBuilder -> DownloadEngine ->
DownloadService -> DataNormalizer -> DataValidator -> Repository ->
the real database/optionlab.duckdb - unlike every other CLI/engine
test in this suite, DownloadEngine itself is NOT faked here. Only the
outermost network boundary (RollingOptionAPI.fetch) is stubbed, so no
real DhanHQ call is made. Uses a distinctive job_id so reruns don't
collide with other tests' data, and is itself idempotent to rerun
(the manifest's completed-batch skip means a second run doesn't
re-download or re-insert).
"""

from pathlib import Path

import pandas as pd

from app.api.rolling_option import RollingOptionAPI
from app.builders.payload_builder import PayloadBuilder
from app.database.repository import Repository
from app.main import main

# Every download always covers the full ATM-10..ATM+10 range (21
# strike offsets); with a single option type, that's 21 units in 1 batch.
UNITS_PER_OPTION_TYPE = PayloadBuilder.MAX_STRIKE_OFFSET - PayloadBuilder.MIN_STRIKE_OFFSET + 1

JOB_ID = "JOB-E2E-CLI-TEST-FULLRANGE"
PARQUET_JOB_ID = "JOB-E2E-CLI-PARQUET-TEST-FULLRANGE"

# A fixed (not per-run-random) location: check_job_reusable() locks
# parquet_output_dir as part of a job_id's identity, and a completed
# unit is skipped (never re-downloaded/re-written) on rerun, so this
# path must stay identical - and the file left behind untouched -
# across repeated runs for this test to remain idempotent.
PARQUET_OUTPUT_DIR = Path("data") / "test_e2e_parquet_cli"


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


def test_cli_download_runs_the_real_pipeline_end_to_end():

    original_fetch = RollingOptionAPI.fetch
    RollingOptionAPI.fetch = fake_fetch

    try:

        exit_code = main([
            "download",
            "--underlying", "NIFTY",
            "--expiry-type", "MONTH",
            "--option-types", "CALL",
            "--start-date", "2025-01-01",
            "--end-date", "2025-01-01",
            "--job-id", JOB_ID,
        ])

        assert exit_code == 0

    finally:

        RollingOptionAPI.fetch = original_fetch

    repo = Repository()

    job = repo.get_job(JOB_ID)

    assert job is not None
    assert job["status"] == "COMPLETED"
    assert job["completed_batches"] == UNITS_PER_OPTION_TYPE
    assert job["failed_batches"] == 0
    assert job["total_rows"] == UNITS_PER_OPTION_TYPE

    rows = repo.query(
        "SELECT close FROM option_data WHERE symbol = 'NIFTY' "
        "AND trade_date = DATE '2025-01-01' AND option_type = 'CALL' "
        "AND close = 102.5 LIMIT 1"
    )

    assert len(rows) == 1


def test_cli_download_with_save_parquet_to_writes_the_partitioned_file():

    original_fetch = RollingOptionAPI.fetch
    RollingOptionAPI.fetch = fake_fetch

    try:

        exit_code = main([
            "download",
            "--underlying", "NIFTY",
            "--expiry-type", "MONTH",
            "--option-types", "CALL",
            "--start-date", "2025-01-01",
            "--end-date", "2025-01-01",
            "--job-id", PARQUET_JOB_ID,
            "--save-parquet-to", str(PARQUET_OUTPUT_DIR),
        ])

        assert exit_code == 0

    finally:

        RollingOptionAPI.fetch = original_fetch

    repo = Repository()

    job = repo.get_job(PARQUET_JOB_ID)

    assert job is not None
    assert job["parquet_output_dir"] == str(PARQUET_OUTPUT_DIR)

    partition_path = (
        PARQUET_OUTPUT_DIR / "underlying=NIFTY" / "year=2025" / "month=01"
        / "option_data.parquet"
    )

    assert partition_path.exists()

    result = pd.read_parquet(partition_path, engine="pyarrow")

    assert (result["close"] == 102.5).any()


if __name__ == "__main__":

    test_cli_download_runs_the_real_pipeline_end_to_end()
    test_cli_download_with_save_parquet_to_writes_the_partitioned_file()

    print("CLI end-to-end test passed")
