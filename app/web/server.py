"""
Web GUI Server

A small FastAPI app + static frontend for triggering downloads,
watching live progress, and browsing past jobs - a thin layer over
the same DownloadJob/DownloadEngine/Repository used by the CLI. Launch
with:
    python -m app.web
"""

import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import set_key
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from app import validation
from app.api.api_client import DhanAPI
from app.autosync.sync_planner import SyncPlanner
from app.builders.payload_builder import PayloadBuilder
from app.config.config import PROJECT_ROOT
from app.config.logging_config import get_logger
from app.constants.trading_calendar import DATA_AVAILABLE_BY
from app.constants.underlyings import SUPPORTED_UNDERLYINGS
from app.models.job import DownloadJob
from app.web.folder_picker import pick_folder
from app.web.job_runner import JobAlreadyRunningError, JobRunner

logger = get_logger()

STATIC_DIR = Path(__file__).parent / "static"

ENV_PATH = PROJECT_ROOT / ".env"


def _auto_sync(job_runner: JobRunner):
    """Best-effort background catch-up sync - called once on server
    startup and again right after a token is confirmed valid, so
    NIFTY/SENSEX data catches up automatically without the user
    needing to click "Sync Data" every day. SyncPlanner.plan_jobs()
    is gap-based and already a no-op once today's data is in, so
    calling this more than once a day (e.g. across server restarts)
    just costs one cheap DB read - no explicit once-per-day
    bookkeeping needed. Silently does nothing if the token isn't
    valid yet or a job is already running; never raises into its
    caller, since both call sites (startup, token update) must not
    fail because of this."""

    try:

        if DhanAPI().test_connection().status_code != 200:

            return

        jobs = SyncPlanner.plan_jobs(job_runner.engine.repo)

        if not jobs:

            return

        logger.info(f"Auto-sync: starting {len(jobs)} job(s).")

        job_runner.start_many(jobs)

    except JobAlreadyRunningError:

        pass

    except Exception as exc:

        logger.error(f"Auto-sync failed to start: {exc}")


def _daily_sync_scheduler(job_runner: JobRunner):
    """Runs for the life of the server process: sleeps until
    DATA_AVAILABLE_BY (8 PM, when a trading session's data should
    realistically be published - see app/constants/trading_calendar.py)
    each day, then triggers _auto_sync(), then repeats for the
    following day. Complements the startup/token-update triggers,
    which only fire at the moment the app happens to be (re)started
    or reconnected - this catches a server left running through the
    end of a trading day up automatically, without the user needing
    to reopen the app or click anything."""

    while True:

        now = datetime.now()

        target = datetime.combine(now.date(), DATA_AVAILABLE_BY)

        if now >= target:

            target += timedelta(days=1)

        time.sleep((target - now).total_seconds())

        _auto_sync(job_runner)


@asynccontextmanager
async def lifespan(app: FastAPI):

    try:

        app.state.job_runner = JobRunner()

    except Exception as exc:

        logger.error(
            f"Failed to start OptionLab web server: {exc}. If this is a "
            "database connection error, another OptionLab process (CLI "
            "or `python -m app.web`) may already have "
            "database/optionlab.duckdb open - DuckDB only allows one "
            "connection to it at a time."
        )

        raise

    threading.Thread(
        target=_auto_sync, args=(app.state.job_runner,), daemon=True
    ).start()

    threading.Thread(
        target=_daily_sync_scheduler, args=(app.state.job_runner,), daemon=True
    ).start()

    yield


app = FastAPI(title="OptionLab", lifespan=lifespan)


@app.middleware("http")
async def _no_cache_static(request: Request, call_next):
    """Static assets change whenever this codebase is edited, but
    browsers apply heuristic caching to files served without an
    explicit Cache-Control header - silently serving a stale app.js/
    style.css after an edit until the user notices something's wrong
    and hard-refreshes. Force revalidation on every load instead."""

    response = await call_next(request)

    if request.url.path.startswith("/static/"):

        response.headers["Cache-Control"] = "no-store"

    return response


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def get_job_runner(request: Request) -> JobRunner:
    """FastAPI dependency exposing the single process-wide JobRunner
    stored on app.state by lifespan(), so routes stay swappable in
    tests (patch server_module.JobRunner) without a global."""

    return request.app.state.job_runner


