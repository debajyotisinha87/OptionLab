# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OptionLab is a Python platform that downloads historical options data from the DhanHQ broker API, validates it, and stores it in DuckDB. It is the foundation for a longer-term quant platform (strategy engine, backtesting, paper/live trading) but today it is **only** a historical data downloader.

`PROJECT_CONTEXT.md` (repo root) is the authoritative, always-current source of truth for project state (current sprint/task, completed vs. upcoming work, full architecture rules) — read it before making non-trivial changes. `PROJECT_RULES.md`, `ARCHITECTURE.md`, and `docs/DECISIONS.md` (ADRs) are supplementary but generally in sync with it.

## Commands

There is no build step (pure Python, no packaging config). No linter or formatter config is checked in either, despite CONTRIBUTING.md mentioning Black — run at your own discretion if asked.

**Install dependencies:**
```bash
python -m venv .venv
pip install -r requirements.txt
```
`requirements.txt` is saved as UTF-16 (BOM) rather than UTF-8 — this is unusual but pip handles it. If you regenerate this file (e.g. `pip freeze`), make sure you don't silently flip it to UTF-8 in a way that breaks an existing workflow depending on the encoding; just note the fact if you touch it.

**Run the app:**
```bash
python -m app.main
```
This currently just prints a banner and calls `DhanAPI.test_connection()` — it makes a real network call to `https://api.dhan.co/v2/fundlimit` using credentials from `.env`.

**Tests — there is no pytest.** `pytest` is not in `requirements.txt` and is not installed. Most files under `app/tests/` are standalone scripts, not pytest suites: they run assertions (or just print output) at module level and are executed directly, e.g.:
```bash
python -m app.tests.test_download_planner
python -m app.tests.test_manifest_integration
```
Only `test_manifest_integration.py` uses real `assert`-based `test_*()` functions with an `if __name__ == "__main__"` runner — treat it as the template for new tests. Others (`test_job.py`, `test_download_planner.py`) just construct objects and print them; they "pass" if they don't raise.

Be careful before running tests/scripts that touch live resources:
- `test_repository.py`, `test_database.py` connect to the real `database/optionlab.duckdb`.
- `test_download_engine.py` and `app/downloader/download_day.py` perform **real API calls to DhanHQ** and write to the real database.
- Prefer the pure/offline ones (`test_job.py`, `test_download_planner.py`, `test_validator.py`, `test_manifest_integration.py`) when just sanity-checking logic.

## Architecture

The download pipeline is a strict, one-directional layer chain — do not skip layers or move logic to the wrong layer:

```
DownloadJob → DownloadPlanner → DownloadBatch → PayloadBuilder → DownloadEngine
    → DownloadService → RollingOptionAPI (DhanHQ) → DataNormalizer → DataValidator
    → Repository → DuckDB (+ download_manifest)
```

Layer responsibilities (from `PROJECT_CONTEXT.md` / `PROJECT_RULES.md` — treat as hard rules, not suggestions):

- **`app/api`** (`DhanAPI` → `RollingOptionAPI`, `HTTPClient`): only talks to DhanHQ over HTTP. No business logic.
- **`app/builders`** (`PayloadBuilder`): pure function turning a `DownloadJob`/`DownloadBatch`/option type into the DhanHQ request payload. Never performs I/O.
- **`app/planner`** (`DownloadPlanner`): splits a job's date range into ≤30-day `DownloadBatch` chunks. Never talks to the API or DB.
- **`app/downloader`** (`DownloadEngine`): top-level orchestrator. Iterates batches × option types, checks the manifest to skip completed work, delegates the actual download to `DownloadService`, and updates manifest status (`PENDING → RUNNING → COMPLETED`/`FAILED`). Contains **no SQL** and **no API details** directly (it calls the Repository/Service instead).
- **`app/services`** (`DownloadService`): does one batch end-to-end — call API, normalize, validate, insert via Repository — and returns a structured result dict (`{"success", "downloaded_rows", "inserted_rows", "error"}`) rather than raising/booleans. Follow this dict-result convention for new code in this layer.
- **`app/storage`** (`DataNormalizer`, `CSVWriter`): normalizes raw API JSON into the canonical `option_data` DataFrame shape; CSV is export-only, never the source of truth.
- **`app/validator`** (`DataValidator`): checks a normalized DataFrame (empty, required columns, nulls, duplicate timestamps, OHLC consistency) and returns a `ValidationReport` (`passed`, `errors`, `warnings`).
- **`app/database`** (`Repository`, `DuckDBManager`): **all SQL lives here and only here.** Table DDL lives in `app/database/schema/*.sql` and is applied via `Repository.execute_sql_file()`. No other module should construct SQL.
- **`app/models`**: plain `@dataclass` models (`DownloadJob`, `DownloadBatch`, `ValidationReport`, etc.) with no business logic. `JobStatus` is a `str, Enum` in `app/models/enums/`.

`app/downloader/manager.py` (`DownloadManager`) and `app/downloader/download_day.py` are earlier, superseded prototypes of the batching/download logic from before the `DownloadPlanner`/`DownloadEngine`/`DownloadService` split — they are not wired into the current pipeline (`DownloadEngine` doesn't use them). Don't extend them; treat `DownloadPlanner`/`DownloadEngine`/`DownloadService` as canonical.

### Database

- Single DuckDB file at `database/optionlab.duckdb` (gitignored).
- Key tables: `option_data` (the actual OHLC/IV/OI candles), `download_manifest` (per-batch/option-type/strike-offset status tracking used for resume/retry), `download_jobs`.
- The manifest is keyed on `(job_id, batch_number, option_type, strike_offset)`; `DownloadEngine.is_download_completed()` uses `get_manifest_status()` against this key to make reruns idempotent — preserve this idempotency when touching the manifest flow.

### Configuration

`app/config/config.py` loads `.env` (via `python-dotenv`) and exposes `DHAN_CLIENT_ID` / `DHAN_ACCESS_TOKEN`, plus auto-creates `data/`, `database/`, `logs/` directories on import. Never hardcode credentials; never commit `.env`.

## Coding conventions

(From `PROJECT_RULES.md` / `docs/CODING_STANDARDS.md`, and reflected consistently in existing code — follow them for consistency.)

- Python 3.14+, PEP8, full type hints on function signatures.
- Classes `PascalCase`, functions/variables `snake_case`, constants `UPPER_CASE`.
- Models are `@dataclass`; enums subclass `str, Enum`.
- Public classes/methods get docstrings (existing code is inconsistent about this — new code should have them).
- Service/engine methods that can fail return a structured result dict rather than raising or returning a bare bool (see `DownloadService.download()`).
- Commit style: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:` — small, frequent commits.
