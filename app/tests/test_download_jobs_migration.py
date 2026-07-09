from datetime import datetime

from app.database.repository import Repository

JOB_ID = "JOB-PARQUET-MIGRATION-TEST"


def test_create_download_jobs_table_is_idempotent_and_adds_the_column():

    repo = Repository()

    repo.create_download_jobs_table()
    repo.create_download_jobs_table()

    columns = repo.query("DESCRIBE download_jobs")["column_name"].tolist()

    assert columns.count("parquet_output_dir") == 1


def test_parquet_output_dir_round_trips_through_save_job_and_get_job():

    repo = Repository()
    repo.create_download_jobs_table()

    repo.save_job(
        job_id=JOB_ID,
        underlying="NIFTY",
        instrument="OPTIDX",
        expiry_type="MONTH",
        option_types="CALL",
        strike_from=0,
        strike_to=0,
        interval=1,
        start_date="2025-01-01",
        end_date="2025-01-01",
        created_at=datetime.now(),
        parquet_output_dir="C:/exports/nifty",
    )

    job = repo.get_job(JOB_ID)

    assert job is not None
    assert job["parquet_output_dir"] == "C:/exports/nifty"


def test_check_job_reusable_rejects_a_mismatched_parquet_output_dir():

    repo = Repository()
    repo.create_download_jobs_table()

    # Re-saving the same job_id/params but a different parquet_output_dir
    # than test_parquet_output_dir_round_trips_through_save_job_and_get_job
    # left behind must be rejected as a conflict, the same way a
    # different underlying or date range would be.
    try:
        repo.check_job_reusable(
            JOB_ID,
            "NIFTY",
            "MONTH",
            "CALL",
            0,
            0,
            "2025-01-01",
            "2025-01-01",
            "C:/exports/different-folder",
        )
    except ValueError as exc:
        assert JOB_ID in str(exc)
    else:
        raise AssertionError(
            "Expected ValueError for a mismatched parquet_output_dir"
        )

    # Matching parquet_output_dir (including None-vs-None) must not raise.
    repo.check_job_reusable(
        JOB_ID,
        "NIFTY",
        "MONTH",
        "CALL",
        0,
        0,
        "2025-01-01",
        "2025-01-01",
        "C:/exports/nifty",
    )


if __name__ == "__main__":

    test_create_download_jobs_table_is_idempotent_and_adds_the_column()
    test_parquet_output_dir_round_trips_through_save_job_and_get_job()
    test_check_job_reusable_rejects_a_mismatched_parquet_output_dir()

    print("Download jobs migration tests passed")
