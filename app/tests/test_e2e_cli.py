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

from app.api.rolling_option import RollingOptionAPI
from app.database.repository import Repository
from app.main import main

JOB_ID = "JOB-E2E-CLI-TEST"


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
            "--strike-from", "0",
            "--strike-to", "0",
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
    assert job["completed_batches"] == 1
    assert job["failed_batches"] == 0
    assert job["total_rows"] == 1

    rows = repo.query(
        "SELECT close FROM option_data WHERE symbol = 'NIFTY' "
        "AND trade_date = DATE '2025-01-01' AND option_type = 'CALL' "
        "AND close = 102.5 LIMIT 1"
    )

    assert len(rows) == 1


if __name__ == "__main__":

    test_cli_download_runs_the_real_pipeline_end_to_end()

    print("CLI end-to-end test passed")
