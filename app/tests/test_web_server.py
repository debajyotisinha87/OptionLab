import os

from fastapi.testclient import TestClient

import app.web.server as server_module
from app.builders.payload_builder import PayloadBuilder


class FakeRepo:
    """By default get_job_progress() mirrors the job row's own
    completed_batches/failed_batches/total_rows, matching a terminal
    job where the two agree. Tests that need to prove progress is read
    live (not from the frozen row) override progress_by_id."""

    def __init__(self, jobs_by_id, progress_by_id=None):

        self._jobs_by_id = jobs_by_id
        self._progress_by_id = progress_by_id or {}

    def list_jobs(self):

        return list(self._jobs_by_id.values())

    def get_job(self, job_id):

        return self._jobs_by_id.get(job_id)

    def get_job_progress(self, job_id):

        if job_id in self._progress_by_id:

            return self._progress_by_id[job_id]

        job = self._jobs_by_id.get(job_id, {})

        return {
            "completed_batches": job.get("completed_batches", 0),
            "failed_batches": job.get("failed_batches", 0),
            "total_rows": job.get("total_rows", 0),
        }


class FakeEngine:

    def __init__(self, repo):

        self.repo = repo


class FakeJobRunner:
    """Zero-arg constructible (app/web/server.py's lifespan calls
    JobRunner() directly), configured per test via class attributes on
    a small subclass - same pattern used for FakeDownloadEngine in
    app/tests/test_job_runner.py and test_cli.py."""

    instances = []
    jobs_by_id = {}
    progress_by_id = {}
    start_error = None
    resume_error = None
    start_many_error = None
    queue_progress_value = None

    def __init__(self):

        self.started = []
        self.resumed = []
        self.started_many = []
        self._current_job_id = None

        self.repo = FakeRepo(type(self).jobs_by_id, type(self).progress_by_id)
        self.engine = FakeEngine(self.repo)

        type(self).instances.append(self)

    @property
    def current_job_id(self):

        return self._current_job_id

    @property
    def queue_progress(self):

        return type(self).queue_progress_value

    def start(self, job):

        if type(self).start_error is not None:

            raise type(self).start_error

        self.started.append(job)

    def start_resume(self, job_id):

        if type(self).resume_error is not None:

            raise type(self).resume_error

        self.resumed.append(job_id)

    def start_many(self, jobs):

        if type(self).start_many_error is not None:

            raise type(self).start_many_error

        self.started_many.append(jobs)


class FakeJob:

    def __init__(self, job_id):

        self.job_id = job_id


class FakeResponse:

    def __init__(self, status_code):

        self.status_code = status_code


class FakeDhanAPI:

    status_code = 200

    def test_connection(self):

        return FakeResponse(type(self).status_code)


class FakeSyncPlanner:

    status_result = {"combos": [], "up_to_date": True}
    plan_jobs_result = []

    @staticmethod
    def status(repo):

        return dict(FakeSyncPlanner.status_result)

    @staticmethod
    def plan_jobs(repo):

        return list(FakeSyncPlanner.plan_jobs_result)


def sample_job(job_id="JOB-1", status="RUNNING", completed_batches=3, failed_batches=0):

    return {
        "job_id": job_id,
        "underlying": "NIFTY",
        "expiry_type": "MONTH",
        "option_types": "CALL,PUT",
        "strike_from": -1,
        "strike_to": 1,
        "start_date": "2025-01-01",
        "end_date": "2025-01-31",
        "status": status,
        "total_batches": 6,
        "completed_batches": completed_batches,
        "failed_batches": failed_batches,
        "total_rows": 1500,
        "created_at": None,
        "started_at": None,
        "completed_at": None,
    }


VALID_PAYLOAD = {
    "underlying": "NIFTY",
    "expiry_type": "MONTH",
    "option_types": ["CALL"],
    "start_date": "2025-01-01",
    "end_date": "2025-01-01",
}


def with_fake_job_runner(runner_class, fn):
    """Patches the JobRunner CLASS referenced by app/web/server.py's
    lifespan (not just the get_job_runner dependency), so entering the
    TestClient context (which runs the real lifespan startup event)
    never touches the real DownloadEngine/DuckDB connection."""

    original = server_module.JobRunner
    server_module.JobRunner = runner_class

    try:

        with TestClient(server_module.app) as client:

            return fn(client)

    finally:

        server_module.JobRunner = original


