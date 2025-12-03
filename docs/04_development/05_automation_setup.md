# Automation Setup Guide - AutoGen-Trader

**Last Updated**: November 24, 2025

Auto-formatting and linting setup for minimal manual review.

---

## Quick Start (5 Minutes)

### 1. Install Pre-Commit Hooks (Local Automation)

```bash
# Activate AutoTrader conda environment
conda activate AutoTrader

# Install pre-commit
pip install pre-commit

# Install the git hooks
pre-commit install

# Test the setup
pre-commit run --all-files
```

**What this does**:

- Automatically formats code before every commit
- Fixes markdown linting issues (MD022, MD032)
- Sorts Python imports
- Removes trailing whitespace
- Fixes end-of-file formatting
- Runs security scans with Bandit

### 2. Enable GitHub Actions (Remote Automation)

Already configured! When you push to:

- `feature/**` branches
- `development`
- `main`

GitHub Actions will:

- Auto-fix any issues you missed locally
- Commit and push the fixes automatically
- Add `[skip ci]` to prevent infinite loops

---

## How It Works

### Pre-Commit Hooks (Local, Instant)

**Runs before every commit**:

```bash
git commit -m "your message"
# ↓
# Auto-fixes run automatically:
# ✓ Black formatting (Python, line length 100)
# ✓ isort (import sorting)
# ✓ Ruff auto-fixes
# ✓ Markdown linting
# ✓ Whitespace cleanup
# ✓ Bandit security scan
# ↓
# Files fixed and staged automatically
# ↓
# Commit completes with fixed files
```

**Bypass if needed**:

```bash
git commit --no-verify -m "urgent fix"
```

### Auto-Fix on Push (Remote, 2-3 min)

**Runs after you push**:

```bash
git push
# ↓
# GitHub Actions triggered
# ↓
# All formatters run on entire codebase
# ↓
# If changes needed:
#   - Commit created: "style: Auto-fix code quality issues [skip ci]"
#   - Changes pushed automatically
# ↓
# Your local branch gets behind by 1 commit
# ↓
# Next pull: git pull (fast-forward merge)
```

**Important**: After pushing, wait 2-3 minutes then:

```bash
git pull  # Pull the auto-fix commit
```

---

## Configuration Files

### `.pre-commit-config.yaml`

Defines which auto-fixes run locally:

- **ruff**: Fast Python linter with auto-fix
- **black**: Python code formatting (line length 100)
- **isort**: Import sorting (compatible with black)
- **mypy**: Static type checking
- **trailing-whitespace**: Removes trailing spaces
- **end-of-file-fixer**: Ensures newline at EOF
- **check-yaml/json**: Validates config files
- **bandit**: Security vulnerability scanning

### `.markdownlint.json`

Markdown rules:

- **MD032**: Blank lines around lists ✅
- **MD022**: Blank lines around headings ✅
- **MD013**: Line length ❌ (disabled for docs)
- **MD033**: Allow HTML tags for special formatting

### `pyproject.toml`

Tool configuration:

- **Black**: Line length 100, Python 3.10 target
- **isort**: Compatible with black, recognizes src/ and config/
- **Ruff**: Modern linter, line length 100
- **pytest**: Test configuration, coverage settings
- **mypy**: Type checking rules
- **bandit**: Security scanning exclusions

---

## Workflows

### `auto-fix-on-push.yml`

**Triggers**: Push to `main`, `development`, `feature/**`
**Actions**:

- Runs black, isort, ruff on Python files
- Auto-commits and pushes fixes if changes detected
**Time**: ~2-3 minutes

### `lint.yml` (quality-check.yml)

**Triggers**: Pull requests to `main`, `development`
**Actions**:

- Non-blocking checks (warnings only)
- Runs ruff, pylint, black --check, mypy
- Security scanning with bandit
- Code complexity analysis with radon
**Time**: ~3-5 minutes

---

## Typical Workflow

### Scenario 1: Normal Commit (Everything Works)

```bash
# Make changes
echo "new code" >> src/new_file.py

# Commit (pre-commit auto-fixes run)
git commit -am "feat: Add new feature"
# [INFO] ruff.....................................................Passed
# [INFO] black....................................................Passed
# [INFO] isort....................................................Passed

# Push
git push
# GitHub Actions runs, no additional fixes needed
```

### Scenario 2: Pre-Commit Fixes Issues

```bash
# Make changes with bad formatting
echo "x=1" >> src/bad_format.py

# Commit triggers auto-fix
git commit -am "feat: Add feature"
# [INFO] black....................................................Failed
# - hook id: black
# - files were modified by this hook
# reformatted src/bad_format.py

# Files auto-fixed and staged
# Commit again (now passes)
git commit -am "feat: Add feature"
# [INFO] black....................................................Passed

git push
```

