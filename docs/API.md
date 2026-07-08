# OptionLab Internal API

This document describes the internal modules used by OptionLab.

---

# RollingOptionAPI

Location

app/api/rolling_option.py

Purpose

Downloads historical option data from DhanHQ.

Methods

fetch(payload)

Returns

Dictionary returned by DhanHQ.

---

# DownloadPlanner

Location

app/planner/download_planner.py

Purpose

Splits a DownloadJob into multiple DownloadBatch objects.

Methods

create_plan(job)

Returns

list[DownloadBatch]

---

# DownloadEngine

Location

app/downloader/download_engine.py

Purpose

Coordinates the complete download pipeline.

Responsibilities

- Get batches from planner
- Build payload
- Download data
- Validate
- Store
- Update manifest

---

# PayloadBuilder

Location

app/builders/payload_builder.py

Purpose

Constructs broker-specific payloads.

Methods

build(job, batch, option_type)

---

# DownloadService

Location

app/services/download_service.py

Purpose

Downloads a single batch.

Responsibilities

- API Call
- Normalize
- Validate
- Store

---

# Repository

Location

app/database/repository.py

Purpose

Single point for all database operations.

---

# DataValidator

Location

app/validator/data_validator.py

Purpose

Ensures downloaded data is valid before storage.