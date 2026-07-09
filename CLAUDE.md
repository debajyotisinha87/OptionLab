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
python -m app.main test-connection
python -m app.main download --underlying NIFTY --expiry-type MONTH --option-types CALL,PUT --start-date 2025-01-01 --end-date 2025-03-31 [--job-id JOB-000001]
python -m app.main resume --job-id JOB-000001
python -m app.main sync
```
`app/main.py` is an argparse-based CLI with four subcommands. `test-connection` makes a real network call to `https://api.dhan.co/v2/fundlimit` using credentials from `.env`. `download` builds a `DownloadJob` and calls `DownloadEngine.run()`; if `--job-id` is omitted it defaults to `<underlying>-<start_date>-<end_date>`. `resume` calls `DownloadEngine.resume()` for an existing `job_id`. `sync` runs `SyncPlanner.plan_jobs()` synchronously (see "Auto-sync" below) — an explicit, manual CLI trigger for the same catch-up logic the web GUI's "Sync Data" button uses; it is never triggered automatically by `test-connection`/`download`/`resume`. All of `download`/`resume`/`sync` make real API calls and write to the real database — there's no dry-run mode. `--expiry-type` (case-insensitive) and `--option-types` are validated against DhanHQ's actual `/v2/charts/rollingoption` enum values (`WEEK`/`MONTH` and `CALL`/`PUT` respectively) so a typo fails fast at the CLI instead of at the live API call.

`--underlying` is validated against `app/constants/underlyings.py`'s `SUPPORTED_UNDERLYINGS` (currently NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY, SENSEX), which maps each to its real DhanHQ `securityId`/`exchangeSegment` — verified against Dhan's public instrument master CSV, not guessed. Before this mapping existed, `PayloadBuilder` hardcoded NIFTY's `securityId` for every request regardless of `--underlying`, so requesting e.g. BANKNIFTY silently downloaded NIFTY data. There is no `--strike-from`/`--strike-to` flag: every job always downloads DhanHQ's full supported strike range for index options (`PayloadBuilder.MIN_STRIKE_OFFSET`/`MAX_STRIKE_OFFSET`, currently ATM-10..ATM+10) — this isn't user-configurable by design (verified empirically against the live API this session: ATM±10 returns real data, ATM±11 and beyond returns an empty response for every offset tried up to ±40). `DownloadEngine.validate_job()` still checks the underlying and strike-range bounds before `run()`/`resume()` do any work, since `resume()` rebuilds a `DownloadJob` straight from the `download_jobs` table — this matters for jobs created before this range was fixed, or before the underlying-validation checks existed, which may still carry a different (narrower) strike range from when `--strike-from`/`--strike-to` were still user-settable. `app/validation.py` holds the framework-agnostic versions of the remaining checks (choice/list-choice/date/non-blank) shared between the CLI's argparse `type=` functions and the web GUI's Pydantic validators, so the two entry points can't silently drift on what counts as valid input.

**Run the web GUI:**
```bash
python -m app.web
```
Starts a local FastAPI server (`app/web/server.py`) at `http://127.0.0.1:8000` — a thin layer over the same `DownloadJob`/`DownloadEngine`/`Repository` the CLI uses, for starting jobs, watching live progress, and resuming from a browser instead of the command line. `app/web/job_runner.py`'s `JobRunner` owns a single `DownloadEngine()` for the process and enforces "one download job at a time" (a job runs in a background thread; a second `start()`/`start_resume()`/`start_many()` while one is active raises `JobAlreadyRunningError`, surfaced as HTTP 409). Because DuckDB only allows one connection per process to a given file, `DuckDBManager`/`Repository` share that single connection across the FastAPI threadpool and the background job thread via a `threading.RLock` (see `Repository._synchronized`) rather than opening per-request connections.

