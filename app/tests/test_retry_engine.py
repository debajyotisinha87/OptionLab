"""
Tests for TASK-021.8: Retry Engine.

Covers two independent layers:
- DownloadEngine/Repository: a manifest unit that keeps failing across
  run()/resume() calls is retried only up to MAX_RETRIES, then left
  alone (no infinite retry loop), and resume() itself becomes a no-op
  once nothing is left to retry.
- HTTPClient: transient network errors and 429/5xx responses are
  retried in-process with backoff before being reported as a failure;
  non-transient failures are not retried.
"""

import time
from contextlib import contextmanager

import requests

import app.api.http_client as http_client_module
from app.api.http_client import HTTPClient
from app.downloader.download_engine import DownloadEngine
from app.tests.test_resume_engine import (
    CountingDownloadService,
    create_test_engine,
    create_test_job,
)


@contextmanager
def patched(obj, attr, value):

    original = getattr(obj, attr)
    setattr(obj, attr, value)

    try:
        yield
    finally:
        setattr(obj, attr, original)


def no_backoff_delay():
    """HTTPClient tests only care about attempt counts/outcomes, not the
    real wait_exponential timing, so skip the actual sleep."""

    return patched(time, "sleep", lambda seconds: None)


# ---------------------------------------------------------------------
# Manifest-level retry cap
# ---------------------------------------------------------------------


def test_unit_is_retried_up_to_max_retries_then_left_alone():

    service = CountingDownloadService(fail_option_types={"CALL"})
    engine = create_test_engine(service)

    job = create_test_job()

    engine.run(job)
    assert service.download_count == 1

    engine.resume(job.job_id)
    assert service.download_count == 2

    engine.resume(job.job_id)
    assert service.download_count == 3

    # retry_count is now == MAX_RETRIES; one more resume must NOT attempt
    # the download again.
    engine.resume(job.job_id)
    assert service.download_count == 3

    entry = engine.repo.manifest[(job.job_id, 1, "CALL", 0)]

    assert entry["status"] == "FAILED"
    assert entry["retry_count"] == engine.MAX_RETRIES

    job_record = engine.repo.get_job(job.job_id)

    assert job_record["status"] == "FAILED"

    # Calling resume() again on an already-terminal, exhausted job must be
    # a true no-op - it must NOT re-close the job (which would rewrite
    # completed_at every time someone calls resume() on a dead job).
    completed_at_before = job_record["completed_at"]

    engine.resume(job.job_id)
    assert service.download_count == 3

    job_record = engine.repo.get_job(job.job_id)
    assert job_record["completed_at"] == completed_at_before


def test_unit_succeeding_before_retry_limit_still_completes():

    service = CountingDownloadService(fail_option_types={"CALL"})
    engine = create_test_engine(service)

    job = create_test_job()

    engine.run(job)
    assert service.download_count == 1

    engine.resume(job.job_id)
    assert service.download_count == 2

    service.fail_option_types.clear()

    engine.resume(job.job_id)
    assert service.download_count == 3

    job_record = engine.repo.get_job(job.job_id)

    assert job_record["status"] == "COMPLETED"


def test_has_retryable_work_true_before_limit_reached():

    service = CountingDownloadService(fail_option_types={"CALL"})
    engine = create_test_engine(service)

    job = create_test_job()

    engine.run(job)

    assert engine.has_retryable_work(job) is True


def test_has_retryable_work_false_once_limit_exhausted():

    service = CountingDownloadService(fail_option_types={"CALL"})
    engine = create_test_engine(service)

    job = create_test_job()

    engine.run(job)
    engine.resume(job.job_id)
    engine.resume(job.job_id)

    assert engine.has_retryable_work(job) is False


def test_resume_short_circuits_before_execute_once_exhausted():

    service = CountingDownloadService(fail_option_types={"CALL"})
    engine = create_test_engine(service)

    job = create_test_job()

    engine.run(job)
    engine.resume(job.job_id)
    engine.resume(job.job_id)

    executed = {"called": False}
    original_execute = engine.execute

    def spy_execute(j):
        executed["called"] = True
        return original_execute(j)

    engine.execute = spy_execute

    engine.resume(job.job_id)

    assert executed["called"] is False


class CrashingDownloadService:
    """
    Simulates the process being killed mid-download: unlike a normal
    failure, .download() never returns - it raises, so DownloadEngine
    never gets to call mark_batch_completed/mark_batch_failed and the
    manifest row is left stuck at RUNNING, exactly like a real crash
    would leave it.
    """

    def __init__(self, crash_times):

        self.crash_times = crash_times
        self.call_count = 0

    def download(self, payload):

        self.call_count += 1

        if self.call_count <= self.crash_times:

            raise RuntimeError("simulated process crash mid-download")

        return {
            "success": True,
            "downloaded_rows": 10,
            "inserted_rows": 10,
            "error": None,
        }


def test_resume_reconciles_a_stale_running_unit_and_retries_it():

    service = CrashingDownloadService(crash_times=1)
    engine = create_test_engine(service)

    job = create_test_job()

    try:
        engine.run(job)
        raise AssertionError("expected the simulated crash to propagate")
    except RuntimeError:
        pass

    entry = engine.repo.manifest[(job.job_id, 1, "CALL", 0)]
    assert entry["status"] == "RUNNING"
    assert entry["retry_count"] == 1

    # A fresh call (as if the process restarted) must reconcile the stale
    # RUNNING row and retry it, not treat it as unretryable.
    engine.resume(job.job_id)

    entry = engine.repo.manifest[(job.job_id, 1, "CALL", 0)]
    assert entry["status"] == "COMPLETED"

    job_record = engine.repo.get_job(job.job_id)
    assert job_record["status"] == "COMPLETED"


