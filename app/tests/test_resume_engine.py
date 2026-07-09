from datetime import datetime

from app.downloader.download_engine import DownloadEngine
from app.models.job import DownloadJob
from app.planner.download_planner import DownloadPlanner


class FakeRepository:
    """
    In-memory stand-in for Repository, keyed exactly like the real
    download_jobs / download_manifest tables so tests exercise the same
    per-unit lookups the real SQL performs (not a single global override).
    """

    def __init__(self):

        self.jobs = {}
        self.manifest = {}
        self.job_close_count = 0

    # -- manifest --

    def manifest_key(self, job_id, batch_number, option_type, strike_offset):

        return (job_id, batch_number, option_type, strike_offset)

    def create_manifest_entry(
        self,
        job_id,
        batch_number,
        underlying,
        instrument,
        expiry_type,
        option_type,
        strike_offset,
        interval,
        from_date,
        to_date,
    ):

        key = self.manifest_key(job_id, batch_number, option_type, strike_offset)

        if key in self.manifest:

            return

        self.manifest[key] = {
            "status": "PENDING",
            "inserted_rows": 0,
            "retry_count": 0,
        }

    def get_manifest_status(self, job_id, batch_number, option_type, strike_offset):

        key = self.manifest_key(job_id, batch_number, option_type, strike_offset)

        entry = self.manifest.get(key)

        return entry["status"] if entry else None

    def get_manifest_retry_count(
        self, job_id, batch_number, option_type, strike_offset
    ):

        key = self.manifest_key(job_id, batch_number, option_type, strike_offset)

        entry = self.manifest.get(key)

        return entry["retry_count"] if entry else 0

    def reconcile_stale_running_batches(self, job_id):

        reconciled = False

        for key, entry in self.manifest.items():

            if key[0] == job_id and entry["status"] == "RUNNING":

                entry["status"] = "FAILED"
                reconciled = True

        return reconciled

    def mark_batch_started(self, job_id, batch_number, option_type, strike_offset):

        key = self.manifest_key(job_id, batch_number, option_type, strike_offset)

        self.manifest[key]["status"] = "RUNNING"
        self.manifest[key]["retry_count"] += 1

    def mark_batch_completed(
        self,
        job_id,
        batch_number,
        option_type,
        strike_offset,
        downloaded_rows,
        inserted_rows,
    ):

        key = self.manifest_key(job_id, batch_number, option_type, strike_offset)

        self.manifest[key]["status"] = "COMPLETED"
        self.manifest[key]["inserted_rows"] = inserted_rows

    def mark_batch_failed(
        self,
        job_id,
        batch_number,
        option_type,
        strike_offset,
        error_message,
    ):

        key = self.manifest_key(job_id, batch_number, option_type, strike_offset)

        self.manifest[key]["status"] = "FAILED"

    def get_job_progress(self, job_id):

        rows = [
            entry
            for key, entry in self.manifest.items()
            if key[0] == job_id
        ]

        return {
            "completed_batches": sum(
                1 for row in rows if row["status"] == "COMPLETED"
            ),
            "failed_batches": sum(
                1 for row in rows if row["status"] == "FAILED"
            ),
            "total_rows": sum(row["inserted_rows"] for row in rows),
        }

    # -- jobs --

    def save_job(
        self,
        job_id,
        underlying,
        instrument,
        expiry_type,
        option_types,
        strike_from,
        strike_to,
        interval,
        start_date,
        end_date,
        created_at,
    ):

        existing = self.jobs.get(job_id)

        if existing is not None:

            if (
                existing["underlying"] != underlying
                or existing["expiry_type"] != expiry_type
                or existing["option_types"] != option_types
                or existing["strike_from"] != strike_from
                or existing["strike_to"] != strike_to
                or existing["start_date"] != start_date
                or existing["end_date"] != end_date
            ):

                raise ValueError(
                    f"job_id '{job_id}' already exists with different "
                    "parameters."
                )

            return

        self.jobs[job_id] = {
            "job_id": job_id,
            "underlying": underlying,
            "instrument": instrument,
            "expiry_type": expiry_type,
            "option_types": option_types,
            "strike_from": strike_from,
            "strike_to": strike_to,
            "interval": interval,
            "start_date": start_date,
            "end_date": end_date,
            "status": "PENDING",
            "created_at": created_at,
            "started_at": None,
            "completed_at": None,
            "total_batches": 0,
            "completed_batches": 0,
            "failed_batches": 0,
            "total_rows": 0,
        }

    def get_job(self, job_id):

        return self.jobs.get(job_id)

    def mark_job_started(self, job_id):

        job = self.jobs[job_id]
        job["status"] = "RUNNING"
        job["started_at"] = job["started_at"] or "FIRST_START"

    def set_job_total_batches(self, job_id, total_batches):

        self.jobs[job_id]["total_batches"] = total_batches

    def mark_job_completed(self, job_id, completed_batches, failed_batches, total_rows):

        self.job_close_count += 1

        job = self.jobs[job_id]
        job["status"] = "COMPLETED"
        job["completed_batches"] = completed_batches
        job["failed_batches"] = failed_batches
        job["total_rows"] = total_rows
        job["completed_at"] = f"FINISHED-{self.job_close_count}"

    def mark_job_failed(self, job_id, completed_batches, failed_batches, total_rows):

        self.job_close_count += 1

        job = self.jobs[job_id]
        job["status"] = "FAILED"
        job["completed_batches"] = completed_batches
        job["failed_batches"] = failed_batches
        job["total_rows"] = total_rows
        job["completed_at"] = f"FINISHED-{self.job_close_count}"