### Scenario 3: Bypass and Remote Fix

```bash
# Urgent commit, skip local checks
git commit --no-verify -m "fix: Critical bug"

# Push
git push

# GitHub Actions detects issues
# Auto-fix commit pushed: "style: Auto-fix code quality issues [skip ci]"

# Pull the fix
git pull
# Fast-forward merge, now in sync
```

---

## Maintenance

### Update Pre-Commit Hooks

```bash
# Update to latest versions
pre-commit autoupdate

# Run updated hooks
pre-commit run --all-files
```

### Disable Specific Hooks Temporarily

Edit `.pre-commit-config.yaml` and comment out:

```yaml
#  - repo: https://github.com/psf/black
#    rev: 24.1.1
#    hooks:
#      - id: black
```

### Check What Will Run

```bash
# Dry run (no changes)
pre-commit run --all-files --verbose
```

---

## Troubleshooting

### Pre-Commit Too Slow

```bash
# Only run on changed files (default)
git commit -am "message"

# Skip if urgent
git commit --no-verify -m "urgent"
```

### Conflicts with Auto-Fix Commits

```bash
# Pull before pushing
git pull --rebase
git push
```

### Disable GitHub Actions Temporarily

Add `[skip ci]` to your commit message:

```bash
git commit -m "wip: Work in progress [skip ci]"
```

### Import Errors in Pre-Commit

If mypy or other tools fail due to missing imports:

```bash
# Install project in editable mode
pip install -e .

# Re-run hooks
pre-commit run --all-files
```

---

## Cost Analysis

### GitHub Actions Usage

- **Free tier**: 2,000 minutes/month
- **Auto-fix workflow**: ~2-3 min per push
- **Quality check workflow**: ~3-5 min per PR
- **Estimated usage**: ~10-20 pushes/week = 50-100 min/month
- **Verdict**: Well within free tier ✅

### Local Performance

- **Pre-commit hooks**: ~5-15 seconds per commit
- **Impact**: Minimal, runs in background
- **Verdict**: Negligible ✅

---

## When to Use What

| Situation | Use Pre-Commit | Use Auto-Fix on Push | Use `--no-verify` |
|-----------|----------------|----------------------|-------------------|
| Normal development | ✅ Yes | ✅ Yes (safety net) | ❌ No |
| Urgent hotfix | ⚠️ Maybe | ✅ Yes | ✅ Yes |
| WIP commits | ✅ Yes | ❌ No (`[skip ci]`) | ⚠️ Maybe |
| Large refactoring | ✅ Yes | ✅ Yes | ❌ No |
| Documentation only | ✅ Yes | ✅ Yes | ❌ No |

---

## Advanced Configuration

### Run Specific Hook Only

```bash
# Only run black
pre-commit run black --all-files

# Only run ruff
pre-commit run ruff --all-files

# Only run security scan
pre-commit run bandit --all-files
```

### Add Custom Hooks

Edit `.pre-commit-config.yaml`:

```yaml
  - repo: local
    hooks:
      - id: check-api-keys
        name: Check for hardcoded API keys
        entry: bash -c 'grep -r "API_KEY.*=" src/ && exit 1 || exit 0'
        language: system
```

### Adjust Line Length

Edit `pyproject.toml`:

```toml
[tool.black]
line-length = 120  # Change from 100 to 120

[tool.ruff]
line-length = 120
```

---

## Project-Specific Notes

### AutoTrader Conda Environment

Always activate the AutoTrader environment before running tools:

```bash
conda activate AutoTrader
pip install -e ".[dev]"  # Installs project + dev dependencies from pyproject.toml
pre-commit install
```

### Config Files Location

Trading configuration files in `config_defaults/` are formatted by black/isort:

- `trading_config.py`
- `market_hours.yaml`
- `cli_messages.yaml`

### Deprecated Code

The `src/deprecated/` directory is excluded from:

- Pre-commit hooks
- Linting checks
- Test coverage

This preserves legacy V0-V4 sentiment framework for reference.

---

## Next Steps

1. **Install pre-commit**: `conda activate AutoTrader && pip install -r requirements-dev.txt`
2. **Setup hooks**: `pre-commit install`
3. **Test it**: `pre-commit run --all-files`
4. **Make a commit**: Watch it auto-fix
5. **Push to GitHub**: Watch Actions auto-fix remotely
6. **Pull changes**: `git pull` after Actions complete

---

## Related Documentation

- [Codebase Structure](01_codebase_structure.md)
- [Project Status](02_project_status.md)
- [CLAUDE.md](../../CLAUDE.md) - AI assistant instructions

**Last Updated**: November 24, 2025
