"""
Download Engine
"""

from app.builders.payload_builder import PayloadBuilder
from app.config.logging_config import get_logger
from app.constants.underlyings import SUPPORTED_UNDERLYINGS
from app.downloader.progress_reporter import ProgressReporter
from app.models.download_batch import DownloadBatch
from app.models.enums.job_status import JobStatus
from app.models.job import DownloadJob
from app.planner.download_planner import DownloadPlanner
from app.services.download_service import DownloadService

logger = get_logger()


class DownloadEngine:

    COMPLETED_STATUS = "COMPLETED"

    MAX_RETRIES = 3

    def __init__(self):

        self.planner = DownloadPlanner()
        self.service = DownloadService()
        self.repo = self.service.repo
        self.progress = ProgressReporter()

        self.repo.create_option_data_table()
        self.repo.create_download_manifest_table()
        self.repo.create_download_jobs_table()

    def run(self, job: DownloadJob):

        self.validate_job(job)

        self.repo.save_job(
            job_id=job.job_id,
            underlying=job.underlying,
            instrument=PayloadBuilder.INSTRUMENT,
            expiry_type=job.expiry_type,
            option_types=",".join(job.option_types),
            strike_from=job.strike_from,
            strike_to=job.strike_to,
            interval=PayloadBuilder.INTERVAL,
            start_date=job.start_date,
            end_date=job.end_date,
            created_at=job.created_at,
            parquet_output_dir=job.parquet_output_dir,
        )

        self.execute(job)

    def resume(self, job_id: str):

        record = self.repo.get_job(job_id)

        if record is None:

            raise ValueError(f"Unknown job_id: {job_id}")

        if record["status"] == self.COMPLETED_STATUS:

            logger.info(f"Job {job_id} is already completed. Nothing to resume.")

            return

        job = self.build_job(record)

        self.validate_job(job)

        reconciled = self.repo.reconcile_stale_running_batches(job_id)

        if not self.has_retryable_work(job):

            # Only re-close the job if reconciliation changed something, or
            # it was never actually closed out (e.g. crashed before its
            # first execute() finished) - otherwise this repeats forever on
            # an already-terminal FAILED job, rewriting completed_at every
            # time someone calls resume() on it.
            if reconciled or record["status"] not in (self.COMPLETED_STATUS, "FAILED"):

                self.finish_job(job_id)

            logger.info(f"Job {job_id} has no retryable work left. Nothing to resume.")

            return

        logger.info(f"Resuming Job : {job_id}")

        self.execute(job)

    def load_job(self, job_id: str) -> DownloadJob:

        record = self.repo.get_job(job_id)

        if record is None:

            raise ValueError(f"Unknown job_id: {job_id}")

        return self.build_job(record)

    @staticmethod
    def build_job(record: dict) -> DownloadJob:

        return DownloadJob(
            job_id=record["job_id"],
            underlying=record["underlying"],
            expiry_type=record["expiry_type"],
            option_types=record["option_types"].split(","),
            strike_from=record["strike_from"],
            strike_to=record["strike_to"],
            start_date=str(record["start_date"]),
            end_date=str(record["end_date"]),
            created_at=record["created_at"],
            status=JobStatus(record["status"]),
            parquet_output_dir=record.get("parquet_output_dir"),
        )

    @staticmethod
    def validate_job(job: DownloadJob):
        """Validates strike-range/underlying invariants that aren't
        enforced by the DownloadJob dataclass itself. Both run() and
        resume() call this before any manifest row is created or the
        job is marked RUNNING - has_retryable_work()'s strike loop
        would otherwise treat an invalid range as silently "no work",
        and a bad underlying would only surface deep inside execute()
        (after mark_job_started()), leaving the job stuck in RUNNING
        forever since finish_job() is never reached on an unhandled
        exception."""

        if job.underlying not in SUPPORTED_UNDERLYINGS:

            raise ValueError(f"Unsupported underlying: {job.underlying}")

        if job.strike_from > job.strike_to:

            raise ValueError(
                f"strike_from ({job.strike_from}) must be <= "
                f"strike_to ({job.strike_to})"
            )

        for offset in (job.strike_from, job.strike_to):

            if (
                offset < PayloadBuilder.MIN_STRIKE_OFFSET
                or offset > PayloadBuilder.MAX_STRIKE_OFFSET
            ):

                raise ValueError(
                    f"strike offset {offset} is outside DhanHQ's "
                    f"supported range ({PayloadBuilder.MIN_STRIKE_OFFSET} "
                    f"to {PayloadBuilder.MAX_STRIKE_OFFSET})"
                )

    @staticmethod
    def strike_offsets(job: DownloadJob) -> range:
        """The single source of truth for which strike offsets a job
        covers, so the count (execute()) and the iteration
        (process_batch()/has_retryable_work()) can never drift apart."""

        return range(job.strike_from, job.strike_to + 1)

    @classmethod
    def iter_units(cls, job: DownloadJob):
        """Yields (option_type, strike_offset) for every unit a single
        batch must download, shared by process_batch() and
        has_retryable_work() so their iteration order/shape can't
        diverge."""

        for option_type in job.option_types:

            for strike_offset in cls.strike_offsets(job):

                yield option_type, strike_offset

    def execute(self, job: DownloadJob):

        logger.info("=" * 60)
        logger.info(f"Starting Job : {job.job_id}")
        logger.info("=" * 60)

        self.repo.reconcile_stale_running_batches(job.job_id)

        self.repo.mark_job_started(job.job_id)

        batches = self.planner.create_plan(job)

        units_per_batch = len(job.option_types) * len(self.strike_offsets(job))

        total_units = len(batches) * units_per_batch

        self.repo.set_job_total_batches(job.job_id, total_units)

        logger.info(f"Total Batches : {len(batches)}")

        already_inserted_rows = self.repo.get_job_progress(job.job_id)["total_rows"]

        self.progress.reset(
            total_units=total_units,
            description=f"Job {job.job_id}",
            initial_rows=already_inserted_rows,
        )

        try:

            for batch in batches:
                self.process_batch(job, batch)

        finally:

            self.progress.close()

        self.finish_job(job.job_id)

        logger.info("=" * 60)
        logger.info("Job Completed")
        logger.info("=" * 60)

    def finish_job(self, job_id: str):

        progress = self.repo.get_job_progress(job_id)

        if progress["failed_batches"] > 0:

            self.repo.mark_job_failed(job_id, **progress)

            return

        self.repo.mark_job_completed(job_id, **progress)

    def process_batch(
        self,
        job: DownloadJob,
        batch: DownloadBatch,
    ):

        logger.info("-" * 60)
        logger.info(f"Processing Batch : {batch.batch_number}")
        logger.info(
            f"Date Range       : {batch.from_date} -> {batch.to_date}"
        )
        logger.info("-" * 60)

        for option_type, strike_offset in self.iter_units(job):

            self.process_option_type(
                job=job,
                batch=batch,
                option_type=option_type,
                strike_offset=strike_offset,
            )

        logger.info("Batch completed.")

    def process_option_type(
        self,
        job: DownloadJob,
        batch: DownloadBatch,
        option_type: str,
        strike_offset: int,
    ):

        strike_label = PayloadBuilder.strike_label(strike_offset)

        logger.info(f"Downloading {option_type} ({strike_label})...")

        payload = PayloadBuilder.build(
            job=job,
            batch=batch,
            option_type=option_type,
            strike_offset=strike_offset,
        )

        if self.is_download_completed(
            job=job,
            batch=batch,
            option_type=option_type,
            strike_offset=strike_offset,
        ):

            logger.info(
                f"Skipping {option_type} ({strike_label}): already completed."
            )

            self.progress.record()

            return

        if self.is_retry_limit_exceeded(
            job=job,
            batch=batch,
            option_type=option_type,
            strike_offset=strike_offset,
        ):

            logger.warning(
                f"Skipping {option_type} ({strike_label}): "
                f"retry limit ({self.MAX_RETRIES}) exceeded."
            )

            self.progress.record()

            return

        self.repo.create_manifest_entry(
            job_id=job.job_id,
            batch_number=batch.batch_number,
            underlying=job.underlying,
            instrument=payload["instrument"],
            expiry_type=job.expiry_type,
            option_type=option_type,
            strike_offset=strike_offset,
            interval=payload["interval"],
            from_date=batch.from_date,
            to_date=batch.to_date,
        )

        self.repo.mark_batch_started(
            job_id=job.job_id,
            batch_number=batch.batch_number,
            option_type=option_type,
            strike_offset=strike_offset,
        )

        result = self.service.download(
            payload, parquet_output_dir=job.parquet_output_dir
        )

        if result["success"]:

            self.repo.mark_batch_completed(
                job_id=job.job_id,
                batch_number=batch.batch_number,
                option_type=option_type,
                strike_offset=strike_offset,
                downloaded_rows=result["downloaded_rows"],
                inserted_rows=result["inserted_rows"],
            )

            self.progress.record(inserted_rows=result["inserted_rows"])

            return

        self.repo.mark_batch_failed(
            job_id=job.job_id,
            batch_number=batch.batch_number,
            option_type=option_type,
            strike_offset=strike_offset,
            error_message=result["error"],
        )

        logger.error(
            f"{option_type} ({strike_label}) download failed: "
            f"{result['error']}"
        )

        self.progress.record()

    def is_download_completed(
        self,
        job: DownloadJob,
        batch: DownloadBatch,
        option_type: str,
        strike_offset: int,
    ) -> bool:

        status = self.repo.get_manifest_status(
            job_id=job.job_id,
            batch_number=batch.batch_number,
            option_type=option_type,
            strike_offset=strike_offset,
        )

        return status == self.COMPLETED_STATUS

    def is_retry_limit_exceeded(
        self,
        job: DownloadJob,
        batch: DownloadBatch,
        option_type: str,
        strike_offset: int,
    ) -> bool:

        retry_count = self.repo.get_manifest_retry_count(
            job_id=job.job_id,
            batch_number=batch.batch_number,
            option_type=option_type,
            strike_offset=strike_offset,
        )

        return retry_count >= self.MAX_RETRIES

    def has_retryable_work(self, job: DownloadJob) -> bool:

        batches = self.planner.create_plan(job)

        for batch in batches:

            for option_type, strike_offset in self.iter_units(job):

                if self.is_download_completed(
                    job=job,
                    batch=batch,
                    option_type=option_type,
                    strike_offset=strike_offset,
                ):

                    continue

                if self.is_retry_limit_exceeded(
                    job=job,
                    batch=batch,
                    option_type=option_type,
                    strike_offset=strike_offset,
                ):

                    continue

                return True

        return False
