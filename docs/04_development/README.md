# Development Documentation

This directory contains guides for developers working on AutoGen-Trader.

## Quick Navigation

### Core References

1. **[Codebase Structure](01_codebase_structure.md)**
   - Project layout and module organization
   - Import conventions and patterns
   - Where to find specific functionality
   - **Start here** if you're new to the codebase

2. **[Project Status & Roadmap](02_project_status.md)**
   - Current implementation status
   - Completed features and known issues
   - Open issues and priorities
   - Sprint planning and milestones
   - **Check this** to understand what's being worked on

3. **[CLI Trade Assistant](03_cli_trade_assistant.md)**
   - Architecture of the interactive CLI
   - How human-in-the-loop trading works
   - Integration with trading cycle
   - **Reference this** for CLI-related changes

4. **[Cache Developer Guide](04_cache_developer_guide.md)**
   - SQLite caching system internals
   - API usage and examples
   - Performance tuning
   - **Read this** if working with market data or cache

5. **[Automation Setup](05_automation_setup.md)**
   - Pre-commit hooks configuration
   - GitHub Actions setup
   - Auto-formatting and linting
   - **Use this** to set up your development environment

---

## Related Documentation

**For architecture decisions**, see [docs/05_decisions/](../05_decisions/README.md)

**For feature documentation**, see [docs/features/](../features/README.md)

**For testing**, see [docs/testing/](../testing/README.md)

---

## Common Tasks

### Adding a New Feature

1. Read [01_codebase_structure.md](01_codebase_structure.md) for where to place code
2. Check [docs/05_decisions/](../05_decisions/) for relevant architectural patterns
3. Update [02_project_status.md](02_project_status.md) to track your work
4. Create tests in `tests/` following existing patterns
5. Document in `docs/features/` when ready for users

### Fixing a Bug

1. Create a GitHub issue (if not already created)
2. Check [02_project_status.md](02_project_status.md) for related issues
3. Write tests that reproduce the bug
4. Fix the bug
5. Update [02_project_status.md](02_project_status.md) when complete
6. Reference the issue in your commit message

### Improving Performance

1. Profile the code to identify bottlenecks
2. Check [04_cache_developer_guide.md](04_cache_developer_guide.md) for caching strategies
3. Review [docs/05_decisions/03_api_caching_patterns.md](../05_decisions/03_api_caching_patterns.md)
4. Implement improvements with tests
5. Document in commit message and relevant docs

### Understanding How Something Works

1. Start with [01_codebase_structure.md](01_codebase_structure.md) to find the files
2. Read code comments and docstrings
3. Check related ADRs in [docs/05_decisions/](../05_decisions/)
4. Look at tests in `tests/` for usage examples
5. Ask in GitHub issues if stuck

---

## Code Quality Standards

All code must follow standards in [docs/05_decisions/](../05_decisions/):

- **01_code_organization.md** - Directory structure and imports
- **02_error_handling_logging.md** - Error handling patterns
- **03_api_caching_patterns.md** - Cache implementation
- **04_agent_singleton_patterns.md** - Agent lifecycle

Pre-commit hooks enforce:

- Black formatting
- Ruff linting
- isort import ordering

---

## Architecture Decisions

Significant design decisions are documented as ADRs. Before making architectural changes, check [docs/05_decisions/](../05_decisions/).

---

## Testing Strategy

See [docs/testing/](../testing/) for:

- Unit testing guidelines
- Integration testing approach
- Forward testing protocol
- How to run tests

---

## Questions?

1. **Where do I put this code?** → [01_codebase_structure.md](01_codebase_structure.md)
2. **How does the CLI work?** → [03_cli_trade_assistant.md](03_cli_trade_assistant.md)
3. **How's the cache implemented?** → [04_cache_developer_guide.md](04_cache_developer_guide.md)
4. **What's the project status?** → [02_project_status.md](02_project_status.md)
5. **How should I design this?** → [docs/05_decisions/](../05_decisions/)
