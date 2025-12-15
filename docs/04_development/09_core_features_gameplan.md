# Core Features Gameplan

**Created**: 2025-12-14
**Updated**: 2025-12-14
**Status**: Active - A Stream 2/3 Complete

## Overview

The 10 core features (`track:core` label) are split between two parallel development streams to enable concurrent work without conflicts.

## Branch Structure

```text
development
├── feature/core-execution      (A Chat - Position Management)
└── feature/core-signals-infra  (C Chat - Signals + Infrastructure)
```

## Stream Assignments

### A Chat: Execution Stream (`feature/core-execution`)

**Focus**: HOW positions are managed (entry, exit, protection)

| Priority | Issue | Title | Dependency |
|----------|-------|-------|------------|
| 1 | #414 | **KILLER** Advanced Trailing Stop Automation | #321 ✅, #400, #364* |
| 2 | #372 | Multi-Level Price Targets | #366 |
| 3 | #366 | OHLCV-Based Intraday Entry Plan | None |

**Execution Order**: #366 → #372 → #414

**Notes**:

- #366 provides ATR calculation needed by #372 and #414
- #414 can start with current VoterAgent; #364 enhancement is optional
- All three issues form a coherent execution pipeline

### C Chat: Signals + Infrastructure Stream (`feature/core-signals-infra`)

**Focus**: WHAT signals the system generates + support infrastructure

| Priority | Issue | Title | Dependency |
|----------|-------|-------|------------|
| 1 | #364 | Ranked Voter System | None |
| 2 | #395 | Multi-Timeframe Ranked Voting | #364, #365 ✅ |
| 3 | #402 | Credential Management | None |
| 4 | #405 | Tiered Watchlist System | None |
| 5 | #407 | CustomTimeframeBuilder | None |
| 6 | #483 | DB Backup/Migration | None |
| 7 | #370 | LLM Trade Journal | None |

**Execution Order**: #364 → #395, then infrastructure (#402, #405, #407, #483, #370) in any order

**Notes**:

- #364 is foundational for #395
- Infrastructure issues are independent and can be parallelized
- #370 (Journal) is lower priority, can be deferred

## Dependency Diagram

```text
Stream A (Execution):
  #366 (OHLCV Entry)
    └──→ #372 (Multi-Targets)
           └──→ #414 (Trailing Stops) ← KILLER

Stream C (Signals):
  #364 (Ranked Voter)
    └──→ #395 (Multi-TF Voting)

Stream C (Infra): Independent
  #402 (Credentials)
  #405 (Watchlist)
  #407 (Timeframes)
  #483 (DB Backup)
  #370 (Journal)
```

## Cross-Stream Dependencies

| A Issue | C Issue | Nature | Resolution |
|---------|---------|--------|------------|
| #414 | #364 | Optional voter integration | A can use current VoterAgent; enhance later |

**No blocking cross-dependencies** - streams can proceed independently.

## Worktree Setup

Each chat should work in a separate worktree:

```bash
# A Chat worktree
git worktree add ../AutoGen-Trader-execution feature/core-execution

# C Chat worktree
git worktree add ../AutoGen-Trader-signals feature/core-signals-infra
```

## Merge Strategy

1. Each stream PRs into `development` when complete
2. A stream merges first (execution is higher priority)
3. C stream rebases on updated `development` before merge
4. Resolve any conflicts in C stream PR

## Success Criteria

### A Stream Complete When:

- [x] #366: OHLCV entry planner functional with ATR stops (commit 3bf530c)
- [x] #372: Multi-level targets with order splitting (commit a3dbeac)
- [ ] #414: Autonomous trailing stops with voter integration

### C Stream Complete When:

- [ ] #364: Ranked voter configuration system
- [ ] #395: Multi-timeframe voting operational
- [ ] Infrastructure: At least 3 of 5 infra issues closed

## Timeline Estimate

| Stream | Issues | Estimate |
|--------|--------|----------|
| A (Execution) | 3 | 2-3 weeks |
| C (Signals) | 2 core + 5 infra | 2-3 weeks |

Parallel execution = both complete in ~3 weeks total.

## Quick Reference

**Filter commands:**

```bash
# All core features
gh issue list --label "track:core"

# Research (separate B chat)
gh issue list --label "track:research"

# Backlog (parked)
gh issue list --label "track:backlog"
```

**Branch switch:**

```bash
# A Chat
git checkout feature/core-execution

# C Chat
git checkout feature/core-signals-infra
```

## Progress Log

### December 14, 2025 - A Stream Progress

**#366 OHLCV-Based Intraday Entry Plan** - COMPLETE

- Created `src/trading/instruments/entry_planning.py`
- Functions: `calculate_atr()`, `find_support_resistance()`, `calculate_volume_confirmation()`, `calculate_entry_plan()`
- Integrated into `real_voter_strategy.py` with fallback to percentage-based stops
- Commit: `3bf530c`

**#372 Multi-Level Price Targets** - COMPLETE

- Created `src/trading/orders/multi_level_targets.py`
- Classes: `MultiLevelTargetManager`, `DistributionStrategy`, `PriceTarget`, `MultiLevelState`
- Supports equal/progressive/inverse distribution, ATR-based targets
- Integration with existing PartialExitManager and TrailingStopManager
- Commit: `a3dbeac`

**Next**: #414 KILLER Trailing Stop Automation
