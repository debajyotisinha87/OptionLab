# OptionLab

![Python](https://img.shields.io/badge/Python-3.14-blue)
![DuckDB](https://img.shields.io/badge/Database-DuckDB-orange)
![License](https://img.shields.io/badge/License-MIT-green)

## Overview

OptionLab is a professional historical options data platform built in Python.

It downloads historical options data from DhanHQ, validates the data, stores it efficiently in DuckDB, and provides a foundation for strategy development, backtesting, and eventually paper/live trading.

---

## Current Features

- Historical Option Download
- Download Planner
- Download Engine
- Data Validation
- DuckDB Storage
- CSV Export
- Repository Pattern
- Download Manifest
- Download Job Tracking

---

## Planned Features

- Resume Interrupted Downloads
- Retry Failed Downloads
- Progress Tracking
- CLI
- Strategy Engine
- Backtesting
- Paper Trading
- Live Trading
- GUI

---

## Project Structure

```
app/
├── api/
├── builders/
├── database/
├── downloader/
├── models/
├── planner/
├── services/
├── storage/
├── tests/
├── utils/
└── validator/
```

---

## Installation

```bash
git clone https://github.com/debajyotisinha87/OptionLab.git

cd OptionLab

python -m venv .venv

pip install -r requirements.txt
```

---

## Run

```bash
python -m app.main
```

---

## Status

Current Version: v0.8.x

Project is under active development.