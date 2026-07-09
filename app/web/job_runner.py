"""
Job Runner

Owns the single DownloadEngine (and therefore the single DuckDB
connection - see DuckDBManager's docstring) used by the web GUI, and
runs at most one download job at a time in a background thread so
HTTP requests never block on a multi-minute download. Status/list
reads go through the same DownloadEngine.repo instance concurrently;
Repository's internal lock makes sharing that one connection safe.
"""

import threading
from typing import Callable

from app.config.logging_config import get_logger
from app.downloader.download_engine import DownloadEngine
from app.models.job import DownloadJob

logger = get_logger()


class JobAlreadyRunningError(Exception):
    """Raised when a job is requested while another is still running.
    The GUI only ever runs one job at a time: DuckDB permits only one
    connection per process, and this keeps the concurrency model
    simple and correct rather than building a multi-writer queue."""


class JobRunner:
    """Runs at most one download job at a time in a background thread.
    Owns the single DownloadEngine for the process; `_current_job_id`
    is an in-memory flag guarded by `_lock`, so it resets on process
    restart even if a job's manifest rows are still left at RUNNING -
    `start`/`start_resume` work for such an orphaned job the same as
    any other, via DownloadEngine.resume()'s own reconciliation."""

    def __init__(self):

        self.engine = DownloadEngine()

        self._lock = threading.Lock()
        self._current_job_id: str | None = None
        self._queue_job_ids: list[str] = []
        self._queue_position: int = 0

    @property
    def current_job_id(self) -> str | None:

        with self._lock:

            return self._current_job_id

    @property
    def queue_progress(self) -> dict | None:
        """{"position", "total"} (1-based) while a start_many() queue
        is running, or None otherwise - used to render "job N of M"
        during an auto-sync run."""

        with self._lock:

            if not self._queue_job_ids:

                return None

            return {
                "position": self._queue_position,
                "total": len(self._queue_job_ids),
            }

    def start(self, job: DownloadJob):
        """Starts a new job in the background. Validates synchronously
        first (cheap, no I/O) so bad input, or a job_id that collides
        with an existing job's different parameters (the same check
        Repository.save_job() makes), is rejected immediately with a
        clear error instead of failing invisibly in the background
        thread after the HTTP response has already gone out."""

        DownloadEngine.validate_job(job)

        self.engine.repo.check_job_reusable(
            job.job_id,
            job.underlying,
            job.expiry_type,
            ",".join(job.option_types),
            job.strike_from,
            job.strike_to,
            job.start_date,
            job.end_date,
            job.parquet_output_dir,
        )

        self._claim(job.job_id)

        threading.Thread(
            target=self._run,
            args=(self.engine.run, job),
            daemon=True,
        ).start()

    def start_resume(self, job_id: str):
        """Resumes an existing job in the background. Validates
        synchronously first, same as start() and for the same reason:
        a job_id predating validate_job() (see DownloadEngine's own
        docstring) would otherwise fail invisibly inside the
        background thread, which only logs and swallows the error."""

        record = self.engine.repo.get_job(job_id)

        if record is None:

            raise ValueError(f"Unknown job_id: {job_id}")

        DownloadEngine.validate_job(DownloadEngine.build_job(record))

        self._claim(job_id)

        threading.Thread(
            target=self._run,
            args=(self.engine.resume, job_id),
            daemon=True,
        ).start()

    def start_many(self, jobs: list[DownloadJob]):
        """Runs a list of jobs sequentially in one background thread,
        claiming the runner busy for the whole queue's duration (not
        just the first job) - used by auto-sync to run up to 4 jobs
        (one per underlying/expiry-type combo) back to back. A job
        that fails is logged (same as _run()) but does not stop the
        rest of the queue, matching the existing per-unit failure
        tolerance inside a single job. A no-op for an empty list."""

        if not jobs:

            return

        for job in jobs:

            DownloadEngine.validate_job(job)

            self.engine.repo.check_job_reusable(
                job.job_id,
                job.underlying,
                job.expiry_type,
                ",".join(job.option_types),
                job.strike_from,
                job.strike_to,
                job.start_date,
                job.end_date,
                job.parquet_output_dir,
            )

        with self._lock:

            if self._current_job_id is not None:

                raise JobAlreadyRunningError(
                    f"Job '{self._current_job_id}' is already running"
                )

            self._queue_job_ids = [job.job_id for job in jobs]
            self._queue_position = 1
            self._current_job_id = jobs[0].job_id

        threading.Thread(
            target=self._run_many,
            args=(jobs,),
            daemon=True,
        ).start()

    def _run_many(self, jobs: list[DownloadJob]):

        for index, job in enumerate(jobs, start=1):

            with self._lock:

                self._current_job_id = job.job_id
                self._queue_position = index

            try:

                self.engine.run(job)

            except Exception as exc:

                logger.error(f"Background sync job {job.job_id} failed: {exc}")

        with self._lock:

            self._current_job_id = None
            self._queue_job_ids = []
            self._queue_position = 0

    def _claim(self, job_id: str):

        with self._lock:

            if self._current_job_id is not None:

                raise JobAlreadyRunningError(
                    f"Job '{self._current_job_id}' is already running"
                )

            self._current_job_id = job_id

    def _run(self, target: Callable[[object], None], arg: object):

        try:

            target(arg)

        except Exception as exc:

            logger.error(f"Background job failed: {exc}")

        finally:

            with self._lock:

                self._current_job_id = None