def test_job_reaches_failed_state_after_repeated_crashes_instead_of_freezing():

    max_retries = DownloadEngine.MAX_RETRIES
    service = CrashingDownloadService(crash_times=max_retries)
    engine = create_test_engine(service)

    job = create_test_job()

    try:
        engine.run(job)
        raise AssertionError("expected the simulated crash to propagate")
    except RuntimeError:
        pass

    for _ in range(max_retries - 1):

        try:
            engine.resume(job.job_id)
            raise AssertionError("expected the simulated crash to propagate")
        except RuntimeError:
            pass

    entry = engine.repo.manifest[(job.job_id, 1, "CALL", 0)]
    assert entry["retry_count"] == engine.MAX_RETRIES
    assert entry["status"] == "RUNNING"

    # One more resume: must reconcile the last stale attempt to FAILED and
    # properly close out the job as FAILED - not silently freeze at RUNNING
    # forever, and not attempt a further download (retry limit already hit).
    call_count_before = service.call_count

    engine.resume(job.job_id)

    assert service.call_count == call_count_before

    entry = engine.repo.manifest[(job.job_id, 1, "CALL", 0)]
    assert entry["status"] == "FAILED"

    job_record = engine.repo.get_job(job.job_id)
    assert job_record["status"] == "FAILED"
    assert job_record["completed_at"] is not None


# ---------------------------------------------------------------------
# HTTPClient-level retry with backoff
# ---------------------------------------------------------------------


def make_status_response(status_code):

    response = requests.Response()
    response.status_code = status_code

    return response


def make_flaky_get(fail_times, failure=None, fail_status=None, success_status=200):

    calls = {"count": 0}

    def flaky_get(url, headers, timeout):

        calls["count"] += 1

        if calls["count"] <= fail_times:

            if failure is not None:
                raise failure

            return make_status_response(fail_status)

        return make_status_response(success_status)

    flaky_get.calls = calls

    return flaky_get


def make_always_fail_post(exception):

    calls = {"count": 0}

    def always_fail_post(url, headers, json, timeout):

        calls["count"] += 1

        raise exception

    always_fail_post.calls = calls

    return always_fail_post


def test_http_client_retries_transient_failures_then_succeeds():

    flaky_get = make_flaky_get(
        fail_times=2,
        failure=requests.exceptions.ConnectionError("simulated transient failure"),
    )

    with no_backoff_delay(), patched(http_client_module.requests, "get", flaky_get):

        response = HTTPClient().get(url="https://example.invalid", headers={})

        assert response.status_code == 200
        assert flaky_get.calls["count"] == 3


def test_http_client_gives_up_after_max_attempts():

    always_fail_post = make_always_fail_post(
        requests.exceptions.ConnectionError("simulated permanent failure")
    )

    with no_backoff_delay(), patched(http_client_module.requests, "post", always_fail_post):

        try:
            HTTPClient().post(
                url="https://example.invalid",
                headers={},
                payload={},
            )
        except requests.exceptions.ConnectionError:
            assert always_fail_post.calls["count"] == http_client_module.RETRY_ATTEMPTS
            return

        raise AssertionError(
            "Expected ConnectionError after exhausting retry attempts"
        )


def test_http_client_retries_on_5xx_then_succeeds():

    flaky_get = make_flaky_get(fail_times=2, fail_status=503, success_status=200)

    with no_backoff_delay(), patched(http_client_module.requests, "get", flaky_get):

        response = HTTPClient().get(url="https://example.invalid", headers={})

        assert response.status_code == 200
        assert flaky_get.calls["count"] == 3


def test_http_client_does_not_retry_non_transient_4xx():

    calls = {"count": 0}

    def bad_request_get(url, headers, timeout):

        calls["count"] += 1

        return make_status_response(400)

    with no_backoff_delay(), patched(http_client_module.requests, "get", bad_request_get):

        response = HTTPClient().get(url="https://example.invalid", headers={})

        assert response.status_code == 400
        assert calls["count"] == 1


def test_http_client_does_not_retry_non_request_exceptions():

    calls = {"count": 0}

    def broken_get(url, headers, timeout):

        calls["count"] += 1

        raise TypeError("not a network error")

    with no_backoff_delay(), patched(http_client_module.requests, "get", broken_get):

        try:
            HTTPClient().get(url="https://example.invalid", headers={})
        except TypeError:
            assert calls["count"] == 1
            return

        raise AssertionError("Expected TypeError to propagate without retrying")


if __name__ == "__main__":

    test_unit_is_retried_up_to_max_retries_then_left_alone()
    test_unit_succeeding_before_retry_limit_still_completes()
    test_has_retryable_work_true_before_limit_reached()
    test_has_retryable_work_false_once_limit_exhausted()
    test_resume_short_circuits_before_execute_once_exhausted()
    test_resume_reconciles_a_stale_running_unit_and_retries_it()
    test_job_reaches_failed_state_after_repeated_crashes_instead_of_freezing()
    test_http_client_retries_transient_failures_then_succeeds()
    test_http_client_gives_up_after_max_attempts()
    test_http_client_retries_on_5xx_then_succeeds()
    test_http_client_does_not_retry_non_transient_4xx()
    test_http_client_does_not_retry_non_request_exceptions()

    print("Retry engine tests passed")
