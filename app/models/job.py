"""
Download Job Model
"""

from dataclasses import dataclass
from datetime import datetime

from app.models.enums.job_status import JobStatus


@dataclass
class DownloadJob:

    job_id: str

    underlying: str

    expiry_type: str

    option_types: list[str]

    strike_from: int

    strike_to: int

    start_date: str

    end_date: str

    created_at: datetime

    status: JobStatus = JobStatus.PENDING

    parquet_output_dir: str | None = None