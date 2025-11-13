# 001 - Code Organization Standards

**Status:** Accepted
**Date:** 2025-11-09
**Audience:** Junior to intermediate developers, AI tools
**Purpose:** Provide starting bias for code structure, naming, and organization

---

## Context

Code grooming revealed:
- Logger bug (used before definition)
- 57 mid-file imports
- 36KB dead code
- Inconsistent patterns

This ADR establishes baseline standards to reduce cognitive load and maintain consistency.

---

## Decision

Standards organized by: **MUST** (required), **SHOULD** (strong preference), **MAY** (optional).

---

### 1. Project Structure

```
AutoGen-TradingSystem/
├── src/                    # All source code
│   ├── core/              # Core business logic
│   ├── cli/               # CLI interface
│   ├── services/          # External services (LLM, APIs)
│   ├── trading/           # Trading infrastructure
│   ├── utils/             # Multi-class utilities only
│   └── [domain folders]   # Max 3 levels deep
├── tests/                 # One-shot tests (API keys, connections)
├── config/                # Configuration files
├── docs/                  # Documentation
├── architecture_decisions/ # This folder
└── main.py                # Entry point (root only for required files)
```

**Nesting Rules:**
- **MUST** keep max 3 levels deep
- **SHOULD** add 3rd level only if 2+ files warrant it
- **Root level**: Only `main.py` and required files (`.gitignore`, `README.md`, etc.)

**Utils Folder:**
- **MUST** place utilities in `utils/` only if used by multiple classes
- **SHOULD** question single-use "utilities" - likely belongs in the class itself
- Example: If only `TradingOrchestrator` uses it, put it in `core/trading_orchestrator.py`

---

### 2. Import Organization

**All imports MUST be at top** (after docstring):

```python
"""Module docstring."""

# Standard library
import logging
from datetime import datetime
from typing import Optional, List

# Third-party
import pandas as pd

# Local
from core.models import Signal
from services.llm import LLMService

logger = logging.getLogger(__name__)  # AFTER all imports
```

**Grammar:**
```
imports ::= [docstring] stdlib_imports third_party_imports local_imports logger_init
stdlib_imports ::= import | from ... import ...
terminal: logger = logging.getLogger(__name__)
```

