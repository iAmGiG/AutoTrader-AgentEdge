#!/usr/bin/env python3
"""Reorganize documentation structure for better navigation and clarity."""
import shutil
from pathlib import Path


def create_directory_structure(base_path):
    """Create the new directory structure."""
    dirs = [
        # Docs subdirectories
        "docs/architecture/diagrams",
        "docs/implementation/agents",
        "docs/implementation/tools",
        "docs/implementation/strategies",

        # Reports subdirectories
        "reports/advisor/executive",
        "reports/advisor/presentations",
        "reports/advisor/technical",
        "reports/sessions/2025",
        "reports/technical",
    ]

    for dir_path in dirs:
        full_path = base_path / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created: {dir_path}")


def move_files(base_path):
    """Move files to their new locations."""
    moves = [
        # From docs to new locations
        ("docs/RH2MAS_technical_UML.png", "docs/architecture/diagrams/"),
        ("docs/sentiment_agent.md", "docs/implementation/agents/"),
        ("docs/README_SENTIMENT_AGENT.md", "docs/implementation/agents/"),
        ("docs/sentiment_agent_changes.md", "docs/implementation/agents/"),
        ("docs/sentiment_agent_future_work.md", "docs/implementation/agents/"),
        ("docs/sentiment_agent_refactoring.md", "docs/implementation/agents/"),
        ("docs/sentiment feature testing.md", "docs/implementation/agents/"),
        ("docs/indicator_library.md", "docs/implementation/tools/"),
        ("docs/web_scraping_corporate_actions.md", "docs/implementation/tools/"),
        ("docs/strategy_v2_documentation.md", "docs/implementation/strategies/"),
        ("docs/status_summary_sentiment_tech_agents.md", "reports/technical/"),

        # From reports to new locations
        ("reports/advisor_presentation_executive_summary.md",
         "reports/advisor/executive/"),
        ("reports/advisor_findings_summary.md", "reports/advisor/executive/"),
        ("reports/advisor_presentation_ai_showcase.md",
         "reports/advisor/presentations/"),
        ("reports/advisor_presentation_technical_appendix.md",
         "reports/advisor/technical/"),
        ("reports/session_report_20250701.md", "reports/sessions/2025/"),
        ("reports/backtesting_session_summary_20250708.md", "reports/sessions/2025/"),
        ("reports/api_fallback_and_strategy_v2_summary.md", "reports/technical/"),
        ("reports/strategy_v2_comparison_summary.md", "reports/technical/"),
    ]

    for src, dst in moves:
        src_path = base_path / src
        dst_path = base_path / dst

        if src_path.exists():
            # If destination is a directory, preserve filename
            if dst_path.is_dir():
                dst_path = dst_path / src_path.name

            try:
                shutil.move(str(src_path), str(dst_path))
                print(f"✅ Moved: {src} → {dst}")
            except Exception as e:
                print(f"❌ Failed to move {src}: {e}")
        else:
            print(f"⚠️  Not found: {src}")


def move_uml_folder(base_path):
    """Move the entire UML folder to architecture/diagrams."""
    src = base_path / "docs/UML"
    dst = base_path / "docs/architecture/diagrams/UML"

    if src.exists():
        try:
            shutil.move(str(src), str(dst))
            print(f"✅ Moved: docs/UML → docs/architecture/diagrams/UML")
        except Exception as e:
            print(f"❌ Failed to move UML folder: {e}")


def create_readme_files(base_path):
    """Create README files for better navigation."""

    # Docs README
    docs_readme = """# Documentation

This directory contains all technical documentation for the RH2MAS project.

## Structure

- **architecture/** - System design and technical architecture
- **implementation/** - How-to guides and implementation details
  - **agents/** - Agent-specific documentation
  - **tools/** - Tool and indicator documentation
  - **strategies/** - Trading strategy documentation
- **reference/** - External references (AutoGen core reference)
- **research/** - Research notes and framework exploration

## Quick Links

- [System Architecture](architecture/README.md)
- [Sentiment Agent Guide](implementation/agents/sentiment_agent.md)
- [Strategy V2 Documentation](implementation/strategies/strategy_v2_documentation.md)
"""

    # Reports README
    reports_readme = """# Reports

This directory contains all project reports, presentations, and session summaries.

## Structure

- **advisor/** - Advisor-facing presentations and summaries
  - **executive/** - High-level executive summaries
  - **presentations/** - Full presentations
  - **technical/** - Technical appendices
- **sessions/** - Development session reports organized by year
- **technical/** - Technical findings and comparison reports

## Quick Links

- [Latest Executive Summary](advisor/executive/advisor_presentation_executive_summary.md)
- [Strategy V2 Comparison](technical/strategy_v2_comparison_summary.md)
- [API Fallback Analysis](technical/api_fallback_and_strategy_v2_summary.md)
"""

    # Session template
    session_template = """# Session Report Template

**Date**: YYYY-MM-DD  
**Duration**: X hours  
**Focus**: [Primary focus area]

## Objectives
- [ ] Objective 1
- [ ] Objective 2

## Accomplishments
1. 
2. 

## Challenges Encountered
- 

## Next Steps
- 

## Code Changes
- Files modified:
- New files created:
- Tests added:

## Notes
"""

    # Write README files
    (base_path / "docs/README_STRUCTURE.md").write_text(docs_readme)
    (base_path / "reports/README_STRUCTURE.md").write_text(reports_readme)
    (base_path / "reports/sessions/TEMPLATE.md").write_text(session_template)

    print("✅ Created README files for navigation")


def main():
    """Main reorganization function."""
    base_path = Path("/mnt/bst/yxie2/cregan1/RH2MAS")

    print("🔧 Reorganizing documentation structure...\n")

    # Create new directory structure
    create_directory_structure(base_path)

    # Move files to new locations
    print("\n📁 Moving files...")
    move_files(base_path)

    # Move UML folder
    move_uml_folder(base_path)

    # Create README files
    print("\n📝 Creating navigation files...")
    create_readme_files(base_path)

    print("\n✅ Reorganization complete!")
    print("\n📋 Next steps:")
    print("1. Review the new structure")
    print("2. Update any broken links in documentation")
    print("3. Remove empty directories if desired")
    print("4. Consider archiving docs/original_sentiment_agent.py")


if __name__ == "__main__":
    main()
