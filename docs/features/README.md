# Feature Documentation - User Manual

This directory contains comprehensive documentation for all integrated features in the AutoGen Trading System. Documents are sequenced like a manual for easy learning.

## 📚 Quick Navigation

### Getting Started

1. **[Position Alerts System](01_position_alerts_system.md)** (Issue #306)
   - What it does: Monitor positions and generate alerts
   - 5 alert types with cooldown and persistence
   - Integrated into trading cycle and CLI
   - **Start here** to understand position monitoring

2. **[GTC Scheduler - Quick Start](02_gtc_scheduler_quickstart.md)** (Issue #287)
   - **5-minute setup wizard** for daily automation
   - Three deployment options: daemon, systemd, cron
   - For users who want to "set it and forget it"
   - **Read this** to get scheduler running quickly

### Advanced/Technical

3. **[GTC Scheduler - Technical Details](03_gtc_scheduler_technical.md)** (Issue #287)
   - Deep dive into architecture and design
   - API efficiency (90% cost savings)
   - Retry logic and error handling
   - For developers and advanced users

4. **[Unified Features Testing](04_unified_features_testing.md)**
   - Complete test results for all features
   - 19/19 tests passed (100%)
   - Integration verification
   - Performance metrics

5. **[Interactive CLI Test Plan](05_interactive_cli_test_plan.md)** (Issue #334)
   - **Live testing guide** with real user prompts
   - 25+ test cases based on manual testing
   - Known issues from #334 documented
   - Bug fixes and improvements needed
   - **Use this** for live validation testing

---

## Feature Summary

### Position Alerts System (#306)

**What:** Real-time monitoring of open positions with smart alerts

**Why:** Know when positions approach targets/stops without constant checking

**Key Features:**

- 5 alert types (approaching TP/SL, stop adjusted, targets reached)
- 5-minute cooldown (anti-spam)
- Alert history persists across restarts
- Integrated into unified CLI

**Usage:**

```bash
python main.py

> check my alerts
📊 Checking Position Alerts...
🔔 2 Alert(s) Generated:
   ⚠️  TQQQ approaching take profit!
```

**Documentation:** [01_position_alerts_system.md](01_position_alerts_system.md)

---

### GTC Daily Scheduler (#287)

**What:** "Set it and forget it" twice-daily trading automation

**Why:** Automate morning reconciliation and evening review without manual intervention

**Key Features:**

- Twice-daily execution (9:20 AM, 3:50 PM ET)
- 90% API cost savings vs continuous polling
- Retry logic with exponential backoff
- Multiple deployment options

**Usage:**

```bash
# Background scheduler
python main.py --daemon

# Or check status via CLI
python main.py

> show scheduler status
🤖 Daily Scheduler Status...
   Morning routine: 09:20:00 ET ✅
   Evening routine: 15:50:00 ET (pending)
```

**Documentation:**

- Quick Start: [02_gtc_scheduler_quickstart.md](02_gtc_scheduler_quickstart.md)
- Technical: [03_gtc_scheduler_technical.md](03_gtc_scheduler_technical.md)

---

### Unified Interactive CLI (#339)

**What:** Single interactive interface for all features with LLM-based intelligent routing

**Why:** Eliminate fragmented commands, enable natural language interaction

**Key Features:**

- **LLM-Based Routing:** Context-aware classification (trade vs status query)
- **Natural Language:** "check my alerts", "show portfolio", "any open orders?"
- **No Hardcoded Patterns:** Handles ambiguous tickers (ANY, WHAT, etc.) automatically
- **All Features in One Session:** Zero friction, just `python main.py`
- **Mode Indicator:** Visual prompt shows CONFIRM/AUTO mode like conda environments

**Architecture:**

- LLM parser determines `request_type` before ticker extraction
- Prevents "any open orders?" from being parsed as ticker "ANY"
- Fast keyword routing for scheduler/alerts (no LLM overhead)
- Scalable: No special cases needed for individual tickers

**Usage:**

```bash
python main.py    # Just works!

(✋ CONFIRM) > buy 10 AAPL           # Execute trade
(✋ CONFIRM) > check my alerts       # Position alerts
(✋ CONFIRM) > any open orders?      # Shows orders (NOT ticker "ANY")
(✋ CONFIRM) > show scheduler status # Scheduler management
(✋ CONFIRM) > /toggle               # Switch to AUTO mode
(🤖 AUTO) > show portfolio           # Account status
```

**Documentation:**

- Architecture: `docs/02_architecture/06_llm_routing.md`
- Test Plan: `docs/features/05_interactive_cli_test_plan.md` (Category 7)
- Main README: See main README.md

---

## How to Use This Manual

### For New Users

1. **Read in order:** Start with #1 (Position Alerts) and progress sequentially
2. **Try examples:** Each doc has copy-paste examples
3. **Refer back:** Use as reference when questions arise

### For Advanced Users

- Jump to specific features
- Read technical docs (#3) for architecture
- Use testing doc (#4) for verification

### For Developers

- Technical details in #3 (Scheduler architecture)
- Test suite in #4 (All test cases)
- ADRs in `/architecture_decisions/`

---

## Feature Integration

All features work together seamlessly:

```
Unified CLI (#339)
    ├── Position Alerts (#306)
    │   ├── Alert checking
    │   └── Alert history
    ├── GTC Scheduler (#287)
    │   ├── Status display
    │   └── Execution history
    └── Portfolio Monitoring
        ├── Account status
        └── Position P/L
```

**Morning Routine Flow:**

1. Scheduler runs at 9:20 AM ET
2. Fetches broker state (2 API calls)
3. Checks position alerts
4. Adjusts stops if needed
5. Saves state with alert history
6. Generates daily report

**User Interaction:**

```bash
python main.py

> check my alerts
# Shows results from morning run

> show scheduler status
# Confirms morning routine completed
```

---

## Related Documentation

### Core System Docs

- **Main README:** `/README.md` - System overview and quick start
- **Development:** `/docs/04_development/` - Project status and structure
- **Architecture:** `/docs/02_architecture/` - System design
- **ADRs:** `/architecture_decisions/` - Architecture decisions

### Issues

- #306 - Position Alerts System
- #287 - GTC Daily Execution
- #328 - YAML Prompt Management
- #339 - Unified Interactive CLI

---

## Support

**Questions?**

- Check this manual first
- See main README.md
- Review test results (#4)
- Check GitHub issues

**Found a bug?**

- Create GitHub issue
- Include steps to reproduce
- Attach relevant logs

**Need a feature?**

- Create GitHub issue with "enhancement" label
- Describe use case
- Explain benefit

---

## Version History

**v1.0 - 2025-01-10**

- Initial unified feature release
- Position alerts (#306)
- GTC scheduler (#287)
- Unified CLI (#339)
- All docs organized and sequenced