class FakeProgressReporter:

    def reset(self, total_units, description, initial_rows=0):

        pass

    def record(self, inserted_rows=0):

        pass

    def close(self):

        pass


class SuccessfulDownloadService:

    def download(self, payload):

        return {
            "success": True,
            "downloaded_rows": 10,
            "inserted_rows": 10,
            "error": None,
        }


class CountingDownloadService:

    def __init__(self, fail_option_types=()):

        self.download_count = 0
        self.fail_option_types = set(fail_option_types)

    def download(self, payload):

        self.download_count += 1

        if payload["drvOptionType"] in self.fail_option_types:

            return {
                "success": False,
                "downloaded_rows": 0,
                "inserted_rows": 0,
                "error": "Download failed",
            }

        return {
            "success": True,
            "downloaded_rows": 10,
            "inserted_rows": 10,
            "error": None,
        }


def create_test_job(
    job_id="JOB-RESUME-TEST",
    option_types=None,
    strike_from=0,
    strike_to=0,
):

    return DownloadJob(
        job_id=job_id,
        underlying="NIFTY",
        expiry_type="MONTH",
        option_types=option_types or ["CALL"],
        strike_from=strike_from,
        strike_to=strike_to,
        start_date="2025-01-01",
        end_date="2025-01-01",
        created_at=datetime.now(),
    )


def create_test_engine(download_service):

    engine = DownloadEngine.__new__(DownloadEngine)
    engine.planner = DownloadPlanner()
    engine.repo = FakeRepository()
    engine.service = download_service
    engine.progress = FakeProgressReporter()

    return engine


def test_run_persists_job_and_marks_completed():

    engine = create_test_engine(SuccessfulDownloadService())

    engine.run(create_test_job())

    job = engine.repo.get_job("JOB-RESUME-TEST")

    assert job["status"] == "COMPLETED"
    assert job["total_batches"] == 1
    assert job["completed_batches"] == 1
    assert job["failed_batches"] == 0
    assert job["total_rows"] == 10


