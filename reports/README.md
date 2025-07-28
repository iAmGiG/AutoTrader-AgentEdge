# Reports Structure (Post-Issue #134)

**Branch**: LLMEnhancedTrading  
**Milestone**: Post-Obfuscation Validation Era

## Folder Structure

```
reports/
├── validation/      # LLM validation and obfuscation test results
├── analysis/        # Market and strategy analysis reports  
├── sessions/        # Work session summaries
│   └── YYYY/       # Organized by year
├── deprecated/     # Pre-134 reports (not in repo)
└── README.md       # This file
```

## Naming Convention

All reports follow: `title_yy_mm_dd.ext`

- **lowercase** throughout
- **2-3 word** descriptive title
- **yy_mm_dd** date format
- Include **branch name** in report metadata
- Include **issue numbers** when relevant

## Report Types

### Validation Reports
- Obfuscation test results
- LLM performance validation
- Data leakage assessments

### Analysis Reports  
- Market performance analysis
- Strategy comparison results
- Cached data insights

### Session Reports
- Daily work summaries
- Milestone completions
- Architecture changes

## Important Notes

- Issue #134 marks the introduction of obfuscation validation
- All pre-134 reports moved to deprecated/ (gitignored)
- New reports must include validation considerations
- Branch tracking is critical due to rapid iteration
