# Dhan Option Research Platform

Version: 1.0
Author: Debajyoti Sinha
Architect: ChatGPT

---

# Objective

Build a professional-grade options research and trading platform using the DhanHQ API.

The platform should be capable of:

- Downloading 5 years of historical option data.
- Downloading ATM, 10 ITM and 10 OTM strikes.
- Storing data locally.
- Running high-speed backtests.
- Executing live strategies.
- Performing portfolio analytics.
- Supporting multiple underlying indices.

---

# Underlyings

Phase 1

- NIFTY
- BANKNIFTY

Phase 2

- FINNIFTY
- MIDCPNIFTY

---

# Historical Data

Resolution

- 1 Minute

Range

- 5 Years

Request Size

- 30 Days

Download Method

Rolling Option API

---

# Data to Store

Every candle should contain

- Date
- Time
- DateTime
- Underlying
- Expiry
- Option Type
- Strike
- ATM Distance
- Spot Price
- Open
- High
- Low
- Close
- Volume
- Open Interest
- Implied Volatility

---

# Storage

Raw

CSV

Processed

Parquet

Database

DuckDB

---

# Modules

01 Config

Handles configuration.

02 API

Communicates with DhanHQ.

03 Downloader

Downloads historical data.

04 Storage

Stores CSV, Parquet and DuckDB.

05 Database

Executes SQL queries.

06 Indicators

EMA
VWAP
ATR
RSI
ADX
Supertrend

07 Strategy Engine

Runs strategies.

08 Backtesting Engine

Runs historical simulations.

09 Live Trading

Places and manages orders.

10 Analytics

Reports
Performance
Risk
Trade Journal

---

# Coding Rules

- Python 3.13
- Type Hints
- Docstrings
- One class per file
- One responsibility per class
- No duplicate code
- No hardcoded values

---

# Development Phases

Phase 1

Project Setup

API Connection

Historical Downloader

CSV Storage

DuckDB

Daily Update

Phase 2

Indicators

Strategy Engine

Backtesting

Phase 3

Live Trading

Risk Management

Portfolio Analytics

GUI

---

# Current Status

Environment

Completed

API Authentication

Completed

Historical Downloader

Pending

Database

Pending

Backtesting

Pending

Live Trading

Pending