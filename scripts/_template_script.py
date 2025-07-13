#!/usr/bin/env python3
"""Template for scripts that need to import from src.

This shows the proper import order to avoid linter issues.
"""
# Standard library imports
import sys
import os

# CRITICAL: Add parent directory to path BEFORE any local imports
# fmt: off
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# fmt: on

# Now we can import from src
from src.utils.example import example_function
from src.agents.base_agent import BaseAgent

# Third-party imports
import pandas as pd
import numpy as np


def main():
    """Main function."""
    print("Script template")


if __name__ == "__main__":
    main()