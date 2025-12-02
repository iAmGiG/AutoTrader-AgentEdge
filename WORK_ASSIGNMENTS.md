# Contributing Guide

**Repository**: AutoGen-Trader (AgentEdge Multi-Agent Trading System)

This document explains how to work on issues and contribute to the codebase.

---

## Getting Started

### Prerequisites

```bash
# Python 3.10+ required
conda create -n AutoTrader python=3.10
conda activate AutoTrader
pip install -e .
```

### Project Structure

See [docs/04_development/01_codebase_structure.md](docs/04_development/01_codebase_structure.md) for:

- Directory organization
- Module dependencies
- Import conventions

### Architecture

See [docs/02_architecture/](docs/02_architecture/) for:

- Core system design
- Agent architecture
- Data flow diagrams

---

## Development Workflow

### 1. Pick an Issue

Check [GitHub Issues](https://github.com/iAmGiG/AutoTrader-AgentEdge/issues) for:

- `good first issue` - Entry-level tasks
- Current priority issues
- See [docs/04_development/02_project_status.md](docs/04_development/02_project_status.md) for roadmap

### 2. Create a Worktree

```bash
# For issue #NNN:
git worktree add "AutoGen-Trader-wt-NNN" feature/development
cd "AutoGen-Trader-wt-NNN"
git checkout -b feature/description-NNN
```

### 3. Make Changes

- Follow [docs/05_decisions/01_code_organization.md](docs/05_decisions/01_code_organization.md) for structure
- Follow [docs/05_decisions/02_error_handling_logging.md](docs/05_decisions/02_error_handling_logging.md) for error handling
- Follow [docs/05_decisions/03_api_caching_patterns.md](docs/05_decisions/03_api_caching_patterns.md) for caching
- Follow [docs/05_decisions/04_agent_singleton_patterns.md](docs/05_decisions/04_agent_singleton_patterns.md) for agent patterns

### 4. Test Locally

```bash
# Run unit tests
python -m pytest tests/ -v

# Code quality checks
ruff check src/
black --check src/

# Type checking
mypy src/ --ignore-missing-imports
```

### 5. Commit & Push

```bash
git add <files>
git commit -m "feat(#NNN): Brief description

Detailed explanation of changes.
Closes #NNN"

git push origin feature/description-NNN
```

### 6. Create Pull Request

```bash
gh pr create --base feature/development
```

- Reference the issue in description
- Link any related issues
- Describe testing approach

### 7. Code Review & Merge

- Address review feedback
- Ensure all tests pass
- Merge via GitHub UI

### 8. Cleanup

```bash
git worktree remove "AutoGen-Trader-wt-NNN"
```

---

## Testing Strategy

### Unit Tests

```bash
python -m pytest tests/unit/ -v
```

### Integration Tests

```bash
python -m pytest tests/integration/ -v
```

### VoterAgent Validation

```bash
# Run production-ready voting agent test
python -c "from src.autogen_agents.voter_agent import VoterAgent; print('VoterAgent: Production Ready')"
```

### Forward Testing

See [docs/testing/forward_test_protocol.md](docs/testing/forward_test_protocol.md) for:

- 30-day validation framework
- Performance metrics
- Acceptance criteria

---

## Code Quality Standards

### Linting & Formatting

Pre-commit hooks enforce:

- **Black**: Code formatting
- **Ruff**: Linting
- **isort**: Import ordering

### Architecture Decisions

All significant design choices are documented as ADRs in [docs/05_decisions/](docs/05_decisions/):

- **01_code_organization.md** - Directory structure, imports, deprecated code
- **02_error_handling_logging.md** - Log levels, exception patterns
- **03_api_caching_patterns.md** - Cache strategy, TTL rules
- **04_agent_singleton_patterns.md** - Agent lifecycle, thread safety

### Deprecation

When removing code:

1. Move to `src/deprecated/{component_name}/`
2. Update any imports to point to deprecated location
3. Add deprecation notice in module docstring
4. Create issue to track eventual removal

---

## Documentation

### When to Document

- **Code changes**: Update relevant docs/ files
- **New features**: Add to [docs/features/](docs/features/)
- **Bug fixes**: Update [docs/03_reference/05_known_issues.md](docs/03_reference/05_known_issues.md) if applicable
- **Architecture decisions**: Create/update ADR in [docs/05_decisions/](docs/05_decisions/)

### Documentation Location

```text
docs/
├── 01_overview/       # System overview for new users
├── 02_architecture/   # Technical deep-dives
├── 03_reference/      # Commands, terminology, troubleshooting
├── 04_development/    # Developer guides and project status
├── 05_decisions/      # Architecture Decision Records (ADRs)
├── features/          # Feature documentation
├── testing/           # Testing frameworks and protocols
└── archived/          # Historical research and experiments
```

---

## Key Resources

### For Quick Questions

- [README.md](README.md) - Project overview
- [docs/03_reference/02_terminology.md](docs/03_reference/02_terminology.md) - Definitions
- [docs/03_reference/03_commands.md](docs/03_reference/03_commands.md) - CLI reference

### For Implementation Details

- [docs/02_architecture/](docs/02_architecture/) - System design
- [docs/04_development/](docs/04_development/) - Developer guides
- [docs/05_decisions/](docs/05_decisions/) - Design patterns

### For Issue Context

- [docs/04_development/02_project_status.md](docs/04_development/02_project_status.md) - Current roadmap
- GitHub Issues - Detailed requirements and context

---

## Questions?

1. **How do I set up the dev environment?** → See "Getting Started" above
2. **What's the current architecture?** → See [docs/02_architecture/01_core_architecture.md](docs/02_architecture/01_core_architecture.md)
3. **What issues are high priority?** → See [docs/04_development/02_project_status.md](docs/04_development/02_project_status.md)
4. **How do I test my changes?** → See "Testing Strategy" above
5. **What are the code standards?** → See [docs/05_decisions/](docs/05_decisions/)
