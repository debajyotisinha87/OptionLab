from datetime import date, timedelta

from app.autosync.sync_planner import SyncPlanner
from app.builders.payload_builder import PayloadBuilder
from app.config.config import EXPORTS_DIR


class FakeRepository:

    def __init__(self, latest_dates=None):

        self.latest_dates = latest_dates or {}

    def get_latest_trade_date(self, symbol, expiry_flag):

        return self.latest_dates.get((symbol, expiry_flag))


def test_plan_jobs_uses_genesis_date_when_no_existing_data():

    repo = FakeRepository()

    jobs = SyncPlanner.plan_jobs(repo)

    assert len(jobs) == 4

    for job in jobs:

        assert job.start_date == SyncPlanner.GENESIS_DATE
        assert job.option_types == ["CALL", "PUT"]
        assert job.strike_from == PayloadBuilder.MIN_STRIKE_OFFSET
        assert job.strike_to == PayloadBuilder.MAX_STRIKE_OFFSET
        assert job.parquet_output_dir == str(EXPORTS_DIR)


def test_plan_jobs_starts_the_day_after_the_latest_downloaded_date():

    latest = date.today() - timedelta(days=5)

    repo = FakeRepository(latest_dates={("NIFTY", "WEEK"): latest})

    jobs = SyncPlanner.plan_jobs(repo)

    nifty_week_job = next(
        job for job in jobs
        if job.underlying == "NIFTY" and job.expiry_type == "WEEK"
    )

    expected_start = (latest + timedelta(days=1)).strftime("%Y-%m-%d")

    assert nifty_week_job.start_date == expected_start
    assert nifty_week_job.end_date == date.today().strftime("%Y-%m-%d")


def test_plan_jobs_skips_a_combo_already_up_to_date():

    today = date.today()

    repo = FakeRepository(latest_dates={("NIFTY", "WEEK"): today})

    jobs = SyncPlanner.plan_jobs(repo)

    assert not any(
        job.underlying == "NIFTY" and job.expiry_type == "WEEK" for job in jobs
    )
    assert len(jobs) == 3


def test_plan_jobs_returns_empty_list_when_everything_up_to_date():

    today = date.today()

    latest_dates = {
        (underlying, expiry_type): today
        for underlying in SyncPlanner.UNDERLYINGS
        for expiry_type in SyncPlanner.EXPIRY_TYPES
    }

    repo = FakeRepository(latest_dates=latest_dates)

    assert SyncPlanner.plan_jobs(repo) == []


def test_status_reports_per_combo_and_overall_up_to_date():

    today = date.today()

    latest_dates = {
        (underlying, expiry_type): today
        for underlying in SyncPlanner.UNDERLYINGS
        for expiry_type in SyncPlanner.EXPIRY_TYPES
    }

    repo = FakeRepository(latest_dates=latest_dates)

    status = SyncPlanner.status(repo)

    assert status["up_to_date"] is True
    assert len(status["combos"]) == 4
    assert all(combo["up_to_date"] for combo in status["combos"])


def test_status_reports_not_up_to_date_when_a_combo_has_no_data():

    repo = FakeRepository()

    status = SyncPlanner.status(repo)

    assert status["up_to_date"] is False
    assert all(combo["latest_date"] is None for combo in status["combos"])


if __name__ == "__main__":

    test_plan_jobs_uses_genesis_date_when_no_existing_data()
    test_plan_jobs_starts_the_day_after_the_latest_downloaded_date()
    test_plan_jobs_skips_a_combo_already_up_to_date()
    test_plan_jobs_returns_empty_list_when_everything_up_to_date()
    test_status_reports_per_combo_and_overall_up_to_date()
    test_status_reports_not_up_to_date_when_a_combo_has_no_data()

    print("Sync planner tests passed")
