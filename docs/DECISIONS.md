# Architecture Decisions

## ADR-001

Decision

Use DuckDB instead of SQLite.

Reason

Better analytical performance.

---

## ADR-002

Decision

Use Repository Pattern.

Reason

Keeps SQL isolated.

---

## ADR-003

Decision

Store data in DuckDB first.

CSV is export-only.

Reason

Single source of truth.

---

## ADR-004

Decision

Manifest-based download engine.

Reason

Supports resume and retry.