class CreateJobRequest(BaseModel):
    """POST /api/jobs request body - mirrors app/main.py's `download`
    arguments, validated with the same app/validation.py helpers."""

    underlying: str
    expiry_type: str
    option_types: list[str]
    start_date: str
    end_date: str
    job_id: str | None = None
    parquet_output_dir: str | None = None

    @field_validator("underlying")
    @classmethod
    def _validate_underlying(cls, value: str) -> str:

        return validation.normalize_choice(value, SUPPORTED_UNDERLYINGS)

    @field_validator("expiry_type")
    @classmethod
    def _validate_expiry_type(cls, value: str) -> str:

        return validation.normalize_choice(value, PayloadBuilder.VALID_EXPIRY_TYPES)

    @field_validator("option_types")
    @classmethod
    def _validate_option_types(cls, value: list[str]) -> list[str]:

        return validation.normalize_choices(
            value, PayloadBuilder.VALID_OPTION_TYPES, label="option type"
        )

    @field_validator("start_date", "end_date")
    @classmethod
    def _validate_date(cls, value: str) -> str:

        return validation.parse_date(value)

    @field_validator("job_id")
    @classmethod
    def _validate_job_id(cls, value: str | None) -> str | None:

        return validation.non_blank(value) if value is not None else None

    @field_validator("parquet_output_dir")
    @classmethod
    def _validate_parquet_output_dir(cls, value: str | None) -> str | None:

        return validation.non_blank(value) if value is not None else None


class BrowseFolderRequest(BaseModel):
    """POST /api/browse-folder request body - initial_dir is optional,
    used to reopen the native dialog where the user last left off."""

    initial_dir: str | None = None


class UpdateTokenRequest(BaseModel):
    """POST /api/token request body."""

    access_token: str

    @field_validator("access_token")
    @classmethod
    def _validate_access_token(cls, value: str) -> str:

        return validation.non_blank(value)


def _json_safe(value: object) -> object:
    """Converts a datetime/date DB value to an ISO string; passes
    everything else through unchanged."""

    if isinstance(value, (datetime, date)):

        return value.isoformat()

    return value


def _serialize_job(job: dict, job_runner: JobRunner) -> dict:
    """Converts a download_jobs row into the JSON shape the frontend
    polls, adding the derived percent_complete/is_running fields the
    DB row doesn't carry on its own.

    completed_batches/failed_batches/total_rows are read live from the
    manifest via get_job_progress() rather than the job row's own
    columns of the same name: DownloadEngine only writes those columns
    once, when the job finishes (finish_job()), so trusting the row
    directly would freeze the progress bar at its pre-run value for a
    job's entire RUNNING duration. get_job_progress() is the same
    aggregate finish_job() itself uses, so it agrees with the row once
    the job is terminal and is simply live before that."""

    total = job["total_batches"] or 0

    progress = job_runner.engine.repo.get_job_progress(job["job_id"])

    completed = progress["completed_batches"] or 0
    failed = progress["failed_batches"] or 0
    finished = completed + failed

    percent_complete = round(100 * finished / total, 1) if total else 0.0

    return {
        "job_id": job["job_id"],
        "underlying": job["underlying"],
        "expiry_type": job["expiry_type"],
        "option_types": job["option_types"],
        "strike_from": job["strike_from"],
        "strike_to": job["strike_to"],
        "start_date": _json_safe(job["start_date"]),
        "end_date": _json_safe(job["end_date"]),
        "status": job["status"],
        "total_batches": total,
        "completed_batches": completed,
        "failed_batches": failed,
        "total_rows": progress["total_rows"],
        "created_at": _json_safe(job["created_at"]),
        "started_at": _json_safe(job["started_at"]),
        "completed_at": _json_safe(job["completed_at"]),
        "percent_complete": percent_complete,
        "is_running": job["job_id"] == job_runner.current_job_id,
    }


@app.get("/")
def index():
    """Serves the frontend shell (app/web/static/index.html)."""

    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/underlyings")
def list_underlyings():
    """Lists the underlyings the CLI/GUI both support, for the form's
    dropdown."""

    return sorted(SUPPORTED_UNDERLYINGS.keys())


@app.post("/api/browse-folder")
def browse_folder(request: BrowseFolderRequest | None = None):
    """Opens a native OS folder-picker dialog server-side (this is a
    local, single-user tool - the server and the browser run on the
    same machine) and returns the chosen path, or null if cancelled."""

    try:

        path = pick_folder(initial_dir=request.initial_dir if request else None)

    except Exception as exc:

        logger.error(f"Folder picker failed: {exc}")

        raise HTTPException(500, f"Could not open folder picker: {exc}")

    return {"path": path}


@app.get("/api/token-status")
def token_status():
    """Checks whether the current DhanHQ access token still works
    (a real network call - the frontend should only call this on page
    load and after an update, not on a polling interval)."""

    response = DhanAPI().test_connection()

    return {"valid": response.status_code == 200}


