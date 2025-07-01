# Utils Directory

This directory contains general-purpose utility modules used throughout the RH2MAS codebase.

## Modules

### `agent_utils.py`

General utilities for agent operations:

- `load_agent_config()` - Load agent configuration from JSON
- `QueryParser` - Parse natural language queries
- `DataProcessor` - Process and format data for agents

### `date_utils.py`

Date and time utilities:

- `get_default_timezone()` - Get default timezone
- `process_date_param()` - Process date parameters from various formats
- `get_processed_date_range()` - Get processed date range with timezone handling
- `localize_df()` - Localize DataFrame index to timezone

### `output_manager.py`

Output management for organized test results:

- `OutputManager` - Manages organized output structure for backtest results
- Creates timestamped directories with structured subdirectories
- Captures LLM reasoning and generates reports
- Extracts best insights from analysis

## Usage

```python
# Import utilities as needed
from src.utils.date_utils import process_date_param
from src.utils.agent_utils import load_agent_config
from src.utils.output_manager import OutputManager
```

## Note

These utilities were moved from `src/tools/` to provide better separation of concerns:

- `/src/tools/` - Contains tool implementations and tool-specific code
- `/src/utils/` - Contains general-purpose utilities used across the codebase
