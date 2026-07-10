"""
Data Quality Checker

Audits the data a job just downloaded (or resumed) after it finishes.
This is not a replacement for DataValidator, which checks a single
batch's DataFrame before insert - some problems only show up once
data from many batches has landed in the database (a whole calendar
day short on rows, or two jobs whose date ranges happened to overlap
leaving duplicate candles behind), which is what this class looks
for. Runs automatically at the end of DownloadEngine.execute() and
only logs its findings - it never raises or blocks a job.
"""

from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median

import pandas as pd

from app.config.logging_config import get_logger
from app.constants.trading_calendar import is_trading_day
from app.database.repository import Repository
from app.models.job import DownloadJob
from app.models.quality_report import QualityReport

logger = get_logger()


class QualityChecker:

    # A day with fewer than this fraction of the recent median row
    # count for its symbol/expiry_flag is flagged as anomalously thin
    # (e.g. a partial download, or a narrower strike range than the
    # rest of the dataset).
    ROW_COUNT_ANOMALY_RATIO = 0.5

    # How many prior trading days to use as the row-count baseline.
    BASELINE_WINDOW_DAYS = 15

    # A baseline built from fewer days than this isn't trustworthy
    # (e.g. the very first job ever run for a symbol/expiry_flag).
    MIN_BASELINE_DAYS = 5

    def __init__(self, repo: Repository):

        self.repo = repo

    def check(self, job: DownloadJob) -> QualityReport:

        report = QualityReport(job_id=job.job_id)

        report.calendar_gaps = self._check_calendar_gaps(job)
        report.duplicate_groups = self._check_duplicates(job)
        report.row_count_anomalies = self._check_row_count_anomalies(job)
        report.parquet_mismatch = self._check_parquet_parity(job)

        self._log(report)

        return report

    @staticmethod
    def _parse(value: str) -> date:

        return datetime.strptime(value, "%Y-%m-%d").date()

    def _check_calendar_gaps(self, job: DownloadJob) -> list[date]:

        start = self._parse(job.start_date)
        end = self._parse(job.end_date)

        expected_trading_days = set()

        cursor = start

        while cursor <= end:

            if is_trading_day(cursor):

                expected_trading_days.add(cursor)

            cursor += timedelta(days=1)

        actual = set(
            self.repo.get_trade_dates(
                job.underlying, job.expiry_type, job.start_date, job.end_date
            )
        )

        return sorted(expected_trading_days - actual)

    def _check_duplicates(self, job: DownloadJob) -> int:

        return self.repo.get_duplicate_timestamp_count(
            job.underlying, job.expiry_type, job.start_date, job.end_date
        )

    def _check_row_count_anomalies(self, job: DownloadJob) -> list[tuple]:

        baseline = self.repo.get_recent_daily_row_counts(
            job.underlying,
            job.expiry_type,
            before_date=job.start_date,
            limit=self.BASELINE_WINDOW_DAYS,
        )

        if len(baseline) < self.MIN_BASELINE_DAYS:

            return []

        baseline_median = median(count for _, count in baseline)

        threshold = baseline_median * self.ROW_COUNT_ANOMALY_RATIO

        job_days = self.repo.get_daily_row_counts(
            job.underlying, job.expiry_type, job.start_date, job.end_date
        )

        return [
            (trade_date, count, baseline_median)
            for trade_date, count in job_days
            if count < threshold
        ]

    def _check_parquet_parity(self, job: DownloadJob) -> dict | None:

        if not job.parquet_output_dir:

            return None

        db_rows = self.repo.get_row_count(
            job.underlying, job.expiry_type, job.start_date, job.end_date
        )

        parquet_rows = self._parquet_row_count(job)

        if db_rows == parquet_rows:

            return None

        return {"db_rows": db_rows, "parquet_rows": parquet_rows}

    def _parquet_row_count(self, job: DownloadJob) -> int:

        start = self._parse(job.start_date)
        end = self._parse(job.end_date)

        months = set()

        cursor = start.replace(day=1)

        while cursor <= end:

            months.add((cursor.year, cursor.month))

            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)

        root = Path(job.parquet_output_dir) / f"underlying={job.underlying}"

        total = 0

        for year, month in months:

            partition = root / f"year={year:04d}" / f"month={month:02d}" / "option_data.parquet"

            if not partition.exists():

                continue

            partition_df = pd.read_parquet(
                partition, columns=["expiry_flag", "trade_date"]
            )

            trade_date = pd.to_datetime(partition_df["trade_date"])

            in_range = (
                (partition_df["expiry_flag"] == job.expiry_type)
                & (trade_date >= pd.Timestamp(start))
                & (trade_date <= pd.Timestamp(end))
            )

            total += int(in_range.sum())

        return total

    @staticmethod
    def _log(report: QualityReport):

        if not report.has_issues:

            logger.info(f"Quality check ({report.job_id}): no issues found.")

            return

        if report.calendar_gaps:

            sample = ", ".join(str(d) for d in report.calendar_gaps[:10])

            more = f" (+{len(report.calendar_gaps) - 10} more)" if len(report.calendar_gaps) > 10 else ""

            logger.warning(
                f"Quality check ({report.job_id}): {len(report.calendar_gaps)} "
                f"NSE/BSE trading day(s) with no data in this range (may be "
                f"before the instrument's real data starts, or years outside "
                f"the maintained holiday calendar are treated as all-trading, "
                f"which can also produce false positives): {sample}{more}"
            )

        if report.duplicate_groups:

            logger.warning(
                f"Quality check ({report.job_id}): {report.duplicate_groups} "
                "duplicate-timestamp group(s) found in the database for "
                "this range."
            )

        if report.row_count_anomalies:

            sample = ", ".join(
                f"{trade_date} ({count} rows vs ~{int(baseline)} baseline)"
                for trade_date, count, baseline in report.row_count_anomalies[:10]
            )

            logger.warning(
                f"Quality check ({report.job_id}): "
                f"{len(report.row_count_anomalies)} day(s) with row counts "
                f"far below the recent baseline: {sample}"
            )

        if report.parquet_mismatch:

            logger.warning(
                f"Quality check ({report.job_id}): Parquet/DuckDB row count "
                f"mismatch for this range - DB={report.parquet_mismatch['db_rows']} "
                f"Parquet={report.parquet_mismatch['parquet_rows']}"
            )
