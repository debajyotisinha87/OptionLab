# OptionLab - Project Context

> This document is the authoritative context for AI assistants and developers working on OptionLab.
>
> Always read this file before modifying the codebase.

---

# Project Overview

OptionLab is a professional historical options data platform written in Python.

The long-term goal is to build a complete quantitative trading platform capable of:

- Historical Options Downloader
- DuckDB Data Warehouse
- Resume & Retry Downloads
- Progress Tracking
- Strategy Engine
- Backtesting
- Portfolio Analytics
- Paper Trading
- Live Trading
- Desktop GUI
- Cloud Runner

The downloader is the foundation of the entire project.

---

# Current Version

Current Development Version

v0.8.x

Current Sprint

Sprint 1

Current Task

TASK-024 – End-to-End Testing

---

# Development Philosophy

OptionLab is designed as production-quality software.

Priority order:

1. Correctness
2. Reliability
3. Maintainability
4. Performance
5. Features

Never sacrifice architecture for speed.

---

# Technology Stack

Language

Python 3.14+

Database

DuckDB

Broker

DhanHQ

Data Processing

Pandas

Storage

DuckDB (Primary)

CSV (Export Only)

Version Control

Git

GitHub

IDE

VS Code

---

# Project Structure

```
app/

    api/
        External API communication

    builders/
        Payload builders

    config/
        Application configuration

    constants/
        Application constants

    database/
        DuckDB
        Repository
        SQL Schemas

    downloader/
        Download Engine

    models/
        Dataclasses

    planner/
        Download Planner

    services/
        Business logic

    storage/
        Data normalization
        CSV export

    validator/
        Data validation

    tests/
        Unit tests
```

---

# Architecture

```
DownloadJob

        │

        ▼

DownloadPlanner

        │

        ▼

DownloadBatch

        │

        ▼

PayloadBuilder

        │

        ▼

DownloadEngine

        │

        ▼

DownloadService

        │

        ▼

RollingOptionAPI

        │

        ▼

DataNormalizer

        │

        ▼

DataValidator

        │

        ▼

Repository

        │

        ▼

DuckDB

        │

        ▼

Download Manifest
```

---

# Design Principles

Use:

- SOLID
- Clean Architecture
- Repository Pattern
- Service Layer
- Single Responsibility Principle

Never mix responsibilities.

---

# Responsibilities

## API

Only communicates with DhanHQ.

Never contains business logic.

---

## PayloadBuilder

Constructs API payloads.

Never performs downloads.

---

## DownloadPlanner

Splits DownloadJob into DownloadBatch objects.

Never communicates with the API.

---

## DownloadEngine

Coordinates the entire download workflow.

Should never contain SQL.

Should never contain API implementation details.

Should never normalize data.

---

## DownloadService

Responsible for:

- API call
- Data normalization
- Validation
- Repository insertion

Returns structured results to DownloadEngine.

---

## Repository

Responsible for ALL SQL.

No SQL should exist outside Repository.

---

## Validator

Responsible only for validating downloaded data.

---

## Models

Use dataclasses whenever appropriate.

Models should not contain business logic.

---

# Coding Standards

Python

PEP8

Type hints required.

Meaningful variable names.

One responsibility per class.

Small methods.

Prefer composition over inheritance.

---

# Error Handling

Never silently ignore exceptions.

Return structured results when possible.

Avoid returning booleans if additional context is useful.

Prefer:

```
{
    "success": True,
    "rows": 375,
    "error": None
}
```

instead of:

```
True
```

---

# Database Rules

DuckDB is the single source of truth.

CSV files are exports only.

No business logic inside SQL.

No SQL outside Repository.

---

# Git Workflow

Small commits.

Meaningful commit messages.

Examples

```
feat:

fix:

docs:

refactor:

test:

chore:
```

Push after every completed milestone.

---

# AI Development Workflow

Every AI assistant must follow these rules.

Rule 1

Never assume the contents of a file.

Rule 2

Always ask for the next file.

Rule 3

The user will paste the COMPLETE file.

Rule 4

Return the COMPLETE replacement file.

Never return partial code.

Rule 5

Wait until the user tests the file.

Rule 6

Only continue after successful testing.

Rule 7

Never overwrite code based on assumptions.

Rule 8

Preserve the existing architecture.

---

# Completed Tasks

✓ API Client

✓ HTTP Client

✓ RollingOptionAPI

✓ PayloadBuilder

✓ DuckDB Manager

✓ Repository Layer

✓ SQL Schemas

✓ Download Jobs

✓ Download Manifest

✓ Download Planner

✓ Download Engine Foundation

✓ DownloadService

✓ Data Normalizer

✓ Data Validator

✓ Validation Report

✓ Project Documentation

✓ Manifest Integration (TASK-021.6)

✓ Resume Engine (TASK-021.7)

✓ Retry Engine (TASK-021.8)

✓ Progress Engine (TASK-021.9)

✓ Logging (TASK-022)

✓ CLI (TASK-023)

✓ Multi-Underlying and Strike-Range Support (TASK-023.5)

✓ Web GUI (TASK-023.6)

✓ End-to-End Testing (TASK-024)

✓ Auto-Sync (NIFTY/SENSEX) and Token Health Check (TASK-023.7)

---

# Current Task

TASK-025

Version 1.0 Release

---

# Future Roadmap

v1.0

Stable Downloader

CLI

Documentation

---

v1.5

Strategy Engine

Backtesting

Analytics

---

v2.0

Paper Trading

Portfolio

Risk Management

---

v3.0

Live Trading

GUI

Cloud Runner

Multi Broker

---

# AI Instructions

When modifying the project:

1. Preserve architecture.
2. Prefer clean design over shortcuts.
3. Avoid duplicate logic.
4. Reuse existing modules.
5. Minimize technical debt.
6. Keep Repository responsible only for SQL.
7. Keep Services responsible for business logic.
8. Never generate code based on assumptions.
9. Ask for the current file before modifying it.
10. Return complete files only.

This document is the single source of truth for OptionLab.