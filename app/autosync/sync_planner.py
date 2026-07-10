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
from app.constants.trading_calendar import expected_latest_trading_date
from app.database.repository import Repository
from app.models.job import DownloadJob


class SyncPlanner:
    """Auto-sync is scoped to a fixed set of underlyings/expiry types
    (not user-configurable, unlike the manual download form) - each
    combo is planned independently since DhanHQ's data depth differs
    per underlying (verified empirically by running a full first-ever
    backfill for each: NIFTY option data starts 2020-08-03 - that's
    DhanHQ's own coverage limit, not NIFTY's real listing date - and
    SENSEX starts 2023-05-15, matching BSE's real Sensex-options
    relaunch date)."""

    UNDERLYINGS = ["NIFTY", "SENSEX"]

    EXPIRY_TYPES = ["WEEK", "MONTH"]

    OPTION_TYPES = ["CALL", "PUT"]

    # Per-underlying anchor for a first-ever backfill. Using each
    # underlying's real data-start date (rather than one blanket date
    # for everything) avoids re-attempting thousands of known-empty
    # batches every time a genesis backfill runs or is resumed - a
    # 2020-01-01 blanket anchor for SENSEX alone cost ~1700 wasted API
    # calls and 20+ minutes retrying 2020-2023, before real data
    # starts in 2023-05.
    GENESIS_DATES = {
        "NIFTY": "2020-08-03",
        "SENSEX": "2023-05-15",
    }

    # Fallback for any underlying without a confirmed boundary above
    # (e.g. if UNDERLYINGS ever grows) - conservative and safe, just
    # not efficient, same as the old behavior.
    DEFAULT_GENESIS_DATE = "2020-01-01"

    @staticmethod
    def _combos():

        for underlying in SyncPlanner.UNDERLYINGS:

            for expiry_type in SyncPlanner.EXPIRY_TYPES:

                yield underlying, expiry_type

    @staticmethod
    def status(repo: Repository) -> dict:
        """Per-combo latest_date/up_to_date plus an overall up_to_date
        flag. Pure DB read - works even if the DhanHQ token is
        currently invalid, since it doesn't call the API.

        "up_to_date" compares against expected_latest_trading_date(),
        not raw calendar today - comparing against today is wrong on
        a weekend/holiday (nothing can ever be >= a date that will
        never have data) and wrong on a trading day before data is
        realistically expected to be published yet."""

        reference_date = expected_latest_trading_date(datetime.now())

        combos = []

        for underlying, expiry_type in SyncPlanner._combos():

            latest = repo.get_latest_trade_date(underlying, expiry_type)

            up_to_date = latest is not None and latest >= reference_date

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
        that has a gap between its latest downloaded data and the most
        recent trading session that should realistically have data by
        now. Returns [] if everything is already current. Capping at
        expected_latest_trading_date() rather than raw today also
        avoids querying DhanHQ for weekend/holiday dates that can
        never return anything."""

        reference_date = expected_latest_trading_date(datetime.now())

        jobs = []

        for underlying, expiry_type in SyncPlanner._combos():

            latest = repo.get_latest_trade_date(underlying, expiry_type)

            if latest is None:

                genesis_date = SyncPlanner.GENESIS_DATES.get(
                    underlying, SyncPlanner.DEFAULT_GENESIS_DATE
                )

                start_date = datetime.strptime(
                    genesis_date, validation.DATE_FORMAT
                ).date()

            else:

                start_date = latest + timedelta(days=1)

            if start_date > reference_date:

                continue

            start_date_str = start_date.strftime(validation.DATE_FORMAT)
            end_date_str = reference_date.strftime(validation.DATE_FORMAT)

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