def test_list_underlyings_returns_the_supported_set():

    class Runner(FakeJobRunner):
        instances = []

    def run(client):

        response = client.get("/api/underlyings")

        assert response.status_code == 200
        assert "NIFTY" in response.json()
        assert "BANKNIFTY" in response.json()

    with_fake_job_runner(Runner, run)


def test_list_jobs_returns_serialized_jobs():

    class Runner(FakeJobRunner):
        instances = []
        jobs_by_id = {"JOB-1": sample_job()}

    def run(client):

        response = client.get("/api/jobs")

        assert response.status_code == 200

        jobs = response.json()
        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "JOB-1"
        assert jobs[0]["percent_complete"] == 50.0

    with_fake_job_runner(Runner, run)


def test_get_job_returns_404_for_unknown_job():

    class Runner(FakeJobRunner):
        instances = []
        jobs_by_id = {}

    def run(client):

        response = client.get("/api/jobs/DOES-NOT-EXIST")

        assert response.status_code == 404

    with_fake_job_runner(Runner, run)


def test_get_job_marks_is_running_for_the_active_job():

    class Runner(FakeJobRunner):
        instances = []
        jobs_by_id = {"JOB-1": sample_job(status="RUNNING")}

        def __init__(self):
            super().__init__()
            self._current_job_id = "JOB-1"

    def run(client):

        response = client.get("/api/jobs/JOB-1")

        assert response.status_code == 200
        assert response.json()["is_running"] is True

    with_fake_job_runner(Runner, run)


def test_create_job_dispatches_to_job_runner_start():

    class Runner(FakeJobRunner):
        instances = []

    def run(client):

        response = client.post("/api/jobs", json=VALID_PAYLOAD)

        assert response.status_code == 202
        assert response.json()["job_id"] == "NIFTY-2025-01-01-2025-01-01"

        runner = Runner.instances[-1]
        assert len(runner.started) == 1
        assert runner.started[0].underlying == "NIFTY"
        assert runner.started[0].option_types == ["CALL"]

        # strike_from/strike_to are no longer a client-settable field -
        # every download always covers DhanHQ's full supported range.
        assert runner.started[0].strike_from == PayloadBuilder.MIN_STRIKE_OFFSET
        assert runner.started[0].strike_to == PayloadBuilder.MAX_STRIKE_OFFSET

    with_fake_job_runner(Runner, run)


def test_create_job_passes_parquet_output_dir_through_to_the_job():

    class Runner(FakeJobRunner):
        instances = []

    def run(client):

        payload = dict(VALID_PAYLOAD, parquet_output_dir="C:/exports/nifty")

        response = client.post("/api/jobs", json=payload)

        assert response.status_code == 202

        runner = Runner.instances[-1]
        assert runner.started[0].parquet_output_dir == "C:/exports/nifty"

    with_fake_job_runner(Runner, run)


def test_create_job_uses_the_explicit_job_id_when_given():

    class Runner(FakeJobRunner):
        instances = []

    def run(client):

        payload = dict(VALID_PAYLOAD, job_id="MY-JOB")

        response = client.post("/api/jobs", json=payload)

        assert response.status_code == 202
        assert response.json()["job_id"] == "MY-JOB"

    with_fake_job_runner(Runner, run)


def test_create_job_rejects_an_unsupported_underlying():

    class Runner(FakeJobRunner):
        instances = []

    def run(client):

        payload = dict(VALID_PAYLOAD, underlying="RELIANCE")

        response = client.post("/api/jobs", json=payload)

        assert response.status_code == 422
        assert Runner.instances == [] or Runner.instances[-1].started == []

    with_fake_job_runner(Runner, run)


def test_create_job_rejects_an_invalid_date():

    class Runner(FakeJobRunner):
        instances = []

    def run(client):

        payload = dict(VALID_PAYLOAD, start_date="not-a-date")

        response = client.post("/api/jobs", json=payload)

        assert response.status_code == 422

    with_fake_job_runner(Runner, run)


def test_create_job_rejects_empty_option_types():

    class Runner(FakeJobRunner):
        instances = []

    def run(client):

        payload = dict(VALID_PAYLOAD, option_types=[])

        response = client.post("/api/jobs", json=payload)

        assert response.status_code == 422

    with_fake_job_runner(Runner, run)