@app.post("/api/token")
def update_token(
    request: UpdateTokenRequest,
    job_runner: JobRunner = Depends(get_job_runner),
):
    """Writes a new access token into .env and applies it to the
    running process immediately - DhanAPI reads os.environ live (see
    app/api/api_client.py), so no restart is needed. Never logs the
    token value."""

    set_key(ENV_PATH, "DHAN_ACCESS_TOKEN", request.access_token, quote_mode="never")

    os.environ["DHAN_ACCESS_TOKEN"] = request.access_token

    response = DhanAPI().test_connection()

    valid = response.status_code == 200

    if valid:

        threading.Thread(
            target=_auto_sync, args=(job_runner,), daemon=True
        ).start()

    return {"valid": valid}


@app.get("/api/sync-status")
def sync_status(job_runner: JobRunner = Depends(get_job_runner)):
    """Per-underlying/expiry-type data-freshness status for the
    auto-sync feature, plus the current sync queue's progress (null
    if no sync is running)."""

    status = SyncPlanner.status(job_runner.engine.repo)

    queue = job_runner.queue_progress

    if queue is not None:

        current_job_id = job_runner.current_job_id
        current_job = (
            job_runner.engine.repo.get_job(current_job_id)
            if current_job_id
            else None
        )

        queue["current_job"] = (
            _serialize_job(current_job, job_runner) if current_job else None
        )

    status["queue"] = queue

    return status


@app.post("/api/sync", status_code=202)
def start_sync(job_runner: JobRunner = Depends(get_job_runner)):
    """Plans and starts the jobs needed to bring NIFTY/SENSEX data up
    to date (up to 4 jobs - one per underlying/expiry-type combo with
    a gap). A no-op if everything is already current. 409 if a job or
    another sync is already running."""

    jobs = SyncPlanner.plan_jobs(job_runner.engine.repo)

    if not jobs:

        return {"job_ids": [], "status": "up_to_date"}

    try:

        job_runner.start_many(jobs)

    except JobAlreadyRunningError as exc:

        raise HTTPException(409, str(exc))

    return {"job_ids": [job.job_id for job in jobs], "status": "started"}


@app.get("/api/jobs")
def list_jobs(job_runner: JobRunner = Depends(get_job_runner)):
    """Lists every job ever created, newest first, for the job table."""

    jobs = job_runner.engine.repo.list_jobs()

    return [_serialize_job(job, job_runner) for job in jobs]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, job_runner: JobRunner = Depends(get_job_runner)):
    """Fetches a single job's current status; 404 if job_id is unknown."""

    job = job_runner.engine.repo.get_job(job_id)

    if job is None:

        raise HTTPException(404, f"Unknown job_id: {job_id}")

    return _serialize_job(job, job_runner)


@app.post("/api/jobs", status_code=202)
def create_job(
    request: CreateJobRequest,
    job_runner: JobRunner = Depends(get_job_runner),
):
    """Starts a new download job in the background. 409 if a job is
    already running, 400 if validate_job() rejects the built job."""

    job_id = (
        request.job_id
        or f"{request.underlying}-{request.start_date}-{request.end_date}"
    )

    job = DownloadJob(
        job_id=job_id,
        underlying=request.underlying,
        expiry_type=request.expiry_type,
        option_types=request.option_types,
        strike_from=PayloadBuilder.MIN_STRIKE_OFFSET,
        strike_to=PayloadBuilder.MAX_STRIKE_OFFSET,
        start_date=request.start_date,
        end_date=request.end_date,
        created_at=datetime.now(),
        parquet_output_dir=request.parquet_output_dir,
    )

    try:

        job_runner.start(job)

    except JobAlreadyRunningError as exc:

        raise HTTPException(409, str(exc))

    except ValueError as exc:

        raise HTTPException(400, str(exc))

    return {"job_id": job_id, "status": "started"}


@app.post("/api/jobs/{job_id}/resume", status_code=202)
def resume_job(job_id: str, job_runner: JobRunner = Depends(get_job_runner)):
    """Resumes an existing job in the background, regardless of its
    current status (e.g. RUNNING left over from a server restart, or
    FAILED with retryable work). 409 if a job is already running, 404
    if job_id is unknown."""

    try:

        job_runner.start_resume(job_id)

    except JobAlreadyRunningError as exc:

        raise HTTPException(409, str(exc))

    except ValueError as exc:

        raise HTTPException(404, str(exc))

    return {"job_id": job_id, "status": "resuming"}