**Rules:**
- **MUST** have three groups: stdlib → third-party → local (blank lines between)
- **MUST** initialize logger AFTER all imports
- **NEVER** import inside functions (use module-level try/except with availability flags)
- **MUST** follow PEP8/linter standards for style (don't overthink it)

**Conditional Imports:**

```python
# Module-level with availability flag
try:
    from alpaca.trading import TradingClient
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    logger.warning("Alpaca not available")
```

---

### 3. Class Structure & Method Ordering

**CFG for class organization:**

```
class_def ::= docstring public_init public_methods private_methods
public_methods ::= core_methods helper_methods
terminal_order: __init__ → public core → public helpers → private (_methods)
```

**Example:**

```python
class TradingOrchestrator:
    """
    Orchestrates trade request processing.

    Coordinates: parser → strategy → risk → execution
    """

    def __init__(self, parser, strategy, risk_mgr, exec_mgr):
        """
        Initialize orchestrator.

        Args:
            parser: Input parser instance
            strategy: Strategy analyzer instance
            risk_mgr: Risk manager instance
            exec_mgr: Execution manager instance
        """
        self.parser = parser
        self.strategy = strategy
        self.risk_mgr = risk_mgr
        self.exec_mgr = exec_mgr

    # Core public methods (main functionality)
    async def process_request(self, user_input: str) -> Decision:
        """Process user request through pipeline."""
        request = await self.parser.parse(user_input)
        return await self._execute_pipeline(request)

    # Helper public methods
    def get_status(self) -> dict:
        """Get orchestrator status."""
        return {"ready": True}

    # Private methods (internal helpers)
    def _execute_pipeline(self, request):
        """Internal pipeline execution."""
        pass
```

**Method Ordering Rules:**
1. `__init__` (always first)
2. Core public methods (main functionality)
3. Helper public methods (utilities, getters)
4. Private methods (`_prefixed`)

---

### 4. Naming Standards

**Follow Python standards** (reduce overhead thinking):

| Type | Standard | Example |
|------|----------|---------|
| Files | `snake_case.py` | `trading_orchestrator.py` |
| Classes | `PascalCase` | `TradingOrchestrator` |
| Functions/Methods | `snake_case()` | `process_request()` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRIES` |
| Private | `_prefix` | `_internal_method()` |

**NEVER** include dates in filenames (unless explicitly requested).

---

### 5. Docstrings

**Standard position** - under `def` signature in `"""quotes"""`:

```python
def calculate_position_size(ticker: str, price: float, portfolio: float) -> int:
    """
    Calculate position size based on portfolio percentage.

    Args:
        ticker: Stock symbol
        price: Entry price per share
        portfolio: Total portfolio value

    Returns:
        Number of shares to purchase
    """
    return int((portfolio * 0.05) / price)
```

**Rules:**
- **MUST** include: params, return, 1-2 sentences on what it does
- **MAY** add more detail for complex/critical methods
- **SHOULD** be concise and actionable

---

### 6. Optimization & Caching

**Optimization Philosophy:**
- **MUST** make it work first
- **SHOULD** optimize after working, unless known shortcut/existing optimization exists
- **MAY** apply known patterns upfront if they're already standard

**Caching Standard:**

> **Cache EVERYTHING API-wise.**
> SQLite/local system is ALWAYS faster than API calls.
> Follow web backend practices: cache first, invalidate intelligently.

```python
# MUST cache all API calls
@lru_cache(maxsize=128)
def get_market_data(ticker: str, date: str):
    """Fetch market data (cached)."""
    return api_call(ticker, date)

# SHOULD use SQLite for persistent caching
class MarketDataCache:
    def __init__(self):
        self.db = sqlite3.connect('cache/market_data.db')

    def get_or_fetch(self, ticker, date):
        cached = self._check_db(ticker, date)
        if cached:
            return cached

        data = fetch_from_api(ticker, date)
        self._save_to_db(ticker, date, data)
        return data
```

**This is THE standard** - not optional for API calls.

---

### 7. Testing Workflow

**Depends on size:**

| Scenario | Approach |
|----------|----------|
| Adding method to existing class | Test on the spot |
| Creating new class | Get core methods in place, then test |
| Major feature | Multi-pass grooming before testing |

**Test Folder:**
- Tests in `tests/` folder (NOT root)
- Use for one-shot testing (API keys, connections)
- **SHOULD** groom between major prompts and critical testing phases

---

### 8. Refactoring Strategy

**Do it in batches, in tiers:**

**Tier 1 - Quick Wins:**
- Single method refactors
- Import organization
- Naming consistency

**Tier 2 - Medium Effort:**
- Dead code removal
- Consolidating duplicate logic
- Adding missing docstrings

**Tier 3 - Major Overhauls:**
- Structure reorganization
- Cleaning over-engineering
- Breaking apart god classes

**Timing:** Between major features, during grooming sessions.

---

### 9. Development Tooling

**MUST use:**
- VS Code format linter (run after file completion)
- PEP8 compliance via linter
- Auto-format on save

**SHOULD reference:**
- Public Python standards (PEP8, Google Style Guide)
- Keep thinking minimal - don't reinvent the wheel

**VS Code Settings:**
```json
{
  "editor.formatOnSave": true,
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black"
}
```

---

### 10. Type Hints

**Follow existing standards** - customize when needed later.

```python
# Current approach - add when it adds clarity
def process_data(ticker: str, data: pd.DataFrame) -> dict:
    """Process market data."""
    pass

# Future: May add stricter typing if tooling demands it
```

---

### 11. Quick Reference

**Before committing code:**
- [ ] Imports at top (stdlib → third-party → local)
- [ ] Logger after imports
- [ ] Methods ordered: `__init__` → core public → helpers → private
- [ ] Docstrings present (params, return, description)
- [ ] API calls cached
- [ ] Run VS Code formatter
- [ ] No files in root (except main.py and required)

---

### 12. Examples from Codebase

**Logger Bug (Why imports matter):**

```python
# ❌ BROKEN
try:
    from trading.alpaca_trading_client import AlpacaOrderManager
except ImportError:
    logger.warning("Not available")  # NameError!

logger = logging.getLogger(__name__)  # Too late

# ✅ FIXED
logger = logging.getLogger(__name__)  # First

try:
    from trading.alpaca_trading_client import AlpacaOrderManager
except ImportError:
    logger.warning("Not available")  # Works
```

**Utils Placement:**

```python
# ❌ Over-engineered
# src/utils/orchestrator_helper.py - only used by TradingOrchestrator
def validate_request(request):
    pass

# ✅ Keep it local
# src/core/trading_orchestrator.py
class TradingOrchestrator:
    def _validate_request(self, request):
        """Internal validation."""
        pass
```

---

## Rationale

**Why these standards?**

1. **Imports at top** - Prevents bugs, clear dependencies
2. **Method ordering** - Easier navigation, predictable structure
3. **Cache everything** - API calls are expensive, local is fast
4. **Utils discipline** - Prevents utility folder bloat
5. **Groom regularly** - Catches issues before they compound
6. **Minimal thinking** - Follow standards, focus on features

**Meta goal:** Keep simple code decisions minimal, development smooth.

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-09 | Initial version based on code grooming |
