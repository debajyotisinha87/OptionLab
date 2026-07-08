# OptionLab Architecture

## High Level Architecture

```
Download Job
      │
      ▼
Download Planner
      │
      ▼
Download Batch
      │
      ▼
Payload Builder
      │
      ▼
Download Service
      │
      ▼
Rolling Option API
      │
      ▼
Data Normalizer
      │
      ▼
Data Validator
      │
      ▼
Repository
      │
      ▼
DuckDB
```

---

## Components

### API

Communicates with DhanHQ.

### Planner

Creates download batches.

### Builders

Constructs API payloads.

### Services

Coordinates business logic.

### Validator

Validates downloaded data.

### Repository

Handles all database operations.

### DuckDB

Stores historical options data.

---

## Design Principles

- Single Responsibility Principle
- Repository Pattern
- Service Layer
- Strong Typing
- Modular Architecture