def test_create_job_returns_409_when_a_job_is_already_running():

    class Runner(FakeJobRunner):
        instances = []
        start_error = server_module.JobAlreadyRunningError("Job 'X' is already running")

    def run(client):

        response = client.post("/api/jobs", json=VALID_PAYLOAD)

        assert response.status_code == 409

    with_fake_job_runner(Runner, run)


def test_create_job_returns_400_for_a_value_error_from_start():

    class Runner(FakeJobRunner):
        instances = []
        start_error = ValueError("strike_from must be <= strike_to")

    def run(client):

        response = client.post("/api/jobs", json=VALID_PAYLOAD)

        assert response.status_code == 400

    with_fake_job_runner(Runner, run)


def test_resume_job_dispatches_to_job_runner_start_resume():

    class Runner(FakeJobRunner):
        instances = []

    def run(client):

        response = client.post("/api/jobs/JOB-1/resume")

        assert response.status_code == 202

        runner = Runner.instances[-1]
        assert runner.resumed == ["JOB-1"]

    with_fake_job_runner(Runner, run)


def test_resume_job_returns_404_for_unknown_job_id():

    class Runner(FakeJobRunner):
        instances = []
        resume_error = ValueError("Unknown job_id: JOB-1")

    def run(client):

        response = client.post("/api/jobs/JOB-1/resume")

        assert response.status_code == 404

    with_fake_job_runner(Runner, run)


def test_resume_job_returns_409_when_a_job_is_already_running():

    class Runner(FakeJobRunner):
        instances = []
        resume_error = server_module.JobAlreadyRunningError("Job 'X' is already running")

    def run(client):

        response = client.post("/api/jobs/JOB-1/resume")

        assert response.status_code == 409

    with_fake_job_runner(Runner, run)


def test_index_serves_the_frontend():

    class Runner(FakeJobRunner):
        instances = []

    def run(client):

        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    with_fake_job_runner(Runner, run)


def test_browse_folder_returns_the_picked_path():

    class Runner(FakeJobRunner):
        instances = []

    def fake_pick_folder(initial_dir=None):
        return "C:/exports/nifty"

    def run(client):

        original = server_module.pick_folder
        server_module.pick_folder = fake_pick_folder

        try:
            response = client.post("/api/browse-folder", json={})
        finally:
            server_module.pick_folder = original

        assert response.status_code == 200
        assert response.json() == {"path": "C:/exports/nifty"}

    with_fake_job_runner(Runner, run)


def test_browse_folder_returns_null_path_when_cancelled():

    class Runner(FakeJobRunner):
        instances = []

    def fake_pick_folder(initial_dir=None):
        return None

    def run(client):

        original = server_module.pick_folder
        server_module.pick_folder = fake_pick_folder

        try:
            response = client.post("/api/browse-folder", json={})
        finally:
            server_module.pick_folder = original

        assert response.status_code == 200
        assert response.json() == {"path": None}

    with_fake_job_runner(Runner, run)


def test_browse_folder_returns_500_when_the_dialog_fails():

    class Runner(FakeJobRunner):
        instances = []

    def failing_pick_folder(initial_dir=None):
        raise RuntimeError("tkinter unavailable")

    def run(client):

        original = server_module.pick_folder
        server_module.pick_folder = failing_pick_folder

        try:
            response = client.post("/api/browse-folder", json={})
        finally:
            server_module.pick_folder = original

        assert response.status_code == 500

    with_fake_job_runner(Runner, run)


def test_list_jobs_reports_live_progress_not_the_frozen_job_row():
    """completed_batches/failed_batches on the job row are only
    written once, when a job finishes - list_jobs()/get_job() must
    report get_job_progress()'s live manifest aggregate instead, or a
    RUNNING job's progress bar would stay frozen for its whole run."""

    class Runner(FakeJobRunner):
        instances = []
        jobs_by_id = {
            "JOB-1": sample_job(
                status="RUNNING", completed_batches=0, failed_batches=0
            )
        }
        progress_by_id = {
            "JOB-1": {
                "completed_batches": 4,
                "failed_batches": 1,
                "total_rows": 999,
            }
        }

    def run(client):

        response = client.get("/api/jobs/JOB-1")

        assert response.status_code == 200

        body = response.json()
        assert body["completed_batches"] == 4
        assert body["failed_batches"] == 1
        assert body["total_rows"] == 999
        assert body["percent_complete"] == round(100 * 5 / 6, 1)

    with_fake_job_runner(Runner, run)


