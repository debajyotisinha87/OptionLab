"""
Progress Reporter

Displays live download progress: percent complete, ETA, rows
downloaded, and download speed (rows/sec).

tqdm's animated bar auto-disables when stdout isn't a live terminal
(e.g. output redirected to a log file for an unattended/scheduled
run). When disabled, tqdm doesn't track its own internal state
(elapsed time, update count, postfix) at all, so this class tracks
everything itself and falls back to a plain-text summary line per
unit in that case - otherwise a logged run would show no progress
info whatsoever, defeating the point of this class for exactly the
unattended use case it needs to support.
"""

import sys
import time

from tqdm import tqdm


class ProgressReporter:

    def __init__(self):

        self.bar = None
        self.total_units = 0
        self.total_rows = 0
        self.session_rows = 0
        self.completed_units = 0
        self.start_time = None

    def reset(self, total_units: int, description: str, initial_rows: int = 0):
        """
        initial_rows seeds the displayed row count with rows already
        downloaded in a previous session (e.g. before a resume()), so
        the displayed total stays consistent with the bar's
        percent-complete, which always covers the whole job. The
        rows/sec rate is deliberately NOT seeded - it only reflects
        this session's throughput, since prior-session rows weren't
        downloaded in this session's elapsed time.
        """

        self.close()

        self.total_units = total_units
        self.total_rows = initial_rows
        self.session_rows = 0
        self.completed_units = 0
        self.start_time = time.monotonic()

        self.bar = tqdm(
            total=total_units,
            desc=description,
            unit="unit",
            ascii=True,
            file=sys.stdout,
            disable=None,
        )

    def record(self, inserted_rows: int = 0):

        if self.bar is None:

            return

        self.total_rows += inserted_rows
        self.session_rows += inserted_rows
        self.completed_units += 1

        elapsed = time.monotonic() - self.start_time

        rows_per_second = self.session_rows / elapsed if elapsed > 0 else 0.0

        self.bar.set_postfix(
            rows=self.total_rows,
            rows_per_sec=f"{rows_per_second:.1f}",
            refresh=False,
        )

        self.bar.update(1)

        if self.bar.disable:

            self.write(self._summary_line(elapsed, rows_per_second))

    def _summary_line(self, elapsed: float, rows_per_second: float) -> str:

        percent = (
            self.completed_units / self.total_units * 100
            if self.total_units
            else 0.0
        )

        remaining_units = self.total_units - self.completed_units
        time_per_unit = elapsed / self.completed_units if self.completed_units else 0

        eta = (
            f"{remaining_units * time_per_unit:.0f}s"
            if time_per_unit > 0
            else "?"
        )

        return (
            f"Progress: {self.completed_units}/{self.total_units} "
            f"({percent:.1f}%) | Rows: {self.total_rows} "
            f"| Speed: {rows_per_second:.1f} rows/sec | ETA: {eta}"
        )

    def write(self, message: str):

        if self.bar is None:

            print(message)

            return

        self.bar.write(message, file=sys.stdout)

    def close(self):

        if self.bar is not None:

            self.bar.close()
            self.bar = None
