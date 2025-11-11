# 002 - YAML-Based Prompt Management

**Status:** Accepted
**Date:** 2025-11-10
**Audience:** Developers, prompt engineers, AI agents
**Purpose:** Externalize LLM prompts for maintainability and cost reduction
**Related Issues:** #328

---

## Context

**Problem:**
- LLM prompts hardcoded in Python files across codebase
- Non-developers can't tune prompts without code changes
- Prompt changes require redeployment
- Token costs from repeated hardcoded strings
- Difficult to track prompt evolution in version control

**Evidence:**
- 4 tool descriptions hardcoded in `tools.py`
- VoterAgent system prompt hardcoded in `voter_agent.py`
- Help text hardcoded in `llm_trading_assistant.py`
- Market context description hardcoded in `market_context_tool.py`

---

## Decision

**Externalize all LLM prompts to `config/agent_prompts.yaml`**

### Structure

```yaml
# Agent system prompts
agents:
  voter_agent:
    system_prompt: |
      You are a trading agent...
      Configuration: {macd}, {rsi}

  sentiment_v4:
    system_prompt: |
      Analyze news sentiment...

# AutoGen tool descriptions (for LLM tool selection)
tools:
  unified_market_data:
    name: "fetch_unified_market_data"
    description: "Fetch market data using..."

  market_context:
    name: "fetch_market_context_data"
    description: |
      Multi-line description...

# User interface text
interface:
  llm_assistant:
    help_text: |
      Available commands...
```

### Implementation Pattern

**1. Load function in `agent_utils.py`:**
```python
import yaml

def load_agent_config(agent_key: str) -> dict:
    """Load config section from agent_prompts.yaml"""
    with open('config/agent_prompts.yaml', 'r') as f:
        all_configs = yaml.safe_load(f)
    return all_configs.get(agent_key, {})
```

**2. Consumer pattern with fallbacks:**
```python
def _get_tool_description(tool_key: str, fallback: str) -> str:
    try:
        tools_config = load_agent_config("tools")
        return tools_config.get(tool_key, {}).get("description", fallback)
    except Exception:
        return fallback  # Graceful degradation

# Usage
tool = FunctionTool(
    func=fetch_data,
    description=_get_tool_description("market_data", "Fallback description")
)
```

---

## Consequences

### Positive

**Maintainability:**
- ✅ Prompt engineers can edit YAML without Python knowledge
- ✅ Version control tracks prompt evolution separately
- ✅ Easy A/B testing (swap YAML files)
- ✅ Centralized prompt library

**Cost Reduction:**
- ✅ Single YAML load vs repeated string allocations
- ✅ Easier to identify redundant/overlapping prompts
- ✅ Can compress/minimize prompts in one place

**Flexibility:**
- ✅ Environment-specific prompts (dev/prod YAML files)
- ✅ Placeholder support for dynamic content
- ✅ Multi-line prompts with proper formatting

### Negative

**Dependencies:**
- ⚠️ Adds PyYAML dependency (was stdlib-only before)
- **Mitigation:** Fallbacks handle missing PyYAML gracefully

**Runtime Errors:**
- ⚠️ YAML syntax errors break prompt loading
- **Mitigation:** Test suite validates YAML structure
- **Mitigation:** Fallbacks ensure system still functions

**Complexity:**
- ⚠️ Indirection makes code tracing harder
- **Mitigation:** Clear naming convention (`load_agent_config("section")`)
- **Mitigation:** Fallback strings document expected content

### Neutral

**Line Count:**
- Added 341 lines (YAML + tests + loaders)
- Removed 33 lines (hardcoded prompts)
- Net +308 lines (conceptual cleanup, not size reduction)

---

## Implementation Checklist

**Phase 1: Infrastructure** ✅
- [x] Create `config/agent_prompts.yaml` with 3 sections
- [x] Add PyYAML to `requirements.txt`
- [x] Update `agent_utils.py` to load YAML

**Phase 2: Migration** ✅
- [x] Migrate 4 tool descriptions to YAML
- [x] Migrate VoterAgent system prompt
- [x] Migrate LLM assistant help text
- [x] Migrate market context description
- [x] Add fallbacks to all consumers

**Phase 3: Testing** ✅
- [x] Test YAML file exists
- [x] Test all sections load correctly
- [x] Test prompts contain expected placeholders
- [x] Test graceful handling when YAML missing

---

## Rules

### MUST

- **MUST** provide fallback strings for all prompts
- **MUST** test YAML syntax in test suite
- **MUST** document YAML structure in comments
- **MUST** use `yaml.safe_load()` (never `yaml.load()`)

### SHOULD

- **SHOULD** externalize any text seen by LLMs
- **SHOULD** use multi-line strings (`|`) for readability
- **SHOULD** group related prompts in sections
- **SHOULD** include usage examples in YAML comments

### MAY

- **MAY** use environment variables in YAML (e.g., `${API_KEY}`)
- **MAY** split large YAML into multiple files
- **MAY** add validation schema (JSON Schema for YAML)

---

## Examples

### Good: Externalized with Fallback

```python
# tools.py
from utils.agent_utils import load_agent_config

def _get_tool_description(tool_key: str, fallback: str) -> str:
    try:
        tools_config = load_agent_config("tools")
        return tools_config.get(tool_key, {}).get("description", fallback)
    except Exception:
        return fallback

tool = FunctionTool(
    func=fetch_data,
    description=_get_tool_description(
        "market_data",
        "Fetch market data (fallback)"  # Always provide default
    )
)
```

### Bad: Hardcoded Prompt

```python
# Don't do this anymore
tool = FunctionTool(
    func=fetch_data,
    description="Fetch market data using unified cache..."  # ❌ Hardcoded
)
```

### Bad: No Fallback

```python
# Fails if YAML missing
config = load_agent_config("tools")
description = config["market_data"]["description"]  # ❌ KeyError risk
```

---

## Future Extensions

**1. Prompt Versioning:**
```yaml
agents:
  voter_agent:
    v1:
      system_prompt: "Old prompt..."
    v2:  # Current
      system_prompt: "New prompt..."
```

**2. Conditional Prompts:**
```yaml
tools:
  market_data:
    description_short: "Fetch market data"
    description_long: "Fetch market data with..."
```

**3. Multi-language Support:**
```yaml
interface:
  llm_assistant:
    help_text:
      en: "Available commands..."
      es: "Comandos disponibles..."
```

---

## References

- Issue #328: YAML Optimization
- Implementation: `feature/yaml-prompt-management` branch
- Test Suite: `tests/test_yaml_prompts.py`
- ADR 001: Code Organization Standards

---

## Approval

**Accepted by:** Implementation validated via #328
**Date:** 2025-11-10
**Rationale:** Separates concerns, improves maintainability, reduces token costs
