import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from app.quality.quality_checker import QualityChecker
from app.models.job import DownloadJob


class FakeRepository:

    def __init__(
        self,
        trade_dates=None,
        duplicate_count=0,
        daily_row_counts=None,
        recent_daily_row_counts=None,
        db_row_count=0,
    ):

        self.trade_dates = trade_dates or []
        self.duplicate_count = duplicate_count
        self.daily_row_counts = daily_row_counts or []
        self.recent_daily_row_counts = recent_daily_row_counts or []
        self.db_row_count = db_row_count

    def get_trade_dates(self, symbol, expiry_flag, start_date, end_date):

        return self.trade_dates

    def get_duplicate_timestamp_count(self, symbol, expiry_flag, start_date, end_date):

        return self.duplicate_count

    def get_daily_row_counts(self, symbol, expiry_flag, start_date, end_date):

        return self.daily_row_counts

    def get_recent_daily_row_counts(self, symbol, expiry_flag, before_date, limit):

        return self.recent_daily_row_counts

    def get_row_count(self, symbol, expiry_flag, start_date, end_date):

        return self.db_row_count


def make_job(start_date, end_date, parquet_output_dir=None):

    return DownloadJob(
        job_id="TEST-JOB",
        underlying="NIFTY",
        expiry_type="MONTH",
        option_types=["CALL", "PUT"],
        strike_from=-10,
        strike_to=10,
        start_date=start_date,
        end_date=end_date,
        created_at=datetime.now(),
        parquet_output_dir=parquet_output_dir,
    )


def test_no_issues_when_all_weekdays_present_and_no_anomalies():

    job = make_job("2025-06-02", "2025-06-04")

    repo = FakeRepository(
        trade_dates=[date(2025, 6, 2), date(2025, 6, 3), date(2025, 6, 4)],
        recent_daily_row_counts=[(date(2025, 6, 1), 300)] * 5,
        daily_row_counts=[
            (date(2025, 6, 2), 300),
            (date(2025, 6, 3), 305),
            (date(2025, 6, 4), 295),
        ],
    )

    report = QualityChecker(repo).check(job)

    assert not report.has_issues


def test_detects_calendar_gaps():

    # 2025-06-02 (Mon) to 2025-06-04 (Wed): 3 weekdays expected, only 2 present.
    job = make_job("2025-06-02", "2025-06-04")

    repo = FakeRepository(trade_dates=[date(2025, 6, 2), date(2025, 6, 4)])

    report = QualityChecker(repo).check(job)

    assert report.calendar_gaps == [date(2025, 6, 3)]
    assert report.has_issues


def test_calendar_gaps_does_not_flag_a_known_nse_holiday():

    # Jan 23 2026 (Fri) -> Jan 26 (Mon, Republic Day) -> Jan 27 (Tue).
    # Missing Jan 26 is not a gap - it's a real NSE holiday.
    job = make_job("2026-01-23", "2026-01-27")

    repo = FakeRepository(trade_dates=[date(2026, 1, 23), date(2026, 1, 27)])

    report = QualityChecker(repo).check(job)

    assert report.calendar_gaps == []
    assert not report.has_issues


def test_detects_duplicate_timestamps():

    job = make_job("2025-06-02", "2025-06-04")

    repo = FakeRepository(
        trade_dates=[date(2025, 6, 2), date(2025, 6, 3), date(2025, 6, 4)],
        duplicate_count=3,
    )

    report = QualityChecker(repo).check(job)

    assert report.duplicate_groups == 3
    assert report.has_issues


def test_detects_row_count_anomaly_against_baseline():

    job = make_job("2025-06-02", "2025-06-02")

    repo = FakeRepository(
        trade_dates=[date(2025, 6, 2)],
        recent_daily_row_counts=[(date(2025, 5, 30 - i), 300) for i in range(5)],
        daily_row_counts=[(date(2025, 6, 2), 10)],
    )

    report = QualityChecker(repo).check(job)

    assert len(report.row_count_anomalies) == 1
    assert report.row_count_anomalies[0][0] == date(2025, 6, 2)
    assert report.row_count_anomalies[0][1] == 10
    assert report.has_issues


