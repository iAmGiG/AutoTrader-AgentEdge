#!/usr/bin/env python3
"""
Report Renaming Script - Standardize report filenames

Format: lowercase_title_yy_mm_dd.md
"""

import os
import re
from pathlib import Path
from datetime import datetime

# Mapping of old filenames to new standardized names
RENAME_MAP = {
    # Advisor Executive Reports
    "advisor/executive/2025_07_08_progress_summary.md": "advisor/executive/progress_summary_25_07_08.md",
    "advisor/executive/advisor_findings_summary.md": "advisor/executive/findings_summary_25_07_14.md",
    "advisor/executive/advisor_presentation_executive_summary.md": "advisor/executive/executive_summary_25_07_14.md",
    "advisor/executive/advisor_report_20250711.md": "advisor/executive/advisor_report_25_07_11.md",
    
    # Advisor Market Analysis Reports
    "advisor/market_analysis/existing_data_report_20250713_120339/market_conditions_analysis.md": 
        "advisor/market_analysis/existing_data_report_20250713_120339/market_analysis_25_07_13.md",
    "advisor/market_analysis/report_20250713_120046/market_conditions_performance_report.md": 
        "advisor/market_analysis/report_20250713_120046/market_performance_25_07_13.md",
    
    # Advisor Presentations
    "advisor/presentations/advisor_presentation_ai_showcase.md": "advisor/presentations/ai_showcase_25_07_14.md",
    
    # Advisor Technical Reports
    "advisor/technical/advisor_presentation_technical_appendix.md": "advisor/technical/technical_appendix_25_07_14.md",
    "advisor/technical/technical_improvements_20250711.md": "advisor/technical/improvements_report_25_07_11.md",
    
    # Session Reports
    "sessions/2025/backtesting_session_summary_20250708.md": "sessions/2025/backtest_summary_25_07_08.md",
    "sessions/2025/session_report_20250701.md": "sessions/2025/session_report_25_07_01.md",
    "sessions/2025/REPOSITORY_CLEANUP_SUMMARY.md": "sessions/2025/cleanup_summary_25_07_28.md",
    "sessions/2025/SESSION_COMPLETION_SUMMARY_2025-07-28.md": "sessions/2025/completion_summary_25_07_28.md",
    
    # Technical Reports (root level)
    "technical/api_fallback_and_strategy_v2_summary.md": "technical/api_fallback_25_07_14.md",
    "technical/status_summary_sentiment_tech_agents.md": "technical/agent_status_25_07_14.md",
    "technical/strategy_v2_comparison_summary.md": "technical/strategy_comparison_25_07_14.md",
    "technical/CACHED_BACKTEST_ANALYSIS.md": "technical/cached_analysis_25_07_28.md",
    "technical/COMPREHENSIVE_MAG7_ANALYSIS.md": "technical/mag7_analysis_25_07_28.md",
}

# Also need to handle the janky folder names
FOLDER_RENAME_MAP = {
    "advisor/market_analysis/existing_data_report_20250713_120339": "advisor/market_analysis/data_report_25_07_13",
    "advisor/market_analysis/report_20250713_120046": "advisor/market_analysis/performance_report_25_07_13",
}

def rename_reports(dry_run=True):
    """Rename all reports to standardized format."""
    reports_dir = Path("reports")
    
    print(f"{'DRY RUN' if dry_run else 'EXECUTING'} Report Renaming")
    print("=" * 60)
    
    # First rename folders
    if not dry_run:
        for old_folder, new_folder in FOLDER_RENAME_MAP.items():
            old_path = reports_dir / old_folder
            new_path = reports_dir / new_folder
            if old_path.exists():
                print(f"Renaming folder: {old_folder} -> {new_folder}")
                old_path.rename(new_path)
                # Update the file rename map to use new folder paths
                for key in list(RENAME_MAP.keys()):
                    if old_folder in key:
                        new_key = key.replace(old_folder, new_folder)
                        RENAME_MAP[new_key] = RENAME_MAP.pop(key).replace(old_folder, new_folder)
    
    # Then rename files
    for old_name, new_name in RENAME_MAP.items():
        old_path = reports_dir / old_name
        new_path = reports_dir / new_name
        
        if old_path.exists():
            print(f"Rename: {old_name}")
            print(f"    -> {new_name}")
            if not dry_run:
                new_path.parent.mkdir(parents=True, exist_ok=True)
                old_path.rename(new_path)
        else:
            print(f"SKIP (not found): {old_name}")
        print()
    
    # Handle JSON files in market analysis folders
    json_files = list((reports_dir / "advisor/market_analysis").rglob("*.json"))
    for json_file in json_files:
        if "condition_summaries.json" in str(json_file):
            new_name = json_file.parent / "condition_summary_25_07_13.json"
        elif "market_conditions_results.json" in str(json_file):
            new_name = json_file.parent / "market_results_25_07_13.json"
        else:
            continue
            
        if json_file != new_name:
            print(f"Rename: {json_file.relative_to(reports_dir)}")
            print(f"    -> {new_name.relative_to(reports_dir)}")
            if not dry_run:
                json_file.rename(new_name)
            print()

if __name__ == "__main__":
    import sys
    
    # Default to dry run unless --execute is passed
    dry_run = "--execute" not in sys.argv
    
    rename_reports(dry_run=dry_run)
    
    if dry_run:
        print("\nThis was a DRY RUN. To execute, run:")
        print("    python rename_reports.py --execute")