def test_token_status_reports_valid_when_connection_succeeds():

    class Runner(FakeJobRunner):
        instances = []

    def run(client):

        original = server_module.DhanAPI
        server_module.DhanAPI = FakeDhanAPI
        FakeDhanAPI.status_code = 200

        try:
            response = client.get("/api/token-status")
        finally:
            server_module.DhanAPI = original

        assert response.status_code == 200
        assert response.json() == {"valid": True}

    with_fake_job_runner(Runner, run)


def test_token_status_reports_invalid_when_connection_fails():

    class Runner(FakeJobRunner):
        instances = []

    def run(client):

        original = server_module.DhanAPI
        server_module.DhanAPI = FakeDhanAPI
        FakeDhanAPI.status_code = 401

        try:
            response = client.get("/api/token-status")
        finally:
            server_module.DhanAPI = original

        assert response.json() == {"valid": False}

    with_fake_job_runner(Runner, run)


def test_update_token_writes_env_and_updates_process_env():

    class Runner(FakeJobRunner):
        instances = []

    def run(client):

        set_key_calls = []

        def fake_set_key(path, key, value, quote_mode=None):
            set_key_calls.append((path, key, value, quote_mode))

        original_set_key = server_module.set_key
        original_dhan_api = server_module.DhanAPI
        server_module.set_key = fake_set_key
        server_module.DhanAPI = FakeDhanAPI
        FakeDhanAPI.status_code = 200

        original_env = os.environ.get("DHAN_ACCESS_TOKEN")

        try:
            response = client.post(
                "/api/token", json={"access_token": "NEW-TOKEN-VALUE"}
            )
        finally:
            server_module.set_key = original_set_key
            server_module.DhanAPI = original_dhan_api
            if original_env is not None:
                os.environ["DHAN_ACCESS_TOKEN"] = original_env
            else:
                os.environ.pop("DHAN_ACCESS_TOKEN", None)

        assert response.status_code == 200
        assert response.json() == {"valid": True}

        assert len(set_key_calls) == 1
        _, key, value, quote_mode = set_key_calls[0]
        assert key == "DHAN_ACCESS_TOKEN"
        assert value == "NEW-TOKEN-VALUE"
        assert quote_mode == "never"

        # The token value must never be echoed back in the response.
        assert "NEW-TOKEN-VALUE" not in response.text

    with_fake_job_runner(Runner, run)


def test_update_token_rejects_a_blank_value():

    class Runner(FakeJobRunner):
        instances = []

    def run(client):

        response = client.post("/api/token", json={"access_token": "   "})

        assert response.status_code == 422

    with_fake_job_runner(Runner, run)


def test_sync_status_reports_planner_status_when_no_queue_active():

    class Runner(FakeJobRunner):
        instances = []

    def run(client):

        original = server_module.SyncPlanner
        server_module.SyncPlanner = FakeSyncPlanner
        FakeSyncPlanner.status_result = {
            "combos": [
                {
                    "underlying": "NIFTY",
                    "expiry_type": "WEEK",
                    "latest_date": None,
                    "up_to_date": False,
                }
            ],
            "up_to_date": False,
        }

        try:
            response = client.get("/api/sync-status")
        finally:
            server_module.SyncPlanner = original

        assert response.status_code == 200

        body = response.json()
        assert body["up_to_date"] is False
        assert body["queue"] is None

    with_fake_job_runner(Runner, run)


def test_sync_status_includes_queue_progress_and_current_job_when_syncing():

    job_id = "NIFTY-SYNC-WEEK-2020-01-01-2025-01-01"

    class Runner(FakeJobRunner):
        instances = []
        jobs_by_id = {job_id: sample_job(job_id=job_id, status="RUNNING")}
        queue_progress_value = {"position": 2, "total": 4}

        def __init__(self):
            super().__init__()
            self._current_job_id = job_id

    def run(client):

        original = server_module.SyncPlanner
        server_module.SyncPlanner = FakeSyncPlanner
        FakeSyncPlanner.status_result = {"combos": [], "up_to_date": False}

        try:
            response = client.get("/api/sync-status")
        finally:
            server_module.SyncPlanner = original

        assert response.status_code == 200

        body = response.json()
        assert body["queue"]["position"] == 2
        assert body["queue"]["total"] == 4
        assert body["queue"]["current_job"]["job_id"] == job_id

    with_fake_job_runner(Runner, run)


