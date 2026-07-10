"""
Data Quality Report
"""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class QualityReport:

    job_id: str

    calendar_gaps: list[date] = field(default_factory=list)

    duplicate_groups: int = 0

    row_count_anomalies: list[tuple] = field(default_factory=list)

    parquet_mismatch: dict | None = None

    @property
    def has_issues(self) -> bool:

        return bool(
            self.calendar_gaps
            or self.duplicate_groups
            or self.row_count_anomalies
            or self.parquet_mismatch
        )
