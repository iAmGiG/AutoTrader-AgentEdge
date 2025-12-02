# Error Handling & Logging Standards

**Status:** Accepted | **Date:** November 2025

## Context

Inconsistent logging and error handling created confusion:

- Technical stack traces shown to users
- Important errors buried in debug noise
- Unclear when to log vs raise exceptions
- Fallback values logged as warnings (alarming users unnecessarily)

## Decision

### Log Levels

| Level | Use Case | Visible to User |
|-------|----------|-----------------|
| DEBUG | Internal state, cache decisions, detailed flow | No (dev only) |
| INFO | User-relevant status updates, successful operations | Yes |
| WARNING | Recoverable issues user should know about | Yes |
| ERROR | Failures requiring attention | Yes |

### User-Facing Messages

**Clean status messages** using helper functions:

```python
from src.utils.date_utils import format_data_status
logger.info(format_data_status("AAPL", "live"))
# Output: 📊 AAPL | 11/28/25 2:30 PM | Live data
```

**Expected fallbacks at DEBUG level:**

```python
# WRONG - alarming for expected behavior
logger.warning("Using fallback portfolio value: $100,000")

# RIGHT - only visible during debugging
logger.debug("Account service not configured - using demo portfolio")
```

**Actual errors at WARNING/ERROR level:**

```python
logger.warning(f"Failed to get portfolio value: {e}")
```

### Exception Handling

1. **Catch and translate for users** - hide technical details
2. **Never show tracebacks to users** - log at DEBUG with `exc_info=True`
3. **Fail fast for programmer errors** - don't catch `TypeError`, `AttributeError`

### Date/Time Formatting (Issue #403)

All user-facing output uses US format:

- Dates: `MM/DD/YY` (e.g., `11/28/25`)
- Times: `h:mm AM/PM` (e.g., `2:30 PM`)
- Helpers: `format_date_us()`, `format_time_us()`, `format_datetime_us()`

## Consequences

**Benefits:**

- Users see clean, actionable messages
- Developers can enable DEBUG for full context

**Trade-offs:**

- Requires discipline to choose correct log level

## Implementation

- Use `safe_print()` from `src/utils/safe_print.py` for CLI (handles emoji/Unicode)
- Date/time helpers in `src/utils/date_utils.py`
