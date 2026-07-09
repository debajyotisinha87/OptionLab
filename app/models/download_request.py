"""
Download Request Model
"""

from dataclasses import dataclass


@dataclass
class DownloadRequest:

    symbol: str

    start_date: str

    end_date: str

    option_type: str

    strike: str

    expiry_flag: str = "MONTH"

    expiry_code: int = 1

    interval: int = 1