"""
Download Engine
"""

from app.builders.payload_builder import PayloadBuilder
from app.models.download_batch import DownloadBatch
from app.models.enums.job_status import JobStatus
from app.models.job import DownloadJob
from app.planner.download_planner import DownloadPlanner
from app.services.download_service import DownloadService


class DownloadEngine:

    COMPLETED_STATUS = "COMPLETED"

    DEFAULT_STRIKE_OFFSET = 0

    def __init__(self):

        self.planner = DownloadPlanner()
        self.service = DownloadService()
        self.repo = self.service.repo

        self.repo.create_option_data_table()
        self.repo.create_download_manifest_table()
        self.repo.create_download_jobs_table()

    def run(self, job: DownloadJob):

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
        )

        self.execute(job)

    def resume(self, job_id: str):

        record = self.repo.get_job(job_id)

        if record is None:

            raise ValueError(f"Unknown job_id: {job_id}")

        if record["status"] == self.COMPLETED_STATUS:

            print(f"Job {job_id} is already completed. Nothing to resume.")

            return

        job = self.build_job(record)

        print(f"Resuming Job : {job_id}")

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
        )

    def execute(self, job: DownloadJob):

        print("=" * 60)
        print(f"Starting Job : {job.job_id}")
        print("=" * 60)

        self.repo.mark_job_started(job.job_id)

        batches = self.planner.create_plan(job)

        self.repo.set_job_total_batches(
            job.job_id,
            len(batches) * len(job.option_types),
        )

        print(f"Total Batches : {len(batches)}")

        for batch in batches:
            self.process_batch(job, batch)

        self.finish_job(job.job_id)

        print("=" * 60)
        print("Job Completed")
        print("=" * 60)

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

        print("-" * 60)
        print(f"Processing Batch : {batch.batch_number}")
        print(f"Date Range       : {batch.from_date} -> {batch.to_date}")
        print("-" * 60)

        for option_type in job.option_types:

            self.process_option_type(
                job=job,
                batch=batch,
                option_type=option_type,
            )

        print("Batch completed.\n")

    def process_option_type(
        self,
        job: DownloadJob,
        batch: DownloadBatch,
        option_type: str,
    ):

        print(f"Downloading {option_type}...")

        payload = PayloadBuilder.build(
            job=job,
            batch=batch,
            option_type=option_type,
        )

        strike_offset = self.DEFAULT_STRIKE_OFFSET

        if self.is_download_completed(
            job=job,
            batch=batch,
            option_type=option_type,
            strike_offset=strike_offset,
        ):

            print(f"Skipping {option_type}: already completed.")

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

        result = self.service.download(payload)

        if result["success"]:

            self.repo.mark_batch_completed(
                job_id=job.job_id,
                batch_number=batch.batch_number,
                option_type=option_type,
                strike_offset=strike_offset,
                downloaded_rows=result["downloaded_rows"],
                inserted_rows=result["inserted_rows"],
            )

            return

        self.repo.mark_batch_failed(
            job_id=job.job_id,
            batch_number=batch.batch_number,
            option_type=option_type,
            strike_offset=strike_offset,
            error_message=result["error"],
        )

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