**Auto-sync (NIFTY/SENSEX):** the GUI's "Data Sync" card checks `GET /api/sync-status` on load and shows "Data Up to Date"/"Data Not Up to Date" + a "Sync Data" button — nothing runs automatically without that click. `app/autosync/sync_planner.py`'s `SyncPlanner` is scoped to a fixed set: `UNDERLYINGS = ["NIFTY", "SENSEX"]` × `EXPIRY_TYPES = ["WEEK", "MONTH"]` (4 combos), always both `CALL`/`PUT` and the full strike range. For each combo, `SyncPlanner.plan_jobs()` compares `Repository.get_latest_trade_date(symbol, expiry_flag)` (a live `MAX(trade_date)` query against `option_data`, not a job's own bookkeeping) to today and builds a fresh `DownloadJob` covering just the gap — `start_date = latest + 1 day` (or `GENESIS_DATE = "2020-01-01"` if no data exists yet), `end_date = today`, `parquet_output_dir = app/exports/parquet` always. This creates a **new** `DownloadJob` every sync rather than mutating an old one, because `DownloadEngine.resume()` cannot extend a job past its original `end_date` — confirmed by reading `resume()`/`has_retryable_work()`, which only replan the *stored* date range. `JobRunner.start_many(jobs)` runs the resulting list (0-4 jobs) sequentially in one background thread, exposed via `queue_progress` for the "job N of 4" progress bar; a failing job doesn't stop the rest of the queue. A first-ever backfill (empty DB) covers ~3.5 years × up to 4 combos × 21 strikes × 2 option types — several thousand API calls, likely 20-40+ minutes; later syncs only fetch the gap, so they're fast.

**Token health check:** `GET /api/token-status` calls the existing `DhanAPI().test_connection()` (real network call — the frontend only calls this on page load/after an update, not on a poll). If invalid, the GUI shows a paste-box; `POST /api/token` writes the new value via `python-dotenv`'s `set_key(ENV_PATH, "DHAN_ACCESS_TOKEN", value, quote_mode="never")` (matches `.env`'s existing unquoted style) and also sets `os.environ["DHAN_ACCESS_TOKEN"]` directly. This takes effect immediately, without restarting the process, because `DhanAPI.__init__` (`app/api/api_client.py`) reads `os.getenv(...)` live at construction time rather than importing `app.config.config`'s frozen import-time constants — every job constructs a fresh `RollingOptionAPI()`/`DhanAPI()`, so the very next job picks up a freshly-pasted token. Never log the token value on this path.

**Tests — there is no pytest.** `pytest` is not in `requirements.txt` and is not installed. Files under `app/tests/` are standalone scripts, not pytest suites, executed directly, e.g.:
```bash
python -m app.tests.test_download_planner
python -m app.tests.test_manifest_integration
```
Most newer files (`test_manifest_integration.py`, `test_resume_engine.py`, `test_retry_engine.py`, `test_progress_reporter.py`, `test_logging_config.py`, `test_cli.py`, `test_job_runner.py`, `test_web_server.py`, `test_e2e_cli.py`, `test_e2e_web.py`, `test_e2e_sync.py`, `test_parquet_writer.py`, `test_download_service.py`, `test_sync_planner.py`) use real `assert`-based `test_*()` functions with an `if __name__ == "__main__"` runner — treat these as the template for new tests, and use their monkeypatch-a-module-level-name pattern (e.g. `main_module.DownloadEngine = FakeDownloadEngine`) to fake out real DB/API/tqdm dependencies rather than adding mocking libraries. Older ones (`test_job.py`, `test_download_planner.py`) just construct objects and print them; they "pass" if they don't raise.

