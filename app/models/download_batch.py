"""
Download Batch Model
"""

from dataclasses import dataclass


@dataclass
class DownloadBatch:

    batch_number: int

    from_date: str

    to_date: str