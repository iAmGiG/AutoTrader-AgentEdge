# Work Assignments & Setup

**Date**: 2025-11-27
**Status**: Ready to begin

---

## Assignment 1: B - CLI & Documentation

### Issue

**#396** - CLI Enhancement: Update Help System, Tutorials, and Error Messages
**URL**: <https://github.com/iAmGiG/AutoTrader-AgentEdge/issues/396>

### Scope

- Update help system and error messages
- Create interactive tutorials
- Document forward testing workflow
- Expose hidden features through CLI
- Update README.md

### Related Context

- See `STRATEGIC_ASSESSMENT.md` in repo root (explains why this is priority)
- See `ACCOMPLISHMENTS_SUMMARY.md` in repo root (what you can show in docs)
- Strategic docs created for reference

### Success Criteria

- All features from #324, #358, #365 discoverable through CLI
- '/help' command shows all available commands
- At least one tutorial for each major workflow
- Error messages provide constructive guidance
- README reflects current feature set

---

## Assignment 2: Code Review & Grooming

### Scope

- Review strategic assessment documents
- Review issue relationships mapping
- Code quality review of recent changes
- General codebase grooming

### Context Documents

1. `ISSUE_RELATIONSHIPS.md` - Dependency mapping for all 50+ open issues
2. `ISSUE_321_INVESTIGATION.md` - Deep dive on trailing stops (in wt-321)
3. `STRATEGIC_ASSESSMENT.md` - Recommendations and roadmap
4. `ACCOMPLISHMENTS_SUMMARY.md` - What we've built

### Recommendations from Assessment

