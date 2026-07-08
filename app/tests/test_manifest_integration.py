from datetime import datetime

from app.downloader.download_engine import DownloadEngine
from app.models.download_batch import DownloadBatch
from app.models.job import DownloadJob


class FakeRepository:

    def __init__(self, manifest_status=None):

        self.events = []
        self.manifest_status = manifest_status

    def create_manifest_entry(self, **kwargs):

        self.events.append(("PENDING", kwargs))

    def get_manifest_status(self, **kwargs):

        return self.manifest_status

    def get_manifest_retry_count(self, **kwargs):

        return 0

    def mark_batch_started(self, **kwargs):

        self.events.append(("RUNNING", kwargs))

    def mark_batch_completed(self, **kwargs):

        self.events.append(("COMPLETED", kwargs))

    def mark_batch_failed(self, **kwargs):

        self.events.append(("FAILED", kwargs))


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


class FailedDownloadService:

    def download(self, payload):

        return {
            "success": False,
            "downloaded_rows": 0,
            "inserted_rows": 0,
            "error": "Download failed",
        }


class CountingDownloadService:

    def __init__(self):

        self.download_count = 0

    def download(self, payload):

        self.download_count += 1

        return {
            "success": True,
            "downloaded_rows": 10,
            "inserted_rows": 10,
            "error": None,
        }


def create_test_job():

    return DownloadJob(
        job_id="JOB-MANIFEST-TEST",
        underlying="NIFTY",
        expiry_type="MONTH",
        option_types=["CALL"],
        strike_from=-1,
        strike_to=1,
        start_date="2025-01-01",
        end_date="2025-01-01",
        created_at=datetime.now(),
    )


def create_test_batch():

    return DownloadBatch(
        batch_number=1,
        from_date="2025-01-01",
        to_date="2025-01-01",
    )


def create_test_engine(download_service, manifest_status=None):

    engine = DownloadEngine.__new__(DownloadEngine)
    engine.repo = FakeRepository(manifest_status=manifest_status)
    engine.service = download_service
    engine.progress = FakeProgressReporter()

    return engine


def test_manifest_completed_flow():

    engine = create_test_engine(SuccessfulDownloadService())

    engine.process_option_type(
        job=create_test_job(),
        batch=create_test_batch(),
        option_type="CALL",
    )

    statuses = [
        event[0]
        for event in engine.repo.events
    ]

    assert statuses == [
        "PENDING",
        "RUNNING",
        "COMPLETED",
    ]

    manifest_entry = engine.repo.events[0][1]

    assert manifest_entry["option_type"] == "CALL"
    assert manifest_entry["strike_offset"] == 0


def test_manifest_failed_flow():

    engine = create_test_engine(FailedDownloadService())

    engine.process_option_type(
        job=create_test_job(),
        batch=create_test_batch(),
        option_type="CALL",
    )

    statuses = [
        event[0]
        for event in engine.repo.events
    ]

    assert statuses == [
        "PENDING",
        "RUNNING",
        "FAILED",
    ]

    failed_event = engine.repo.events[-1][1]

    assert failed_event["error_message"] == "Download failed"


def test_completed_manifest_entry_is_skipped():

    service = CountingDownloadService()
    engine = create_test_engine(
        download_service=service,
        manifest_status="COMPLETED",
    )

    engine.process_option_type(
        job=create_test_job(),
        batch=create_test_batch(),
        option_type="CALL",
    )

    assert service.download_count == 0
    assert engine.repo.events == []


if __name__ == "__main__":

    test_manifest_completed_flow()
    test_manifest_failed_flow()
    test_completed_manifest_entry_is_skipped()

    print("Manifest integration tests passed")
