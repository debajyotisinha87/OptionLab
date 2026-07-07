from app.downloader.manager import DownloadManager


ranges = DownloadManager.split_date_range(
    "2025-01-01",
    "2025-04-15",
)

for r in ranges:
    print(r)