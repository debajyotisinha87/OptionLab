"""
Download Manager

Creates download batches for the Dhan Rolling Option API.
"""

from datetime import datetime, timedelta


class DownloadManager:

    MAX_DAYS = 30

    @staticmethod
    def split_date_range(start_date: str, end_date: str):

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        ranges = []

        current = start

        while current <= end:

            batch_end = min(
                current + timedelta(days=29),
                end,
            )

            ranges.append(
                (
                    current.strftime("%Y-%m-%d"),
                    batch_end.strftime("%Y-%m-%d"),
                )
            )

            current = batch_end + timedelta(days=1)

        return ranges