def test_run_downloads_every_strike_in_the_requested_range():

    service = CountingDownloadService()
    engine = create_test_engine(service)

    engine.run(create_test_job(strike_from=-1, strike_to=1))

    # 1 date-range batch x 1 option_type x 3 strikes (-1, 0, +1)
    assert service.download_count == 3

    job = engine.repo.get_job("JOB-RESUME-TEST")

    assert job["status"] == "COMPLETED"
    assert job["total_batches"] == 3
    assert job["completed_batches"] == 3


def test_run_rejects_an_unsupported_underlying_before_persisting():

    engine = create_test_engine(SuccessfulDownloadService())

    job = create_test_job()
    job.underlying = "RELIANCE"

    try:
        engine.run(job)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for an unsupported underlying")

    # Must fail before the job is ever persisted.
    assert engine.repo.get_job("JOB-RESUME-TEST") is None


def test_run_rejects_an_inverted_strike_range_before_persisting():

    engine = create_test_engine(SuccessfulDownloadService())

    try:
        engine.run(create_test_job(strike_from=5, strike_to=-5))
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for strike_from > strike_to")

    assert engine.repo.get_job("JOB-RESUME-TEST") is None


def test_run_rejects_an_out_of_bounds_strike_offset():

    engine = create_test_engine(SuccessfulDownloadService())

    try:
        engine.run(create_test_job(strike_from=-15, strike_to=-15))
    except ValueError:
        return

    raise AssertionError("Expected ValueError for an out-of-bounds strike offset")


def test_resume_rejects_a_legacy_job_with_a_bad_underlying_instead_of_looping_forever():

    # Simulates a job persisted before underlying validation existed,
    # bypassing run()'s upfront validate_job() entirely - this is
    # exactly the scenario that used to leave a job stuck in RUNNING
    # forever, since PayloadBuilder's ValueError used to only surface
    # deep inside execute() (after mark_job_started()), skipping
    # finish_job() entirely.
    engine = create_test_engine(SuccessfulDownloadService())

    engine.repo.save_job(
        job_id="LEGACY-JOB",
        underlying="RELIANCE",
        instrument="OPTIDX",
        expiry_type="MONTH",
        option_types="CALL",
        strike_from=0,
        strike_to=0,
        interval=1,
        start_date="2025-01-01",
        end_date="2025-01-01",
        created_at=datetime.now(),
    )
    engine.repo.jobs["LEGACY-JOB"]["status"] = "RUNNING"

    try:
        engine.resume("LEGACY-JOB")
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError for a legacy job with a bad underlying"
        )

    # Must not have been silently marked COMPLETED with zero rows.
    job = engine.repo.get_job("LEGACY-JOB")
    assert job["status"] == "RUNNING"


def test_resume_rejects_a_legacy_job_with_an_inverted_strike_range():

    engine = create_test_engine(SuccessfulDownloadService())

    engine.repo.save_job(
        job_id="LEGACY-JOB-2",
        underlying="NIFTY",
        instrument="OPTIDX",
        expiry_type="MONTH",
        option_types="CALL",
        strike_from=5,
        strike_to=-5,
        interval=1,
        start_date="2025-01-01",
        end_date="2025-01-01",
        created_at=datetime.now(),
    )
    engine.repo.jobs["LEGACY-JOB-2"]["status"] = "RUNNING"

    try:
        engine.resume("LEGACY-JOB-2")
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError for a legacy job with strike_from > strike_to"
        )

    # Must not have been silently marked COMPLETED with zero rows.
    job = engine.repo.get_job("LEGACY-JOB-2")
    assert job["status"] == "RUNNING"


def test_run_marks_job_failed_when_a_batch_fails():

    engine = create_test_engine(CountingDownloadService(fail_option_types={"CALL"}))

    engine.run(create_test_job())

    job = engine.repo.get_job("JOB-RESUME-TEST")

    assert job["status"] == "FAILED"
    assert job["failed_batches"] == 1