def test_start_sync_returns_up_to_date_when_nothing_to_sync():

    class Runner(FakeJobRunner):
        instances = []

    def run(client):

        original = server_module.SyncPlanner
        server_module.SyncPlanner = FakeSyncPlanner
        FakeSyncPlanner.plan_jobs_result = []

        try:
            response = client.post("/api/sync")
        finally:
            server_module.SyncPlanner = original

        assert response.status_code == 202
        assert response.json() == {"job_ids": [], "status": "up_to_date"}

        runner = Runner.instances[-1]
        assert runner.started_many == []

    with_fake_job_runner(Runner, run)


def test_start_sync_dispatches_planned_jobs_to_start_many():

    class Runner(FakeJobRunner):
        instances = []

    def run(client):

        job = FakeJob(job_id="NIFTY-SYNC-WEEK-2020-01-01-2025-01-01")

        original = server_module.SyncPlanner
        server_module.SyncPlanner = FakeSyncPlanner
        FakeSyncPlanner.plan_jobs_result = [job]

        try:
            response = client.post("/api/sync")
        finally:
            server_module.SyncPlanner = original

        assert response.status_code == 202

        body = response.json()
        assert body["status"] == "started"
        assert body["job_ids"] == [job.job_id]

        runner = Runner.instances[-1]
        assert runner.started_many == [[job]]

    with_fake_job_runner(Runner, run)


def test_start_sync_returns_409_when_a_job_is_already_running():

    class Runner(FakeJobRunner):
        instances = []
        start_many_error = server_module.JobAlreadyRunningError(
            "Job 'X' is already running"
        )

    def run(client):

        original = server_module.SyncPlanner
        server_module.SyncPlanner = FakeSyncPlanner
        FakeSyncPlanner.plan_jobs_result = [FakeJob(job_id="JOB-X")]

        try:
            response = client.post("/api/sync")
        finally:
            server_module.SyncPlanner = original

        assert response.status_code == 409

    with_fake_job_runner(Runner, run)


def test_lifespan_logs_and_reraises_when_job_runner_construction_fails():

    class RaisingJobRunner:

        def __init__(self):

            raise RuntimeError("simulated DuckDB connection failure")

    original = server_module.JobRunner
    server_module.JobRunner = RaisingJobRunner

    try:

        try:
            with TestClient(server_module.app):
                pass
        except RuntimeError as exc:
            assert "simulated DuckDB connection failure" in str(exc)
        else:
            raise AssertionError("Expected RuntimeError from lifespan startup")

    finally:
        server_module.JobRunner = original


if __name__ == "__main__":

    test_list_underlyings_returns_the_supported_set()
    test_list_jobs_returns_serialized_jobs()
    test_get_job_returns_404_for_unknown_job()
    test_get_job_marks_is_running_for_the_active_job()
    test_create_job_dispatches_to_job_runner_start()
    test_create_job_passes_parquet_output_dir_through_to_the_job()
    test_create_job_uses_the_explicit_job_id_when_given()
    test_create_job_rejects_an_unsupported_underlying()
    test_create_job_rejects_an_invalid_date()
    test_create_job_rejects_empty_option_types()
    test_create_job_returns_409_when_a_job_is_already_running()
    test_create_job_returns_400_for_a_value_error_from_start()
    test_resume_job_dispatches_to_job_runner_start_resume()
    test_resume_job_returns_404_for_unknown_job_id()
    test_resume_job_returns_409_when_a_job_is_already_running()
    test_index_serves_the_frontend()
    test_browse_folder_returns_the_picked_path()
    test_browse_folder_returns_null_path_when_cancelled()
    test_browse_folder_returns_500_when_the_dialog_fails()
    test_list_jobs_reports_live_progress_not_the_frozen_job_row()
    test_token_status_reports_valid_when_connection_succeeds()
    test_token_status_reports_invalid_when_connection_fails()
    test_update_token_writes_env_and_updates_process_env()
    test_update_token_rejects_a_blank_value()
    test_sync_status_reports_planner_status_when_no_queue_active()
    test_sync_status_includes_queue_progress_and_current_job_when_syncing()
    test_start_sync_returns_up_to_date_when_nothing_to_sync()
    test_start_sync_dispatches_planned_jobs_to_start_many()
    test_start_sync_returns_409_when_a_job_is_already_running()
    test_lifespan_logs_and_reraises_when_job_runner_construction_fails()

    print("Web server tests passed")
