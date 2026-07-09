"""
Download Result
"""

from dataclasses import dataclass

import pandas as pd


@dataclass
class DownloadResult:

    success: bool

    dataframe: pd.DataFrame | None

    message: str