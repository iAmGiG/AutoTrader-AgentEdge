# Database-First Caching Architecture Design

**Issue:** #469
**Status:** Design Phase
**Author:** Claude Code
**Date:** 2025-12-04

## Executive Summary

This document outlines the design for implementing a database-first caching architecture where all data flows through the database before being displayed to users, ensuring consistency between stored and displayed data.

## Current State Analysis

### Data Flow Patterns Identified

| Path | Data Type | Current Pattern | Cache Type | Issues |
|------|-----------|-----------------|------------|--------|
| Market Data | OHLCV bars | fetch -> cache -> display | SQLite | Cache key mismatch (fixed) |
| Account Status | Equity, buying power | fetch -> memory cache -> display | In-memory 60s | No persistence |
| Positions | Holdings, P&L | fetch -> memory cache -> display | In-memory 60s | No audit trail |
| Orders | Open/filled orders | fetch -> display (merge local) | None + JSON | Dual source of truth |
| Analysis | MACD/RSI signals | calculate -> database -> display | SQLite | **Only DB-first path** |

### Current vs Proposed Architecture

```mermaid
flowchart TB
    subgraph Current[Current Architecture]
        A1[Alpaca API] --> B1[In-Memory Cache]
        A1 --> C1[Display to User]
        B1 -.-> D1[Maybe Store]
    end

    subgraph Proposed[Proposed Architecture Database-First]
        A2[Alpaca API] --> B2[UnifiedBrokerCache]
        B2 --> C2[(SQLite Database)]
        C2 --> D2[Display to User]
    end
```

### Detailed Data Flow Sequence

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Cache as UnifiedBrokerCache
    participant DB as SQLite
    participant API as Alpaca API

    User->>CLI: Request portfolio
    CLI->>Cache: get_positions(account_id)
    Cache->>DB: Check cache freshness
    alt Cache Fresh
        DB-->>Cache: Return cached data
        Cache-->>CLI: Return positions
    else Cache Stale
        Cache->>API: Fetch fresh data
        API-->>Cache: Return positions
        Cache->>DB: Store to database
        DB-->>Cache: Confirm stored
        Cache-->>CLI: Return positions
    end
    CLI->>Cache: audit_display()
    Cache->>DB: Log audit entry
    CLI-->>User: Display portfolio
```

### Cache State Machine

```mermaid
stateDiagram-v2
    [*] --> Empty
    Empty --> Fresh: API Fetch + Store
    Fresh --> Stale: TTL Expired
    Stale --> Fresh: Refresh
    Fresh --> Fresh: Cache Hit
    Stale --> Stale: API Fail Serve Stale
```

### Database Schema - Entity Relationship

```mermaid
erDiagram
    broker_state_cache {
        int id PK
        string account_id
        string state_type
        json data_json
    }

    position_snapshots {
        int id PK
        string account_id FK
        string symbol
        float qty
        float unrealized_pnl
    }

    order_snapshots {
        int id PK
        string account_id FK
        string order_id
        string symbol
        string status
    }

    display_audit_log {
        int id PK
        datetime display_time
        string display_type
        json data_json
    }

    broker_state_cache ||--o{ position_snapshots : has
    broker_state_cache ||--o{ order_snapshots : has
```

## SQL Schema Definitions

### broker_state_cache Table

```sql
CREATE TABLE IF NOT EXISTS broker_state_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    state_type TEXT NOT NULL,
    data_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    UNIQUE(account_id, state_type)
);
```

## Implementation Plan

### Phase 1: Core Infrastructure (This PR)

1. Create UnifiedBrokerCache class - SQLite-backed broker state caching
2. Fix cache_adapter.py - Fixed cache key mismatch between GET and SET
3. Create BrokerSnapshotManager - Store position/order snapshots

### Phase 2: Integration

1. Replace BrokerStateCache usage with UnifiedBrokerCache
2. Update portfolio_tools.py to query from cache
3. Update order_tools.py to use unified orders table

### Migration Strategy

```mermaid
flowchart TD
    A[Start Migration] --> B{Feature Flag Enabled?}
    B -->|No| C[Use Existing JSON]
    B -->|Yes| D[Write to Both DB + JSON]
    D --> E{Validation Pass?}
    E -->|No| F[Log Discrepancy]
    F --> C
    E -->|Yes| G[Read from DB Only]
    G --> H[Remove JSON Fallback]
```

## Success Metrics

- Cache hit rate greater than 80 percent for broker state
- Display latency less than 500ms
- 100 percent audit coverage for displayed data
- Zero discrepancy between displayed and stored data

## Timeline Estimate

- Phase 1 (Core): 2-3 hours
- Phase 2 (Integration): 3-4 hours
- Phase 3 (Display): 2-3 hours
- Phase 4 (Validation): 1-2 hours

Total: approximately 10 hours of implementation work