def test_skips_row_count_check_when_baseline_too_small():

    job = make_job("2025-06-02", "2025-06-02")

    repo = FakeRepository(
        trade_dates=[date(2025, 6, 2)],
        recent_daily_row_counts=[(date(2025, 6, 1), 300)],
        daily_row_counts=[(date(2025, 6, 2), 10)],
    )

    report = QualityChecker(repo).check(job)

    assert report.row_count_anomalies == []


def test_skips_parquet_check_when_no_parquet_dir():

    job = make_job("2025-06-02", "2025-06-02", parquet_output_dir=None)

    repo = FakeRepository(trade_dates=[date(2025, 6, 2)], db_row_count=999)

    report = QualityChecker(repo).check(job)

    assert report.parquet_mismatch is None


def _write_parquet_partition(temp_dir, underlying, year, month, rows):

    partition_dir = Path(temp_dir) / f"underlying={underlying}" / f"year={year:04d}" / f"month={month:02d}"
    partition_dir.mkdir(parents=True)

    df = pd.DataFrame(rows)
    df.to_parquet(partition_dir / "option_data.parquet", engine="pyarrow", index=False)


def test_detects_parquet_mismatch():

    temp_dir = tempfile.mkdtemp()

    try:
        _write_parquet_partition(
            temp_dir, "NIFTY", 2025, 6,
            rows=[
                {"expiry_flag": "MONTH", "trade_date": date(2025, 6, 2)},
                {"expiry_flag": "MONTH", "trade_date": date(2025, 6, 2)},
            ],
        )

        job = make_job("2025-06-02", "2025-06-02", parquet_output_dir=temp_dir)

        repo = FakeRepository(trade_dates=[date(2025, 6, 2)], db_row_count=5)

        report = QualityChecker(repo).check(job)

        assert report.parquet_mismatch == {"db_rows": 5, "parquet_rows": 2}
        assert report.has_issues

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_parquet_matches_reports_no_mismatch():

    temp_dir = tempfile.mkdtemp()

    try:
        _write_parquet_partition(
            temp_dir, "NIFTY", 2025, 6,
            rows=[
                {"expiry_flag": "MONTH", "trade_date": date(2025, 6, 2)},
                {"expiry_flag": "MONTH", "trade_date": date(2025, 6, 2)},
            ],
        )

        job = make_job("2025-06-02", "2025-06-02", parquet_output_dir=temp_dir)

        repo = FakeRepository(trade_dates=[date(2025, 6, 2)], db_row_count=2)

        report = QualityChecker(repo).check(job)

        assert report.parquet_mismatch is None

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_parquet_check_ignores_rows_from_a_different_expiry_flag_in_the_same_partition():

    # A monthly and weekly job for the same underlying/month share one
    # Parquet partition file - the mismatch check must only count rows
    # belonging to this job's own expiry_flag.
    temp_dir = tempfile.mkdtemp()

    try:
        _write_parquet_partition(
            temp_dir, "NIFTY", 2025, 6,
            rows=[
                {"expiry_flag": "MONTH", "trade_date": date(2025, 6, 2)},
                {"expiry_flag": "WEEK", "trade_date": date(2025, 6, 2)},
                {"expiry_flag": "WEEK", "trade_date": date(2025, 6, 2)},
            ],
        )

        job = make_job("2025-06-02", "2025-06-02", parquet_output_dir=temp_dir)

        repo = FakeRepository(trade_dates=[date(2025, 6, 2)], db_row_count=1)

        report = QualityChecker(repo).check(job)

        assert report.parquet_mismatch is None

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":

    test_no_issues_when_all_weekdays_present_and_no_anomalies()
    test_detects_calendar_gaps()
    test_calendar_gaps_does_not_flag_a_known_nse_holiday()
    test_detects_duplicate_timestamps()
    test_detects_row_count_anomaly_against_baseline()
    test_skips_row_count_check_when_baseline_too_small()
    test_skips_parquet_check_when_no_parquet_dir()
    test_detects_parquet_mismatch()
    test_parquet_matches_reports_no_mismatch()
    test_parquet_check_ignores_rows_from_a_different_expiry_flag_in_the_same_partition()

    print("All test_quality_checker tests passed.")
