"""
End-to-End Sync Test

Exercises the auto-sync orchestration path for real: SyncPlanner.plan_jobs()
-> JobRunner.start_many() -> DownloadEngine.run() for each queued job,
through the actual POST /api/sync endpoint, with only
RollingOptionAPI.fetch stubbed (no real DhanHQ call). SyncPlanner's
UNDERLYINGS/EXPIRY_TYPES/GENESIS_DATES are temporarily narrowed to a
single, otherwise-untouched underlying (BANKNIFTY - every other e2e
test in this suite only ever uses NIFTY) and a 2-day genesis, so this
runs in seconds instead of the real ~3.5-year, 4-combo backfill.
"""

import time
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

import app.web.server as server_module
from app.api.rolling_option import RollingOptionAPI
from app.autosync.sync_planner import SyncPlanner
from app.constants.trading_calendar import expected_latest_trading_date
from app.database.repository import Repository

TEST_UNDERLYING = "BANKNIFTY"
TEST_EXPIRY_TYPE = "MONTH"


def _reset_test_data():
    """BANKNIFTY/MONTH is otherwise untouched by the rest of this test
    suite (every other e2e test only ever uses NIFTY), so it's safe to
    use as a throwaway combo - but unlike the other e2e tests' fixed
    job_id/date-range idempotency, a sync job's date range depends on
    "today", so leftover data from a previous run of this test would
    make status_before's "not up to date" assumption false on a
    same-day rerun. Constructed and dropped outside the TestClient's
    lifespan so it doesn't hold a second connection alongside it."""

    repo = Repository()

    repo.execute(f"DELETE FROM option_data WHERE symbol = '{TEST_UNDERLYING}'")
    repo.execute(
        f"DELETE FROM download_manifest WHERE job_id LIKE '{TEST_UNDERLYING}-SYNC-%'"
    )
    repo.execute(
        f"DELETE FROM download_jobs WHERE job_id LIKE '{TEST_UNDERLYING}-SYNC-%'"
    )


def fake_fetch(self, payload):
    """Unlike test_e2e_cli.py/test_e2e_web.py's fixed-timestamp fake
    (fine there - those always request the same single date), this one
    must return a row actually dated on the batch's toDate: SyncPlanner
    decides what to fetch next based on get_latest_trade_date(), so a
    fake response that doesn't reflect the requested date would make
    "up to date" unreachable regardless of how many batches run."""

    trade_date = datetime.strptime(payload["toDate"], "%Y-%m-%d")
    timestamp = int(trade_date.replace(hour=9, minute=15).timestamp())

    option_data = {
        "timestamp": [timestamp],
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


def _wait_for_sync_to_finish(client, timeout=60):

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:

        response = client.get("/api/sync-status")
        body = response.json()

        if body["queue"] is None:

            return body

        time.sleep(0.2)

    raise AssertionError(f"Sync did not finish within {timeout}s")


def test_sync_runs_the_real_pipeline_and_second_run_is_a_no_op():

    original_fetch = RollingOptionAPI.fetch
    original_underlyings = SyncPlanner.UNDERLYINGS
    original_expiry_types = SyncPlanner.EXPIRY_TYPES
    original_genesis = SyncPlanner.GENESIS_DATES
    original_auto_sync = server_module._auto_sync

    RollingOptionAPI.fetch = fake_fetch
    SyncPlanner.UNDERLYINGS = [TEST_UNDERLYING]
    SyncPlanner.EXPIRY_TYPES = [TEST_EXPIRY_TYPE]
    SyncPlanner.GENESIS_DATES = {
        TEST_UNDERLYING: (
            datetime.now().date() - timedelta(days=2)
        ).strftime("%Y-%m-%d")
    }
    # Real server startup fires _auto_sync() for real, in a background
    # thread racing this test's own explicit client.post("/api/sync")
    # calls - it would either double-trigger the sync (real DhanHQ
    # network call this test doesn't stub) or make the test's own
    # sync request lose the race and get a 409.
    server_module._auto_sync = lambda job_runner: None

    _reset_test_data()

    try:

        with TestClient(server_module.app) as client:

            status_before = client.get("/api/sync-status").json()
            assert status_before["up_to_date"] is False

            response = client.post("/api/sync")

            assert response.status_code == 202

            body = response.json()
            assert body["status"] == "started"
            assert len(body["job_ids"]) == 1
            assert body["job_ids"][0].startswith(
                f"{TEST_UNDERLYING}-SYNC-{TEST_EXPIRY_TYPE}-"
            )

            final_status = _wait_for_sync_to_finish(client)

            assert final_status["up_to_date"] is True

            repo = server_module.app.state.job_runner.engine.repo

            latest = repo.get_latest_trade_date(TEST_UNDERLYING, TEST_EXPIRY_TYPE)
            assert latest is not None
            assert latest == expected_latest_trading_date(datetime.now())

            # Second sync, same day: nothing left to fetch.
            second_response = client.post("/api/sync")

            assert second_response.status_code == 202
            assert second_response.json() == {"job_ids": [], "status": "up_to_date"}

    finally:

        RollingOptionAPI.fetch = original_fetch
        SyncPlanner.UNDERLYINGS = original_underlyings
        SyncPlanner.EXPIRY_TYPES = original_expiry_types
        SyncPlanner.GENESIS_DATES = original_genesis
        server_module._auto_sync = original_auto_sync

        _reset_test_data()


if __name__ == "__main__":

    test_sync_runs_the_real_pipeline_and_second_run_is_a_no_op()

    print("Sync end-to-end test passed")
