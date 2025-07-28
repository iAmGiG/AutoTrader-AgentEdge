#!/usr/bin/env python3
"""
Issue #140: Clean Report Organization Post-134

This script moves all pre-134 reports to deprecated folder and 
establishes new clean structure for post-validation era.
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

# Post-134 reports to keep (from today 2025-07-28)
POST_134_REPORTS = [
    "sessions/2025/cleanup_summary_25_07_28.md",
    "sessions/2025/completion_summary_25_07_28.md", 
    "technical/cached_analysis_25_07_28.md",
    "technical/mag7_analysis_25_07_28.md"
]

def migrate_reports(dry_run=True):
    """Migrate pre-134 reports to deprecated folder."""
    reports_dir = Path("reports")
    deprecated_dir = reports_dir / "deprecated"
    
    print(f"{'DRY RUN' if dry_run else 'EXECUTING'} Issue #140: Report Migration")
    print("=" * 60)
    print(f"Branch: LLMEnhancedTrading")
    print(f"Milestone: Post-Issue #134 (Obfuscation Validation)")
    print("=" * 60)
    
    # Find all report files
    all_reports = []
    for ext in ["*.md", "*.json"]:
        all_reports.extend(reports_dir.rglob(ext))
    
    # Filter out README files and templates
    all_reports = [f for f in all_reports if not (
        f.name == "README_STRUCTURE.md" or 
        f.name == "README.md" or
        f.name == "TEMPLATE.md" or
        "deprecated" in str(f)
    )]
    
    # Separate pre and post 134 reports
    pre_134_reports = []
    post_134_reports = []
    
    for report in all_reports:
        relative_path = report.relative_to(reports_dir)
        if str(relative_path) in POST_134_REPORTS:
            post_134_reports.append(report)
        else:
            pre_134_reports.append(report)
    
    print(f"\nFound {len(pre_134_reports)} pre-134 reports to deprecate")
    print(f"Found {len(post_134_reports)} post-134 reports to keep\n")
    
    # Move pre-134 reports to deprecated
    print("DEPRECATING Pre-134 Reports:")
    print("-" * 60)
    for report in sorted(pre_134_reports):
        relative_path = report.relative_to(reports_dir)
        new_path = deprecated_dir / relative_path
        
        print(f"  {relative_path}")
        if not dry_run:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(report), str(new_path))
    
    print(f"\nKEEPING Post-134 Reports:")
    print("-" * 60)
    for report in sorted(post_134_reports):
        relative_path = report.relative_to(reports_dir)
        print(f"  ✓ {relative_path}")
    
    # Create new clean structure
    if not dry_run:
        print("\nCreating new clean folder structure...")
        
        # Ensure clean directories exist
        (reports_dir / "validation").mkdir(exist_ok=True)
        (reports_dir / "analysis").mkdir(exist_ok=True) 
        (reports_dir / "sessions").mkdir(exist_ok=True)
        
        # Create .gitignore for deprecated folder
        gitignore_content = """# Deprecated reports - not tracked
deprecated/
"""
        with open(reports_dir / ".gitignore", "w") as f:
            f.write(gitignore_content)
            
        print("✓ Created clean folder structure")
        print("✓ Added .gitignore for deprecated folder")

def create_new_readme():
    """Create new README for clean report structure."""
    readme_content = """# Reports Structure (Post-Issue #134)

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
"""
    
    with open("reports/README.md", "w") as f:
        f.write(readme_content)
    print("\n✓ Created new README.md")

if __name__ == "__main__":
    import sys
    
    dry_run = "--execute" not in sys.argv
    
    migrate_reports(dry_run=dry_run)
    
    if not dry_run:
        create_new_readme()
    
    if dry_run:
        print("\nThis was a DRY RUN. To execute migration:")
        print("    python migrate_reports_issue_140.py --execute")