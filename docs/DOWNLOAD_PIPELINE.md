# Download Pipeline

The historical downloader follows this sequence.

DownloadJob

↓

DownloadPlanner

↓

DownloadBatch

↓

PayloadBuilder

↓

DownloadService

↓

RollingOptionAPI

↓

DataNormalizer

↓

DataValidator

↓

Repository

↓

DuckDB

↓

DownloadManifest

---

Future

↓

Retry Engine

↓

Resume Engine

↓

Progress Engine