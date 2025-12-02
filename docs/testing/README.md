# Testing Documentation

This directory contains testing frameworks, guidelines, and protocols for AutoGen-Trader.

## Quick Navigation

### Testing Protocols

1. **[Forward Testing Protocol](01_forward_test_protocol.md)**
   - 30-day validation framework before live deployment
   - Performance metrics and acceptance criteria
   - How to run forward tests
   - Interpreting results and reports
   - **Use this** to validate new strategies or major changes

---

## Testing Strategy Overview

### Unit Tests

Located in: `tests/unit/`

Run all unit tests:

```bash
python -m pytest tests/unit/ -v
```

Run specific test file:

```bash
python -m pytest tests/unit/trading/test_trailing_stop_manager.py -v
```

Run with coverage:

```bash
python -m pytest tests/unit/ --cov=src --cov-report=html
```

### Integration Tests

Located in: `tests/integration/`

Run integration tests:

```bash
python -m pytest tests/integration/ -v
```

Integration tests require valid configuration (API keys, etc.)

### Forward Testing

The **forward testing protocol** validates system performance over 30 days before live trading.

**When to use:**

- Testing new strategies
- Validating major changes to core logic
- Before enabling live trading on new account
- Baseline performance comparison

**How it works:**

1. Run system in paper trading for 30 consecutive days
2. Track all trades and performance metrics
3. Calculate Sharpe ratio, win rate, max drawdown, etc.
4. Compare against acceptance criteria
5. Generate detailed report with recommendations

See [01_forward_test_protocol.md](01_forward_test_protocol.md) for full details.

### Backtesting

Historical validation of strategies:

```bash
# Run VoterAgent backtest on historical data
python tests/experiment_293_macd_vs_voting.py

# Run extended period backtest
python tests/experiment_extended_period_voting.py
```

See [../03_reference/01_validation_results.md](../03_reference/01_validation_results.md) for historical results.

---

## Test Organization

```text
tests/
├── unit/                          # Fast unit tests (< 1s each)
│   ├── agents/                    # Agent tests
│   ├── trading/                   # Trading logic tests
│   ├── execution/                 # Order execution tests
│   └── risk/                      # Risk management tests
│
├── integration/                   # Integration tests (requires setup)
│   ├── broker/                    # Broker integration tests
│   ├── data_sources/              # Market data tests
│   └── cli/                       # CLI integration tests
│
└── experiment_*.py                # Forward testing scripts
    ├── experiment_293_macd_vs_voting.py
    └── experiment_extended_period_voting.py
```

---

## Running Tests

### Quick Test (development)

```bash
# Run fast unit tests only
python -m pytest tests/unit/ -v --tb=short
```

### Full Test Suite

```bash
# Run all tests with coverage
python -m pytest tests/ -v --cov=src --cov-report=html
```

### Specific Component

```bash
# Test trading module only
python -m pytest tests/unit/trading/ -v

# Test a single function
python -m pytest tests/unit/trading/test_trailing_stop_manager.py::TestTrailingStopManager::test_trailing_stop_adjustment -v
```

### With Markers

```bash
# Run only fast tests
python -m pytest -m "not slow" tests/

# Run only slow tests
python -m pytest -m "slow" tests/
```

---

## Writing Tests

### Test File Structure

```python
# tests/unit/module/test_feature.py
import pytest
from src.module.feature import MyClass


class TestMyClass:
    """Test MyClass functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.obj = MyClass()

    def teardown_method(self):
        """Clean up after tests."""
        pass

    def test_basic_functionality(self):
        """Test basic feature behavior."""
        result = self.obj.do_something()
        assert result == expected

    def test_error_condition(self):
        """Test error handling."""
        with pytest.raises(ValueError):
            self.obj.invalid_operation()
```

### Best Practices

1. **Arrange, Act, Assert**

   ```python
   # Arrange
   input_data = {"symbol": "AAPL", "qty": 10}

   # Act
   result = order_manager.place_order(input_data)

   # Assert
   assert result.status == "pending"
   ```

2. **Use descriptive names**

   ```python
   def test_market_order_filled_immediately():
       # Clear what's being tested
   ```

3. **Test one thing per test**
   - Each test should validate one behavior
   - If you need multiple assertions, they should test the same logical behavior

4. **Use fixtures for setup**

   ```python
   @pytest.fixture
   def sample_order():
       return Order(symbol="AAPL", qty=10, side="buy")

   def test_order_validation(sample_order):
       assert sample_order.is_valid()
   ```

---

## Code Coverage

View coverage report:

```bash
# Generate HTML coverage report
python -m pytest tests/ --cov=src --cov-report=html

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

**Coverage targets:**

- Core trading logic: 90%+
- Utilities: 80%+
- CLI: 70% (harder to test interactively)

---

## Continuous Integration

Tests run automatically on:

- Pull request creation
- Push to feature branches
- Merge to `feature/development`

Pre-commit hooks run before commit:

- Unit tests (quick subset)
- Code linting
- Type checking

---

## Debugging Failed Tests

### Enable verbose output

```bash
python -m pytest tests/ -vv --tb=long
```

### Use pytest debugging

```bash
# Drop into debugger on failure
python -m pytest tests/ --pdb

# Drop into debugger on first failure
python -m pytest tests/ -x --pdb
```

### Print debug output

```python
def test_something():
    result = function()
    print(f"Result: {result}")  # Will show with -s flag
    assert result == expected

# Run with:
# python -m pytest tests/ -s
```

---

## Performance Testing

For performance-sensitive operations:

```python
import time

def test_fast_operation():
    """Ensure operation completes in < 100ms."""
    start = time.time()
    result = expensive_operation()
    elapsed = time.time() - start

    assert elapsed < 0.1, f"Operation took {elapsed}s, expected < 0.1s"
```

---

## Testing Checklist

Before committing:

- [ ] All tests pass locally: `pytest tests/`
- [ ] Coverage is acceptable: `pytest --cov`
- [ ] New features have tests
- [ ] Bug fixes have regression tests
- [ ] Pre-commit hooks pass: `git commit` (auto-runs)

---

## Questions?

1. **How do I run tests?** → See "Running Tests" section above
2. **How do I write a test?** → See "Writing Tests" section above
3. **How do I validate a strategy?** → See [01_forward_test_protocol.md](01_forward_test_protocol.md)
4. **What's the coverage target?** → See "Code Coverage" section above
5. **How do I debug a failing test?** → See "Debugging Failed Tests" section above
