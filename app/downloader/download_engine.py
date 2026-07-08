"""
Download Engine
"""

from app.builders.payload_builder import PayloadBuilder
from app.models.download_batch import DownloadBatch
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

    def run(self, job: DownloadJob):

        print("=" * 60)
        print(f"Starting Job : {job.job_id}")
        print("=" * 60)

        batches = self.planner.create_plan(job)

        print(f"Total Batches : {len(batches)}")

        for batch in batches:
            self.process_batch(job, batch)

        print("=" * 60)
        print("Job Completed")
        print("=" * 60)

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
