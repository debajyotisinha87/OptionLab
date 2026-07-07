from datetime import datetime

from app.models.job import DownloadJob


job = DownloadJob(
    job_id="JOB-000001",
    underlying="NIFTY",
    expiry_type="MONTH",
    option_types=["CALL", "PUT"],
    strike_from=-10,
    strike_to=10,
    start_date="2021-01-01",
    end_date="2025-12-31",
    created_at=datetime.now(),
)

print(job)