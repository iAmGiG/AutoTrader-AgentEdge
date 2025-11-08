#!/usr/bin/env python3
"""
Enhanced Linting Script for RH2MAS Code Quality

This script demonstrates how to integrate linting checks into the development workflow.
It can be used before commits or as part of the code review process.

Usage:
    python scripts/lint_check.py [path]
    python scripts/lint_check.py src/voting/
    python scripts/lint_check.py examples/basic_voting_demo.py

Features:
- Import ordering validation (PEP 8)
- Line length checks (100 character limit)
- Unused import detection
- Code style consistency
- Integration with existing pyproject.toml configuration
"""

import subprocess
import sys
from pathlib import Path


def run_ruff_check(target_path: str = ".") -> tuple[bool, str]:
    """
    Run Ruff linter on specified path.

    Args:
        target_path: Path to check (file or directory)

    Returns:
        Tuple of (success: bool, output: str)
    """
    try:
        # Run ruff check with project configuration
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", target_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        success = result.returncode == 0
        output = result.stdout + result.stderr

        return success, output

    except subprocess.TimeoutExpired:
        return False, "Linting check timed out"
    except FileNotFoundError:
        return False, "Ruff not installed. Run: pip install ruff"
    except Exception as e:
        return False, f"Error running linter: {e}"


def run_import_check(target_path: str = ".") -> tuple[bool, str]:
    """
    Check import ordering specifically.

    Args:
        target_path: Path to check

    Returns:
        Tuple of (success: bool, output: str)  
    """
    try:
        # Focus on import-related rules
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", target_path, "--select", "I"],
            capture_output=True,
            text=True,
            timeout=30
        )

        success = result.returncode == 0
        output = result.stdout + result.stderr

        return success, output

    except Exception as e:
        return False, f"Error checking imports: {e}"


def format_linting_report(success: bool, output: str, check_type: str) -> str:
    """Format linting results for display."""
    if success:
        return f"✅ {check_type}: All checks passed!"
    else:
        return f"❌ {check_type} Issues Found:\n{output}"


def main():
    """Main linting workflow."""
    # Determine target path
    target_path = sys.argv[1] if len(sys.argv) > 1 else "."

    # Verify path exists
    if not Path(target_path).exists():
        print(f"❌ Error: Path '{target_path}' does not exist")
        sys.exit(1)

    print("🔍 RH2MAS Code Quality Check")
    print(f"📁 Target: {target_path}")
    print("=" * 50)

    # Check 1: Import ordering (PEP 8)
    print("\n1️⃣ Checking import ordering...")
    import_success, import_output = run_import_check(target_path)
    print(format_linting_report(import_success, import_output, "Import Ordering"))

    # Check 2: Full linting suite
    print("\n2️⃣ Running full linting suite...")
    lint_success, lint_output = run_ruff_check(target_path)
    print(format_linting_report(lint_success, lint_output, "Full Linting"))

    # Summary
    print("\n" + "=" * 50)
    overall_success = import_success and lint_success

    if overall_success:
        print("🎉 All code quality checks passed!")
        print("✅ Ready for commit/code review")
        sys.exit(0)
    else:
        print("⚠️  Code quality issues found")
        print("💡 Fix issues before committing")
        print("\nTo auto-fix some issues:")
        print(f"   python -m ruff check --fix {target_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
