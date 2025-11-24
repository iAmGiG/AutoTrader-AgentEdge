# GitHub Actions Workflows

This directory contains automated workflows for the AutoGen-TradingSystem repository.

## Workflows

### `main.yml` - CI Tests

**Triggers:** Push to `main` branch, Pull requests to `main`

Runs the project's test suite using pytest to ensure code quality.

### `check-commit-signatures.yml` - Commit Signature Checker

**Triggers:**

- Pull requests (opened, synchronized, reopened)
- Push to `development` and `main` branches

**Purpose:** Prevents commits with Claude Code signatures from being merged.

**What it checks:**

- `Generated with [Claude Code]` - Auto-generated footer
- `Co-Authored-By: Claude <noreply@anthropic.com>` - Co-author signature

**Why:** Claude Code signatures should not appear in the repository's commit history. This workflow automatically detects and rejects any commits containing these signatures.

**If signatures are detected:**

1. The workflow will fail with an error message
2. Use the cleanup script to remove signatures:

   ```bash
   git filter-branch -f --msg-filter 'scripts/remove_commit_signatures.py' HEAD~10..HEAD
   git push -f origin <branch-name>
   ```

3. The PR will automatically update with the cleaned commits

## Related Scripts

- **`scripts/remove_commit_signatures.py`** - Python script to remove Claude Code signatures from commit messages
  - Used with `git filter-branch` to clean commit history
  - See script header for usage examples
