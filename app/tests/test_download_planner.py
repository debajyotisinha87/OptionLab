from datetime import datetime

from app.models.job import DownloadJob
from app.planner.download_planner import DownloadPlanner

job = DownloadJob(
    job_id="JOB-000001",
    underlying="NIFTY",
    expiry_type="MONTH",
    option_types=["CALL", "PUT"],
    strike_from=-10,
    strike_to=10,
    start_date="2025-01-01",
    end_date="2025-03-31",
    created_at=datetime.now(),
)

planner = DownloadPlanner()

plan = planner.create_plan(job)

print(f"Total Batches : {len(plan)}")

for batch in plan:
    print(batch)