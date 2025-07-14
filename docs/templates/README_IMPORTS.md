# Import Ordering in Scripts

## The Problem

Scripts in this directory need to add the parent directory to Python's path before importing from `src`. However, linters (especially autopep8 in VS Code) tend to reorder imports, moving the `sys.path.insert` line after the local imports, which breaks the scripts.

## Solutions Implemented

### 1. Autopep8 Configuration

We've configured autopep8 to ignore E402 (module import not at top of file) through:

- `.pep8` configuration file
- `setup.cfg` with autopep8 section
- `.vscode/settings.json` for VS Code specific settings

### 2. Comment Directives

Use one of these comment patterns around the sys.path manipulation:

```python
# autopep8: off
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# autopep8: on
```

Or for multiple formatters:

```python
# fmt: off
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# fmt: on
```

### 3. Correct Import Pattern

All scripts should follow this pattern:

```python
#!/usr/bin/env python3
"""Script description."""

# Standard library imports
import sys
import os

# autopep8: off
# Add parent directory to path BEFORE any local imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# autopep8: on

# Now we can import from src
from src.module import something
from src.agents.agent import Agent

# Third-party imports
import pandas as pd
import numpy as np
```

## VS Code Settings

The project includes `.vscode/settings.json` which:

- Disables "organize imports" on save
- Configures autopep8 to ignore E402
- Sets appropriate line length

## If Issues Persist

1. Reload VS Code window after changes
2. Check that VS Code is using the project settings (not user settings)
3. Manually run: `autopep8 --ignore=E402 script.py`
4. Use `# noqa: E402` on specific import lines as last resort

## Testing

To verify autopep8 won't break your imports:

```bash
autopep8 --diff --ignore=E402 scripts/your_script.py
```

This will show what changes autopep8 would make without modifying the file.
