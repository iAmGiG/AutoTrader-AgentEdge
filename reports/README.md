# Reports Structure (V0-V4 Framework)

**Branch**: ToolArchChange  
**Framework**: V0-V4 Sentiment Analysis Comparison Study

## Folder Structure

```
reports/
├── v0_v4/           # V0-V4 comparison results and analysis
│   ├── quarterly/  # AAPL quarterly test results
│   └── analysis/   # Statistical comparisons between versions
├── sessions/        # Work session summaries
│   └── TEMPLATE.md # Template for session reports
├── technical/       # Technical implementation reports
├── validation/      # Testing and validation results
└── README.md       # This file
```

## Naming Convention

All reports follow: `title_yy_mm_dd.ext`

- **lowercase** throughout
- **2-3 word** descriptive title
- **yy_mm_dd** date format
- Include **version** (V0-V4) when relevant
- Include **issue numbers** for traceability

## Report Types

### V0-V4 Analysis Reports

- Quarterly performance comparisons
- Sentiment approach effectiveness
- Statistical significance testing
- Trade frequency analysis

### Technical Reports  

- Implementation details for each version
- Architecture decisions
- Tool integration documentation

### Validation Reports

- Date obfuscation testing (V4)
- Performance metrics validation
- Data integrity checks

## Important Notes

- Issues #181-190 define the V0-V4 implementation roadmap
- Focus on gradual LLM introduction demonstration
- All legacy reports archived to deprecated/ (gitignored)
- Quarterly testing periods: AAPL 2024 Q1-Q4, 2025 Q1
