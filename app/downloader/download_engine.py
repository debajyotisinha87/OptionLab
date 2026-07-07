"""
Download Engine
"""

from app.builders.payload_builder import PayloadBuilder
from app.models.job import DownloadJob
from app.planner.download_planner import DownloadPlanner
from app.services.download_service import DownloadService


class DownloadEngine:

    def __init__(self):

        self.planner = DownloadPlanner()
        self.service = DownloadService()

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
        batch,
    ):

        print("-" * 60)
        print(f"Processing Batch : {batch.batch_number}")
        print(f"Date Range       : {batch.from_date} -> {batch.to_date}")
        print("-" * 60)

        for option_type in job.option_types:

            print(f"Downloading {option_type}...")

            payload = PayloadBuilder.build(
                job=job,
                batch=batch,
                option_type=option_type,
            )

            self.service.download(payload)

        print("Batch completed.\n")