def test_run_rejects_reusing_job_id_with_different_dates():

    engine = create_test_engine(SuccessfulDownloadService())

    engine.run(create_test_job())

    other_job = DownloadJob(
        job_id="JOB-RESUME-TEST",
        underlying="NIFTY",
        expiry_type="MONTH",
        option_types=["CALL"],
        strike_from=-1,
        strike_to=1,
        start_date="2025-02-01",
        end_date="2025-02-01",
        created_at=datetime.now(),
    )

    try:
        engine.run(other_job)
    except ValueError:
        return

    raise AssertionError(
        "Expected ValueError when reusing a job_id with different parameters"
    )


def test_resume_continues_only_the_unfinished_units():

    service = CountingDownloadService(fail_option_types={"PUT"})
    engine = create_test_engine(service)

    engine.run(create_test_job(option_types=["CALL", "PUT"]))

    job = engine.repo.get_job("JOB-RESUME-TEST")
    assert job["status"] == "FAILED"
    assert service.download_count == 2

    # PUT now succeeds; resuming should skip the already-completed CALL
    # and only retry PUT.
    service.fail_option_types.clear()

    engine.resume("JOB-RESUME-TEST")

    assert service.download_count == 3

    job = engine.repo.get_job("JOB-RESUME-TEST")
    assert job["status"] == "COMPLETED"
    assert job["completed_batches"] == 2
    assert job["failed_batches"] == 0


def test_resume_is_a_noop_for_an_already_completed_job():

    service = CountingDownloadService()
    engine = create_test_engine(service)

    engine.run(create_test_job())

    download_count_before = service.download_count
    started_at_before = engine.repo.get_job("JOB-RESUME-TEST")["started_at"]

    engine.resume("JOB-RESUME-TEST")

    job = engine.repo.get_job("JOB-RESUME-TEST")

    assert service.download_count == download_count_before
    assert job["started_at"] == started_at_before


def test_resume_preserves_started_at_across_a_retry():

    service = CountingDownloadService(fail_option_types={"CALL"})
    engine = create_test_engine(service)

    engine.run(create_test_job())

    started_at_before = engine.repo.get_job("JOB-RESUME-TEST")["started_at"]

    service.fail_option_types.clear()
    engine.resume("JOB-RESUME-TEST")

    job = engine.repo.get_job("JOB-RESUME-TEST")

    assert job["status"] == "COMPLETED"
    assert job["started_at"] == started_at_before


def test_resume_restores_option_types_for_multi_leg_jobs():

    service = CountingDownloadService(fail_option_types={"CALL", "PUT"})
    engine = create_test_engine(service)

    engine.run(create_test_job(option_types=["CALL", "PUT"]))

    service.fail_option_types.clear()
    engine.resume("JOB-RESUME-TEST")

    job = engine.repo.get_job("JOB-RESUME-TEST")

    assert job["status"] == "COMPLETED"
    assert job["completed_batches"] == 2


def test_resume_raises_for_unknown_job_id():

    engine = create_test_engine(SuccessfulDownloadService())

    try:
        engine.resume("JOB-DOES-NOT-EXIST")
    except ValueError:
        return

    raise AssertionError("Expected ValueError for unknown job_id")


if __name__ == "__main__":

    test_run_persists_job_and_marks_completed()
    test_run_downloads_every_strike_in_the_requested_range()
    test_run_rejects_an_unsupported_underlying_before_persisting()
    test_run_rejects_an_inverted_strike_range_before_persisting()
    test_run_rejects_an_out_of_bounds_strike_offset()
    test_resume_rejects_a_legacy_job_with_a_bad_underlying_instead_of_looping_forever()
    test_resume_rejects_a_legacy_job_with_an_inverted_strike_range()
    test_run_marks_job_failed_when_a_batch_fails()
    test_run_rejects_reusing_job_id_with_different_dates()
    test_resume_continues_only_the_unfinished_units()
    test_resume_is_a_noop_for_an_already_completed_job()
    test_resume_preserves_started_at_across_a_retry()
    test_resume_restores_option_types_for_multi_leg_jobs()
    test_resume_raises_for_unknown_job_id()

    print("Resume engine tests passed")
