# CLI Tools Implementation Notes

**Issues**: [#455 (Phase 1A)](https://github.com/iAmGiG/AutoTrader-AgentEdge/issues/455), [#456 (Phase 1B)](https://github.com/iAmGiG/AutoTrader-AgentEdge/issues/456)
**Parent Issue**: [#433](https://github.com/iAmGiG/AutoTrader-AgentEdge/issues/433) - Refactor cli_session.py to FunctionTool architecture
**Branch**: `feature/cli-tools-455-456`

## Completed Work

### Phase 1A: FunctionTool Infrastructure (#455) ✅

Created complete CLI tools infrastructure following AutoGen FunctionTool pattern:

#### 1. Tool Registry System

**File**: `src/cli/tools/__init__.py`

- `CliToolRegistry` class for managing CLI FunctionTools
- Category-based organization (MODE_TOOLS, TIMEFRAME_TOOLS, etc.)
- Auto-discovery mechanism that imports tool modules on startup
- Helper functions: `register_cli_tool()`, `get_cli_tool()`, `get_cli_tools_by_category()`, `get_all_cli_tools()`
- Global registry instance: `CLI_TOOL_REGISTRY`

**Key Features**:

- Type-safe tool registration with optional categories
- Duplicate detection with warnings
- Clean separation of concerns
- Extensible for future tool categories

#### 2. Example Tool Module

**File**: `src/cli/tools/example_tool.py`

Demonstrates the FunctionTool pattern with two simple examples:

- `echo_message(message, prefix=None)` - Echo with optional prefix
- `greet_user(name, formal=False)` - Greet with style selection

**Pattern Demonstrated**:

```python
# 1. Define pure function with type hints
def echo_message(message: str, prefix: Optional[str] = None) -> str:
    """Docstring becomes tool description"""
    ...

# 2. Wrap in FunctionTool
echo_tool = FunctionTool(
    func=echo_message,
    name="echo_message",
    description="Echo a message..."
)

# 3. Register with category
register_cli_tool(echo_tool, category=TIMEFRAME_TOOLS)
```

### Phase 1B: Mode and Timeframe Tools (#456) ✅

Extracted and wrapped existing CLI commands as FunctionTools:

#### 1. Timeframe Tools

**File**: `src/cli/tools/timeframe_tools.py`

Wraps `TimeframeCommands` (from [#365](https://github.com/iAmGiG/AutoTrader-AgentEdge/issues/365)) as 6 FunctionTools:

- `list_timeframes(verbose=False)` - List all available timeframes
- `set_timeframe(timeframe)` - Change active timeframe
- `show_current_timeframe()` - Show current timeframe
- `show_timeframe_recommendations()` - Show recommendations by trading style
- `validate_and_info(timeframe)` - Validate and show timeframe info
- `get_timeframe_for_agent(command, arg=None)` - Structured data for agents

**Integration**: Delegates to existing `src.cli.timeframe_commands.TimeframeCommands`

#### 2. Mode Tools

**File**: `src/cli/tools/mode_tools.py`

Wraps `TradingModeManager` (from [#400](https://github.com/iAmGiG/AutoTrader-AgentEdge/issues/400)) as 6 FunctionTools:

- `list_trading_modes()` - List all modes with descriptions
- `set_mode(mode)` - Change active trading mode
- `show_current_mode()` - Show current mode with full details
- `show_mode_comparison()` - Side-by-side comparison table
- `get_mode_parameters_dict(mode=None)` - Structured data for agents
- `validate_mode(mode)` - Validate mode name

**Integration**: Delegates to existing `src.core.trading_modes.TradingModeManager`

## Architecture

### Design Principles

1. **Pure Functions**: Each tool wraps a pure function with clear inputs/outputs
2. **Type Hints**: Function signatures auto-generate tool schemas
3. **Delegation**: Tools delegate to existing implementations (no duplication)
4. **Registry Pattern**: Central registry for discovery and organization
5. **Category Organization**: Tools grouped by domain for easy filtering

### File Structure

```text
src/cli/tools/
├── __init__.py              # Registry + auto-discovery
├── example_tool.py          # Example pattern demonstration
├── mode_tools.py            # Trading mode tools (#456)
└── timeframe_tools.py       # Timeframe tools (#456)
```

### Integration Points

**Existing Code Used**:

- `src/cli/timeframe_commands.py` - TimeframeCommands singleton
- `src/core/trading_modes.py` - TradingModeManager + helper functions
- `autogen_core.tools.FunctionTool` - AutoGen tool wrapper

**New Exports**:

- `from src.cli.tools import get_all_cli_tools, get_cli_tools_by_category`
- `from src.cli.tools.mode_tools import CLI_MODE_TOOLS`
- `from src.cli.tools.timeframe_tools import CLI_TIMEFRAME_TOOLS`

## Testing Status

### What Works ✅

- Tool registry class and helper functions
- Category-based organization
- Example tool pattern demonstration
- Mode and timeframe tool wrappers created
- Auto-discovery mechanism implemented

### Known Issues ⚠️

**Circular Import Problem**:

- Importing `src.cli.tools` triggers full application initialization
- `src.cli.__init__.py` imports `cli_session.py`
- `cli_session.py` imports entire agent system
- Agent system requires `config/config.json`

**Impact**:

- Cannot test in isolation without full environment
- Tools work correctly when imported in proper application context
- Auto-discovery loads successfully when app is properly initialized

**Solution Path**:

- Fix circular dependencies in main codebase (separate issue)
- Move tool imports out of module-level `__init__.py` files
- Use lazy loading or dependency injection patterns

## Usage Examples

### For CLI Session

```python
from src.cli.tools import get_cli_tools_by_category, MODE_TOOLS

# Get all mode tools
mode_tools = get_cli_tools_by_category(MODE_TOOLS)

# Use a specific tool
from src.cli.tools.mode_tools import show_current_mode
result = show_current_mode()
print(result)
```

### For Agents

```python
from src.cli.tools import get_all_cli_tools

# Register all CLI tools with an agent
all_tools = get_all_cli_tools()
agent.register_tools(all_tools)

# Or register specific categories
from src.cli.tools import get_cli_tools_by_category, TIMEFRAME_TOOLS
timeframe_tools = get_cli_tools_by_category(TIMEFRAME_TOOLS)
agent.register_tools(timeframe_tools)
```

### Direct Function Calls

```python
# Import and use functions directly
from src.cli.tools.mode_tools import set_mode, get_mode_parameters_dict

# Change mode
result = set_mode("conservative")
print(result)  # "✅ Trading mode changed from moderate to conservative"

# Get structured data
params = get_mode_parameters_dict("aggressive")
print(params["max_position_pct"])  # 0.20
```

## Next Steps

### Phase 2 (#433 continued)

Extract remaining CLI commands from `cli_session.py`:

1. **Account Tools** - Account switching, listing, status
2. **Portfolio Tools** - Portfolio display, position queries
3. **Order Tools** - Order placement, status, cancellation
4. **Scheduler Tools** - Schedule management commands
5. **Alert Tools** - Alert configuration commands

### Integration Tasks

1. Fix circular import issues in main codebase
2. Update `cli_session.py` to use tools instead of direct methods
3. Add CLI tool support to agent system
4. Create integration tests with full environment
5. Update documentation

### Future Enhancements

1. **Tool Validation** - Input validation before execution
2. **Tool Composition** - Combine tools into workflows
3. **Tool Documentation** - Auto-generate docs from schemas
4. **Tool Testing** - Comprehensive test suite per tool
5. **Tool Metrics** - Usage tracking and performance monitoring

## References

- **Parent Issue**: #433 - Refactor cli_session.py
- **Phase 1A**: #455 - Create FunctionTool infrastructure
- **Phase 1B**: #456 - Extract mode and timeframe tools
- **Related**: #365 - Timeframe commands
- **Related**: #400 - Trading modes system
- **Pattern Source**: `src/data_sources/tools.py` - Market data tools
- **Pattern Source**: `src/autogen_agents/base_agent.py` - Agent tool integration
