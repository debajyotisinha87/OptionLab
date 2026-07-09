"""
Sync Planner

Plans catch-up download jobs for the auto-sync feature: on each check,
compares the latest data actually downloaded (per underlying/expiry
type) against today and builds fresh DownloadJob(s) covering only the
gap - reusing the existing DownloadJob/manifest model rather than
mutating a completed job's date range, since DownloadEngine.resume()
cannot extend a job past its original end_date.
"""

from datetime import datetime, timedelta

from app import validation
from app.builders.payload_builder import PayloadBuilder
from app.config.config import EXPORTS_DIR
from app.database.repository import Repository
from app.models.job import DownloadJob


class SyncPlanner:
    """Auto-sync is scoped to a fixed set of underlyings/expiry types
    (not user-configurable, unlike the manual download form) - each
    combo is planned independently since DhanHQ's data depth differs
    per underlying (verified empirically: NIFTY option data starts
    ~2023-01, SENSEX ~2023-06)."""

    UNDERLYINGS = ["NIFTY", "SENSEX"]

    EXPIRY_TYPES = ["WEEK", "MONTH"]

    OPTION_TYPES = ["CALL", "PUT"]

    # Conservative anchor for a first-ever backfill, deliberately
    # earlier than either underlying's real data start - the gap
    # before real data begins is absorbed by the existing "no data
    # returned" handling as a one-time, harmless cost, so this doesn't
    # need to track DhanHQ's actual boundary precisely.
    GENESIS_DATE = "2020-01-01"

    @staticmethod
    def _combos():

        for underlying in SyncPlanner.UNDERLYINGS:

            for expiry_type in SyncPlanner.EXPIRY_TYPES:

                yield underlying, expiry_type

    @staticmethod
    def status(repo: Repository) -> dict:
        """Per-combo latest_date/up_to_date plus an overall up_to_date
        flag. Pure DB read - works even if the DhanHQ token is
        currently invalid, since it doesn't call the API."""

        today = datetime.now().date()

        combos = []

        for underlying, expiry_type in SyncPlanner._combos():

            latest = repo.get_latest_trade_date(underlying, expiry_type)

            up_to_date = latest is not None and latest >= today

            combos.append({
                "underlying": underlying,
                "expiry_type": expiry_type,
                "latest_date": latest.isoformat() if latest else None,
                "up_to_date": up_to_date,
            })

        return {
            "combos": combos,
            "up_to_date": all(combo["up_to_date"] for combo in combos),
        }

    @staticmethod
    def plan_jobs(repo: Repository) -> list[DownloadJob]:
        """Builds one DownloadJob per (underlying, expiry_type) combo
        that has a gap between its latest downloaded data and today.
        Returns [] if everything is already current."""

        today = datetime.now().date()

        jobs = []

        for underlying, expiry_type in SyncPlanner._combos():

            latest = repo.get_latest_trade_date(underlying, expiry_type)

            if latest is None:

                start_date = datetime.strptime(
                    SyncPlanner.GENESIS_DATE, validation.DATE_FORMAT
                ).date()

            else:

                start_date = latest + timedelta(days=1)

            if start_date > today:

                continue

            start_date_str = start_date.strftime(validation.DATE_FORMAT)
            end_date_str = today.strftime(validation.DATE_FORMAT)

            job_id = (
                f"{underlying}-SYNC-{expiry_type}-"
                f"{start_date_str}-{end_date_str}"
            )

            jobs.append(DownloadJob(
                job_id=job_id,
                underlying=underlying,
                expiry_type=expiry_type,
                option_types=list(SyncPlanner.OPTION_TYPES),
                strike_from=PayloadBuilder.MIN_STRIKE_OFFSET,
                strike_to=PayloadBuilder.MAX_STRIKE_OFFSET,
                start_date=start_date_str,
                end_date=end_date_str,
                created_at=datetime.now(),
                parquet_output_dir=str(EXPORTS_DIR),
            ))

        return jobs
