# TODO - Complete #308 CLI Human-in-Loop MVP

**Last Updated**: January 12, 2025
**Progress**: ~70% Complete (on hold - UX improvements prioritized)
**Remaining**: 5-7 hours

## Recent Work (Jan 12, 2025)

### Interactive CLI - Beginner UX Improvements (#357)
- ✅ Fixed bare ticker parsing (e.g., "meta", "pltr" now work)
- ✅ Added intelligent clarification for ambiguous inputs
- ✅ Implemented layman terminology support ("get out", "cash out", etc.)
- ✅ Created plain English prompts (no jargon)
- ✅ Added `/tips` command for trading education
- ✅ Flexible response acceptance (numbers, keywords, casual language)
- ✅ Updated documentation with new test cases
- ✅ Created custom `/code-review` command for grooming

**Key Improvements:**
- Bare ticker "pltr" → reformats to "analyze PLTR"
- SELL signal + no position → asks "BUY or SHORT or REVIEW?"
- Recognizes 10+ layman sell terms
- Educational tips for non-traders

See issue #357 for full details.

## Previous Work (Nov 10-11, 2025)

### Scheduler System Improvements
- ✅ Created dedicated scheduler CLI (`/schedule` command)
- ✅ Fixed entry price display bug (#349)
- ✅ Implemented "carbon copy" approach for stop/target prices
- ✅ Investigated Alpaca bracket order API limitations
- ✅ Enhanced morning/evening routine reports
- ✅ Cleaned up debug output
- ✅ Updated documentation comprehensively

See `docs/sessions/2025-11-11_alpaca_bracket_order_fix.md` for details.

---

## ✅ Completed (70%)

### Core Components
- [x] Core interfaces (InputParser, StrategyAnalyzer, RiskManager, ExecutionManager)
- [x] Data models (TradeRequest, AnalysisResult, RiskAssessment, TradeSuggestion, OrderResult)
- [x] TradingOrchestrator (central coordinator)
- [x] LLMService + OpenAIService
- [x] LLMParser (natural language parsing)
- [x] VoterStrategy (MVP stub)
- [x] SimpleRiskManager (portfolio %, buying power)
- [x] AlpacaExecutionManager (order execution)
- [x] Foundation tests (4/4 passing)

---

## 🚧 Remaining Work (30%)

### 1. Configuration System (1-2 hours) - PRIORITY 1

**Goal**: Enable dependency injection and component wiring via YAML config

**Files to Create**:
- `config/orchestrator_config.yaml` - Component selection and parameters
- `config/llm_config.yaml` - LLM provider settings (OpenAI API key, models)
- `src/core/factory.py` - OrchestratorFactory to build from config

**orchestrator_config.yaml** structure:
```yaml
# Component selection
input_parser:
  type: "llm_parser"
  llm_service: "openai"

strategy_analyzer:
  type: "voter_strategy"
  # Later: can swap to "options_strategy" or "multi_agent"

risk_manager:
  type: "simple_risk"
  default_position_pct: 5.0
  max_position_pct: 15.0
  # Later: can swap to "portfolio_manager"

execution_manager:
  type: "alpaca_execution"
  # order_manager will be injected
```

**llm_config.yaml** structure:
```yaml
openai:
  tool_calling_model: "gpt-4o-mini"
  reasoning_model: "gpt-4o-mini"  # Can use o3-mini but expensive
  api_key_env: "OPENAI_API_KEY"
  temperature: 0.0
```

**OrchestratorFactory** responsibilities:
1. Load YAML configs
2. Instantiate components based on config
3. Inject dependencies
4. Return wired TradingOrchestrator

**Example usage**:
```python
from core.factory import OrchestratorFactory

factory = OrchestratorFactory()
orchestrator = factory.create_from_config("config/orchestrator_config.yaml")

# Now ready to use
decision = await orchestrator.process_request("is SPY good?", user_id)
```

---

### 2. CLI Presentation Layer (2-3 hours) - PRIORITY 2

**Goal**: Interactive REPL for conversational trading

**Files to Create**:
- `src/presentation/cli/cli_session.py` - Main REPL loop
- `src/presentation/cli/formatters.py` - Output formatting (rich library)
- `src/presentation/cli/commands.py` - CLI-specific commands (help, exit, status)

**Features Needed**:

#### A. Interactive Session Loop
```python
# cli_session.py
class CLISession:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.autonomy_mode = "confirm"  # or "auto"

    async def run(self):
        # Welcome message
        # Loop: get user input → process → display → confirm → execute
        # Handle commands: /help, /exit, /status, /set auto
```

#### B. Rich Formatting
```python
# formatters.py
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

def format_suggestion(suggestion):
    # Create beautiful formatted output
    # Use colors, tables, panels
    # Display: signal, entry, stop, target, quantity, portfolio %
```

#### C. Confirmation Workflow
```
> is SPY at 600 good?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 SPY @ $600.25
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ ENTRY SUGGESTED

📈 Technical Analysis:
   • MACD: BUY (bullish crossover) [STUB]
   • RSI: NEUTRAL (value: 52) [STUB]
   • Confidence: 75.0%

💰 Entry Plan:
   • Entry: $600.00 - $600.50
   • Stop Loss: $588.00 (-2.0%)
   • Target: $621.00 (+3.5%)
   • Position: 8 shares (4.8% portfolio)
   • Order Type: GTC

⚠️  Warnings: None

Continue? [yes/no/modify/skip]: _
```

#### D. Autonomy Modes
- **Confirm mode** (default): Ask for every trade
- **Auto mode**: Execute automatically, just show results

**Commands**:
- `/help` - Show help
- `/exit` - Exit session
- `/status` - Show current settings
- `/set auto` - Enable auto-execute mode
- `/set confirm` - Enable confirm mode (default)

---

### 3. Main Integration (1 hour) - PRIORITY 3

**Goal**: Wire everything in main.py and add `trade-assist` command

**File to Modify**: `main.py`

**Add new command**:
```python
def trade_assist():
    """
    Interactive CLI trading assistant.

    Powered by AutoGen multi-agent framework with human-in-loop oversight.

    Usage: python main.py trade-assist
    """
    import asyncio
    from presentation.cli import CLISession
    from core.factory import OrchestratorFactory

    # Create orchestrator from config
    factory = OrchestratorFactory()
    orchestrator = factory.create_from_config()

    # Run CLI session
    session = CLISession(orchestrator)
    asyncio.run(session.run())
```

**Add to CLI**:
```python
# In main() function
elif command == "trade-assist":
    trade_assist()
```

**Test**:
```bash
python main.py trade-assist
```

---

### 4. End-to-End Integration Tests (1 hour) - PRIORITY 4

**Goal**: Validate complete workflow works

**File to Create**: `tests/test_integration.py`

**Tests Needed**:

#### A. Full Workflow Test
```python
async def test_full_workflow():
    """Test complete flow: parse → analyze → risk → suggest → execute"""
    # Create real orchestrator with stub components
    # Process request
    # Verify suggestion created
    # Approve decision
    # Execute trade
    # Verify OrderResult
```

#### B. Configuration Loading Test
```python
def test_factory_creates_orchestrator():
    """Test OrchestratorFactory loads config and builds orchestrator"""
    factory = OrchestratorFactory()
    orchestrator = factory.create_from_config("config/orchestrator_config.yaml")
    assert orchestrator is not None
```

#### C. CLI Session Test (if time permits)
```python
async def test_cli_session():
    """Test CLI can process user input and display results"""
    # Mock stdin/stdout
    # Simulate user input
    # Verify output formatted correctly
```

---

### 5. Documentation Updates (30 min) - ONGOING

**Files to Update**:

#### A. Update project_status.md
- Mark #308 as complete
- Update phase status
- Add completion date

#### B. Update README.md (if needed)
- Add `trade-assist` command to usage
- Update quick start

#### C. Create USER_GUIDE.md (optional)
```markdown
# Quick Start Guide

## Installation
...

## Running Trade Assistant
```bash
python main.py trade-assist
```

## Example Usage
> is SPY at 600 a good entry?
...

## Commands
/help - Show help
/exit - Exit
/set auto - Auto-execute mode
```

---

## 🎯 Recommended Order

1. **Configuration** (1-2h) - Enables everything else
2. **Factory** (30min) - Wires components
3. **Basic CLI** (1-2h) - Minimal REPL to test
4. **Main Integration** (30min) - Add trade-assist command
5. **Test End-to-End** (30min) - Validate it works
6. **Polish CLI** (1h) - Add rich formatting, improve UX
7. **Documentation** (30min) - Update docs

**Total**: 5-7 hours

---

## 💡 Quick Wins for Minimal Demo

If time is limited, this gets a working demo fastest:

1. **Hardcoded Factory** (15 min)
   - Skip YAML, hardcode component creation in factory
   - Just get orchestrator wired up

2. **Basic CLI** (30 min)
   - Simple input() loop
   - Print suggestions (no rich formatting)
   - y/n confirmation

3. **Main integration** (15 min)
   - Add trade-assist command
   - Call CLI session

**Total for minimal demo**: 1 hour

Then iterate to add:
- YAML config
- Rich formatting
- Better error handling
- Tests

---

## 🧪 Testing Strategy

### Unit Tests (Already Done)
- ✅ Core models
- ✅ VoterStrategy
- ✅ TradingOrchestrator
- ✅ Suggestion merging

### Integration Tests (TODO)
- [ ] Factory creates orchestrator from config
- [ ] Full workflow executes
- [ ] CLI processes input correctly

### Manual Testing (TODO)
- [ ] Run trade-assist command
- [ ] Enter various requests
- [ ] Verify formatting looks good
- [ ] Test confirm vs auto modes
- [ ] Test error handling

### Paper Trading (OPTIONAL)
- [ ] If Alpaca credentials available
- [ ] Place real paper trade
- [ ] Verify order appears in Alpaca dashboard

---

## 🚫 Out of Scope (Defer to Later)

These are NOT needed for MVP:

- Session persistence (SessionStore) - defer
- Real VoterAgent integration - using stub OK for now
- Account service (real portfolio data) - fallback OK
- Complex error recovery - basic try/catch OK
- Logging to file - console logging OK
- GUI - CLI only for MVP
- Web API - CLI only for MVP

---

## 📝 Notes

- **Keep it simple**: MVP goal is to demonstrate the architecture works
- **Stub mode is OK**: Don't need real broker connection to validate
- **Test as you go**: Run quick tests after each component
- **Document decisions**: Update this file as you work

---

*This TODO will be updated as work progresses. Check off items as completed.*
