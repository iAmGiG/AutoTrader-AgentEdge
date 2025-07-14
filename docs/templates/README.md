# Templates Directory

This directory contains template files for common development patterns in the RH2MAS project.

## Available Templates

### script_template.py

A template for creating new Python scripts that need to import from the `src` directory.

Key features:

- Proper import order to avoid linter issues
- Standard library imports first
- Path manipulation before local imports
- Example imports from common modules

Usage:

```bash
cp docs/templates/script_template.py scripts/my_new_script.py
```

Then modify the imports and main function as needed for your specific use case.
