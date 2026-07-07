"""
Download Planner
"""

from datetime import datetime, timedelta

from app.models.download_batch import DownloadBatch
from app.models.job import DownloadJob


class DownloadPlanner:

    MAX_DAYS_PER_REQUEST = 30

    def create_plan(self, job: DownloadJob):

        batches = []

        start = datetime.strptime(job.start_date, "%Y-%m-%d")
        end = datetime.strptime(job.end_date, "%Y-%m-%d")

        batch_number = 1

        while start <= end:

            batch_end = min(
                start + timedelta(days=self.MAX_DAYS_PER_REQUEST - 1),
                end,
            )

            batches.append(
                DownloadBatch(
                    batch_number=batch_number,
                    from_date=start.strftime("%Y-%m-%d"),
                    to_date=batch_end.strftime("%Y-%m-%d"),
                )
            )

            batch_number += 1
            start = batch_end + timedelta(days=1)

        return batches