- Priority 1: CLI Overhaul (#396) - highest impact
- Priority 2: Complete #321 (trailing stops) - easy win
- Priority 3: Multi-agent infrastructure (#390, #388, #389)
- Quick wins: #362, #361, #364, #384, #385

---

## Assignment 3: Me - Issue #321 (Dynamic Trailing Stops)

### Branch & Worktree

```text
Branch: feature/trailing-stops-321
Worktree: A:\Projects\AutoGen-Trader-wt-321
```

### What I'm Doing

Integrating TrailingStopManager into the trading system:

- Replace duplicate inline implementations
- Add comprehensive tests
- Validate with forward testing framework
- Update documentation

### Key Files

- `src/trading/trailing_stop_manager.py` - Implementation (ready to use, don't modify)
- `src/trading/trading_cycle.py` - Replace calculate_stop_adjustments()
- `src/trading/trade_lifecycle.py` - Replace adjust_stop()

### Current Status: ✅ COMPLETE

| Phase | Status | Commit |
|-------|--------|--------|
| Phase 1: trading_cycle.py | ✅ Done | `ffdfeac` |
| Phase 2: trade_lifecycle.py | ✅ Done | `4cfa8c4` |
| Phase 3: Unit tests (31 tests) | ✅ Done | (gitignored) |
| Phase 4: Forward testing | ⏳ Deferred | Post-merge |
| Phase 5: Documentation | ✅ Done | `686bd7c` |

**Result**: TrailingStopManager now used in both files. No duplicate code. Ready to merge.

---

## Assignment 4: Me - Issue #390 (Event Bus)

### Branch & Worktree

```text
Branch: feature/event-bus-390
Worktree: A:\Projects\AutoGen-Trader-wt-390
```

### What I'm Doing

Building event bus infrastructure for multi-agent coordination:

- EventBus class with publish/subscribe
- Event type definitions
- BaseAgent integration
- Unblocks #389 (TradingOrchestrator) and #323 (Full Pipeline)

### Key Architecture

- Agents publish events (signals, market data, risks)
- TradingOrchestrator subscribes and coordinates
- Thread-safe, asyncio compatible

### Work Plan (from GitHub issue #397)

1. Create EventBus class (publish/subscribe)
2. Define event types for all agents
3. Integrate with BaseAgent
4. Unit tests and integration tests
5. Documentation and examples

**Total Estimate**: 15-20 hours

---

## Workflow

### For B (CLI & Documentation)

1. Review #396 issue
2. Review context documents (STRATEGIC_ASSESSMENT.md, etc.)
3. Update CLI help system
4. Create tutorials
5. Update README.md
6. Code review and general grooming as time permits

### For Me (Issue #321 & #390)

**Strategy**: Work on #321 first (simpler, more contained), then move to #390

#### #321 Timeline

1. Start with trading_cycle.py integration
2. Test integration
3. Move to trade_lifecycle.py
4. Write unit tests
5. Validate with forward testing
6. Commit and PR

#### #390 Timeline

1. Design EventBus class
2. Define all event types
3. Integrate with BaseAgent
4. Test with mock agents
5. Integration tests
6. Documentation

---

## Success Indicators

### CLI (#396) Complete When

- ✅ Help system works and is discoverable
- ✅ New features documented
- ✅ Tutorials written
- ✅ README updated
- ✅ No stale documentation

### #321 Complete When

- ✅ TrailingStopManager used everywhere
- ✅ No duplicate code
- ✅ Tests passing
- ✅ Forward test validation done
- ✅ Documentation updated

### #390 Complete When

- ✅ EventBus working
- ✅ All agent types have events
- ✅ BaseAgent supports event handlers
- ✅ Tests passing
- ✅ Multi-agent coordination example works

---

## Related Issues & Dependencies

### Open, Ready to Work On

- #362: Arrow key history
- #361: LLM intent classification
- #364: Ranked voter system
- #384: Market hours detection
- #385: Bracket order logging
- #248: Partial position exits
- #372: Multi-level price targets

### Blocked (Waiting)

- #323: Full pipeline (blocked by #388, #389, #390)
- #389: TradingOrchestrator (blocked by #390)
- #367: Advanced GEX (blocked by #352)

---

## Communication

**Main Repository**: <https://github.com/iAmGiG/AutoTrader-AgentEdge>

**Key Issues**:

- #396 - CLI Enhancement (B's assignment)
- #321 - Trailing Stops (My #1 assignment)
- #390 - Event Bus (My #2 assignment)

**Context Documents** (in repo root):

- STRATEGIC_ASSESSMENT.md - Why we're doing this
- ACCOMPLISHMENTS_SUMMARY.md - What we've built
- ISSUE_RELATIONSHIPS.md - Full dependency mapping
- WORK_ASSIGNMENTS.md - This file

---

## Quick Reference

### Worktrees

```bash
# 321 - Trailing Stops
A:\Projects\AutoGen-Trader-wt-321
cd "A:\Projects\AutoGen-Trader-wt-321"

# 390 - Event Bus
A:\Projects\AutoGen-Trader-wt-390
cd "A:\Projects\AutoGen-Trader-wt-390"

# Main repo
A:\Projects\AutoGen-Trader
```

### Git Flow

```bash
# Work on worktree
cd "A:\Projects\AutoGen-Trader-wt-321"

# Commit changes
git add -A
git commit -m "feat: Your message here"

# Push branch
git push origin feature/trailing-stops-321

# Create PR when ready (from GitHub or gh cli)
gh pr create --base feature/development
```

### Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/unit/trading/test_trailing_stop_manager.py -v

# Run with coverage
python -m pytest tests/ --cov=src
```

### Validation

```bash
# Code quality
ruff check src/
black --check src/

# Type checking
mypy src/ --ignore-missing-imports
```

---

## Next Steps

**Right Now**:

1. ✅ GitHub issues created (#396, #397)
2. ✅ Worktrees set up
3. ✅ Documentation prepared
4. ⏳ Await team feedback

**B's Work**:

- Review #396 and context docs
- Start CLI improvements
- Update documentation

**My Work**:

- Begin #321 implementation in wt-321
- Track progress
- Create PRs when phases complete

---

## Questions?

Refer to:

- **How to integrate #321?**: See GitHub issue #321 comment with detailed plan
- **How to build #390?**: See GitHub issue #397 with specification
- **Why these priorities?**: See STRATEGIC_ASSESSMENT.md
- **What's completed?**: See ACCOMPLISHMENTS_SUMMARY.md
- **What depends on what?**: See ISSUE_RELATIONSHIPS.md