Be careful before running tests/scripts that touch live resources:
- `test_repository.py`, `test_download_jobs.py`, `test_download_manifest.py`, `test_download_jobs_migration.py` connect to the real `database/optionlab.duckdb`.
- `test_download_engine.py` performs **real API calls to DhanHQ** and writes to the real database (as does `python -m app.main download`/`resume`/`sync`).
- `test_e2e_cli.py`/`test_e2e_web.py` (TASK-024) also write to the real database, deliberately: they exercise the *real* `DownloadEngine`/`Repository`/DuckDB pipeline end-to-end through the CLI and the web GUI respectively — only `RollingOptionAPI.fetch` is stubbed, so no real DhanHQ call is made, but everything else (planner, payload builder, normalizer, validator, manifest, job rows, `ParquetWriter`) is genuinely exercised against `database/optionlab.duckdb` and a fixed `data/test_e2e_parquet_*` folder. Safe to rerun (idempotent via the manifest's completed-batch skip) but not side-effect-free.
- `test_e2e_sync.py` similarly exercises the real `SyncPlanner`/`JobRunner.start_many()` orchestration through `POST /api/sync`, temporarily narrowing `SyncPlanner.UNDERLYINGS`/`EXPIRY_TYPES`/`GENESIS_DATE` to a single otherwise-untouched combo (BANKNIFTY/MONTH — every other e2e test only ever uses NIFTY) so it runs in seconds instead of the real multi-combo/multi-year backfill; it explicitly deletes that combo's `option_data`/`download_manifest`/`download_jobs` rows both before and after, so unlike `test_e2e_cli.py`/`test_e2e_web.py` it deliberately leaves no trace (a sync job's date range depends on "today", so leftover data would make its own "not up to date yet" precondition false on a same-day rerun).
- Prefer the pure/offline ones (`test_job.py`, `test_download_planner.py`, `test_validator.py`, `test_manifest_integration.py`, `test_resume_engine.py`, `test_retry_engine.py`, `test_progress_reporter.py`, `test_logging_config.py`, `test_cli.py`, `test_job_runner.py`, `test_web_server.py`, `test_parquet_writer.py`, `test_download_service.py`, `test_sync_planner.py`) when just sanity-checking logic — `test_job_runner.py`/`test_web_server.py`/`test_sync_planner.py` fake out `DownloadEngine`/`JobRunner`/`Repository` the same way `test_cli.py` fakes `DownloadEngine`, so none of them touch the real DB.

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
- **`app/storage`** (`DataNormalizer`, `ParquetWriter`): normalizes raw API JSON into the canonical `option_data` DataFrame shape; `ParquetWriter` is an optional, auto-triggered (via `--save-parquet-to`/the GUI's folder picker) year/month-partitioned Parquet export alongside a successful DuckDB write — export-only, never the source of truth.
- **`app/validator`** (`DataValidator`): checks a normalized DataFrame (empty, required columns, nulls, duplicate timestamps, OHLC consistency) and returns a `ValidationReport` (`passed`, `errors`, `warnings`).
- **`app/database`** (`Repository`, `DuckDBManager`): **all SQL lives here and only here.** Table DDL lives in `app/database/schema/*.sql` and is applied via `Repository.execute_sql_file()`. No other module should construct SQL.
- **`app/models`**: plain `@dataclass` models (`DownloadJob`, `DownloadBatch`, `ValidationReport`, etc.) with no business logic. `JobStatus` is a `str, Enum` in `app/models/enums/`.
- **`app/autosync`** (`SyncPlanner`): sits one level above `DownloadPlanner` — plans which *jobs* to create (not batches within one job) by comparing `Repository.get_latest_trade_date()` to today per underlying/expiry-type combo. Pure planning logic; the actual running happens through the normal `DownloadEngine`/`JobRunner` machinery, not a separate execution path.

`app/downloader/manager.py` (`DownloadManager`) and `app/downloader/download_day.py` were earlier, superseded prototypes of the batching/download logic from before the `DownloadPlanner`/`DownloadEngine`/`DownloadService` split; they were never wired into the current pipeline and have since been deleted outright (along with their smoke tests) rather than left as dead code — treat `DownloadPlanner`/`DownloadEngine`/`DownloadService` as canonical and don't try to resurrect them.

### Database

- Single DuckDB file at `database/optionlab.duckdb` (gitignored).
- Key tables: `option_data` (the actual OHLC/IV/OI candles), `download_manifest` (per-batch/option-type/strike-offset status tracking used for resume/retry), `download_jobs`.
- The manifest is keyed on `(job_id, batch_number, option_type, strike_offset)`; `DownloadEngine.is_download_completed()` uses `get_manifest_status()` against this key to make reruns idempotent — preserve this idempotency when touching the manifest flow.

### Configuration

`app/config/config.py` loads `.env` (via `python-dotenv`) and exposes `DHAN_CLIENT_ID` / `DHAN_ACCESS_TOKEN`, plus auto-creates `data/`, `database/`, `logs/`, `app/exports/parquet` (`EXPORTS_DIR`, gitignored — the fixed auto-sync Parquet destination) directories on import. Never hardcode credentials; never commit `.env`. Note `DhanAPI` (`app/api/api_client.py`) deliberately does *not* use these frozen `DHAN_CLIENT_ID`/`DHAN_ACCESS_TOKEN` constants — it reads `os.getenv(...)` live at construction time instead, specifically so the GUI's token-update flow (`POST /api/token`) takes effect on the next job without a process restart.

## Coding conventions

(From `PROJECT_RULES.md` / `docs/CODING_STANDARDS.md`, and reflected consistently in existing code — follow them for consistency.)

- Python 3.14+, PEP8, full type hints on function signatures.
- Classes `PascalCase`, functions/variables `snake_case`, constants `UPPER_CASE`.
- Models are `@dataclass`; enums subclass `str, Enum`.
- Public classes/methods get docstrings (existing code is inconsistent about this — new code should have them).
- Service/engine methods that can fail return a structured result dict rather than raising or returning a bare bool (see `DownloadService.download()`).
- Commit style: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:` — small, frequent commits.
