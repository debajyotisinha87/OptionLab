# Database Design

Database Engine:

- DuckDB

Database File:

```
database/optionlab.duckdb
```

---

## Tables

### option_data

Stores historical options data.

Columns

- symbol
- trade_datetime
- trade_date
- trade_time
- option_type
- strike_type
- expiry_flag
- expiry_code
- open
- high
- low
- close
- volume
- oi
- iv
- spot

---

### download_jobs

Stores download requests.

---

### download_manifest

Tracks batch progress.

---

### Future Tables

- system_logs
- schema_version
- strategy_results
- backtest_results