import threading
import time

import app.web.job_runner as job_runner_module
from app.web.job_runner import JobAlreadyRunningError, JobRunner


class FakeRepo:

    def __init__(self, jobs, reuse_error=None):

        self.jobs = jobs
        self.reuse_error = reuse_error

    def get_job(self, job_id):

        return self.jobs.get(job_id)

    def check_job_reusable(self, job_id, *args, **kwargs):

        if self.reuse_error is not None:

            raise self.reuse_error


class FakeDownloadEngine:
    """Simulates DownloadEngine's run()/resume()/validate_job(). Must
    be constructible with zero arguments (JobRunner.__init__ calls
    DownloadEngine() directly) so per-test behavior is configured via
    class attributes on a small subclass instead of constructor args -
    same pattern as FakeDownloadEngine in app/tests/test_cli.py."""

    instances = []
    jobs = {}
    gate: threading.Event | None = None
    reuse_error = None

    def __init__(self):

        self.run_calls = []
        self.resume_calls = []
        self.repo = FakeRepo(jobs=type(self).jobs, reuse_error=type(self).reuse_error)

        type(self).instances.append(self)

    def run(self, job):

        if type(self).gate is not None:

            type(self).gate.wait(timeout=5)

        self.run_calls.append(job)

    def resume(self, job_id):

        if type(self).gate is not None:

            type(self).gate.wait(timeout=5)

        self.resume_calls.append(job_id)

    @staticmethod
    def validate_job(job):

        pass

    @staticmethod
    def build_job(record):

        return FakeJob(job_id=record["job_id"], underlying=record.get("underlying", "NIFTY"))


class FailingValidateEngine(FakeDownloadEngine):

    instances = []
    jobs = {"JOB-1": {"job_id": "JOB-1", "underlying": "RELIANCE"}}

    @staticmethod
    def validate_job(job):

        raise ValueError(f"Unsupported underlying: {job.underlying}")


class CrashingEngine(FakeDownloadEngine):

    instances = []

    def run(self, job):

        raise RuntimeError("simulated crash")


class FakeJob:

    def __init__(self, job_id="JOB-1", underlying="NIFTY"):

        self.job_id = job_id
        self.underlying = underlying
        self.expiry_type = "MONTH"
        self.option_types = ["CALL"]
        self.strike_from = 0
        self.strike_to = 0
        self.start_date = "2025-01-01"
        self.end_date = "2025-01-01"
        self.parquet_output_dir = None


def with_fake_engine(engine_class, fn):

    original = job_runner_module.DownloadEngine
    job_runner_module.DownloadEngine = engine_class

    try:
        return fn()
    finally:
        job_runner_module.DownloadEngine = original


def _wait_until_idle(runner, timeout=2):

    deadline = time.monotonic() + timeout

    while runner.current_job_id is not None and time.monotonic() < deadline:

        time.sleep(0.01)


def test_start_runs_the_job_and_clears_current_job_id_when_done():

    def run():

        runner = JobRunner()

        runner.start(FakeJob(job_id="JOB-1"))

        _wait_until_idle(runner)

        assert runner.current_job_id is None

        engine = FakeDownloadEngine.instances[-1]
        assert [j.job_id for j in engine.run_calls] == ["JOB-1"]

    FakeDownloadEngine.instances = []
    FakeDownloadEngine.gate = None

    with_fake_engine(FakeDownloadEngine, run)


def test_start_raises_when_a_job_is_already_running():

    class GatedEngine(FakeDownloadEngine):

        instances = []
        gate = threading.Event()

    def run():

        runner = JobRunner()

        runner.start(FakeJob(job_id="JOB-1"))

        # JOB-1's background run() is blocked on the gate, so it's
        # still "running" from JobRunner's point of view.
        try:
            runner.start(FakeJob(job_id="JOB-2"))
        except JobAlreadyRunningError as exc:
            assert "JOB-1" in str(exc)
        else:
            raise AssertionError("Expected JobAlreadyRunningError")
        finally:
            GatedEngine.gate.set()

        _wait_until_idle(runner)

    with_fake_engine(GatedEngine, run)


def test_start_does_not_claim_current_job_id_when_validation_fails():

    def run():

        runner = JobRunner()

        try:
            runner.start(FakeJob(job_id="JOB-1", underlying="RELIANCE"))
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError from validate_job")

        # A rejected job must not block a subsequent valid one.
        assert runner.current_job_id is None

    with_fake_engine(FailingValidateEngine, run)


def test_start_does_not_claim_current_job_id_when_job_id_collides():

    class CollidingEngine(FakeDownloadEngine):

        instances = []
        reuse_error = ValueError(
            "job_id 'JOB-1' already exists with different parameters."
        )

    def run():

        runner = JobRunner()

        try:
            runner.start(FakeJob(job_id="JOB-1"))
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError for a job_id collision")

        # A rejected job must not block a subsequent valid one.
        assert runner.current_job_id is None

    with_fake_engine(CollidingEngine, run)


def test_start_resume_does_not_claim_current_job_id_when_validation_fails():

    def run():

        runner = JobRunner()

        try:
            runner.start_resume("JOB-1")
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError from validate_job")

        # A rejected resume must not block a subsequent valid job.
        assert runner.current_job_id is None

    with_fake_engine(FailingValidateEngine, run)


def test_start_resume_raises_for_unknown_job_id():

    class EmptyEngine(FakeDownloadEngine):

        instances = []
        jobs = {}

    def run():

        runner = JobRunner()

        try:
            runner.start_resume("DOES-NOT-EXIST")
        except ValueError as exc:
            assert "DOES-NOT-EXIST" in str(exc)
        else:
            raise AssertionError("Expected ValueError for unknown job_id")

        assert runner.current_job_id is None

    with_fake_engine(EmptyEngine, run)


def test_start_resume_runs_the_job():

    class EngineWithJob(FakeDownloadEngine):

        instances = []
        jobs = {"JOB-1": {"job_id": "JOB-1"}}

    def run():

        runner = JobRunner()

        runner.start_resume("JOB-1")

        _wait_until_idle(runner)

        assert runner.current_job_id is None

        engine = EngineWithJob.instances[-1]
        assert engine.resume_calls == ["JOB-1"]

    with_fake_engine(EngineWithJob, run)


def test_a_background_exception_still_clears_current_job_id():

    def run():

        runner = JobRunner()

        runner.start(FakeJob(job_id="JOB-1"))

        _wait_until_idle(runner)

        assert runner.current_job_id is None

    with_fake_engine(CrashingEngine, run)


if __name__ == "__main__":

    test_start_runs_the_job_and_clears_current_job_id_when_done()
    test_start_raises_when_a_job_is_already_running()
    test_start_does_not_claim_current_job_id_when_validation_fails()
    test_start_does_not_claim_current_job_id_when_job_id_collides()
    test_start_resume_does_not_claim_current_job_id_when_validation_fails()
    test_start_resume_raises_for_unknown_job_id()
    test_start_resume_runs_the_job()
    test_a_background_exception_still_clears_current_job_id()

    print("Job runner tests passed")
