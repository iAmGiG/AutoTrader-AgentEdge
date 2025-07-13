#!/usr/bin/env python3
"""Generate consolidated report from multiple backtest runs.

Usage:
    python generate_consolidated_report.py [output_dir]
    
This script scans all backtest runs and creates a comprehensive
consolidated report with comparisons and visualizations.
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.report_generator import ReportGenerator, generate_visualization_script
import argparse
from datetime import datetime


def find_all_runs(base_dir: Path) -> list:
    """Find all completed backtest runs."""
    runs_dir = base_dir / "runs"
    if not runs_dir.exists():
        return []

    completed_runs = []
    for run_dir in runs_dir.iterdir():
        if run_dir.is_dir():
            metadata_path = run_dir / "metadata.json"
            if metadata_path.exists():
                # Check if run completed
                import json
                with open(metadata_path) as f:
                    metadata = json.load(f)
                if metadata.get('status') == 'completed':
                    completed_runs.append(run_dir)

    return sorted(completed_runs)


def main():
    parser = argparse.ArgumentParser(description='Generate consolidated backtest report')
    parser.add_argument('output_dir', nargs='?', default='.cache/backtests/consolidated',
                        help='Output directory for consolidated report')
    parser.add_argument('--base-dir', default='.cache/backtests',
                        help='Base directory containing backtest runs')
    parser.add_argument('--last-n', type=int, default=None,
                        help='Only include last N runs')

    args = parser.parse_args()

    # Find all completed runs
    base_dir = Path(args.base_dir)
    all_runs = find_all_runs(base_dir)

    if not all_runs:
        print("No completed backtest runs found!")
        return

    print(f"Found {len(all_runs)} completed runs")

    # Limit to last N if specified
    if args.last_n:
        all_runs = all_runs[-args.last_n:]
        print(f"Using last {len(all_runs)} runs")

    # Create output directory
    output_dir = Path(args.output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = output_dir / f"report_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate consolidated report
    print("\n📊 Generating consolidated report...")
    report_gen = ReportGenerator()

    # Main consolidated report
    report_path = output_dir / "consolidated_report.md"
    report_gen.create_consolidated_report(all_runs, report_path)

    # Extract best examples across all runs
    print("\n🏆 Extracting best examples across all runs...")
    all_examples = {
        'sentiment_analysis': [],
        'technical_analysis': [],
        'decision_reasoning': [],
        'risk_assessment': [],
        'market_synthesis': []
    }

    for run_dir in all_runs:
        examples = report_gen.extract_llm_examples(run_dir, num_examples=3)
        for category in all_examples:
            all_examples[category].extend(examples.get(category, []))

    # Sort and limit to top examples
    for category in all_examples:
        all_examples[category] = sorted(
            all_examples[category],
            key=lambda x: x.get('quality_score', x.get('confidence', 0)),
            reverse=True
        )[:10]

    # Save best examples
    import json
    examples_path = output_dir / "best_examples_all_runs.json"
    with open(examples_path, 'w') as f:
        json.dump(all_examples, f, indent=2, default=str)
    print(f"✅ Best examples saved to: {examples_path}")

    # Create examples showcase report
    showcase_report = create_examples_showcase(all_examples)
    showcase_path = output_dir / "llm_intelligence_showcase.md"
    showcase_path.write_text(showcase_report)
    print(f"✅ Intelligence showcase saved to: {showcase_path}")

    # Generate visualization script
    viz_script_path = output_dir / "visualize_results.py"
    viz_script_path.write_text(generate_visualization_script())
    print(f"✅ Visualization script saved to: {viz_script_path}")

    print(f"\n🎯 Consolidated report complete!")
    print(f"📁 Output directory: {output_dir}")
    print("\nGenerated files:")
    print("  - consolidated_report.md      : Performance comparison across all runs")
    print("  - llm_intelligence_showcase.md: Best examples of AI analysis")
    print("  - best_examples_all_runs.json : Raw data of best examples")
    print("  - consolidated_metrics.csv    : Metrics data for further analysis")
    print("  - visualize_results.py        : Script to generate charts")

    # Try to generate visualizations if matplotlib is available
    try:
        import matplotlib
        print("\n📈 Attempting to generate visualizations...")
        metrics_csv = output_dir / "consolidated_metrics.csv"
        if metrics_csv.exists():
            import subprocess
            result = subprocess.run([sys.executable, str(viz_script_path),
                                     str(metrics_csv), str(output_dir)],
                                    capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Visualizations generated successfully!")
            else:
                print(f"⚠️  Visualization generation failed: {result.stderr}")
    except ImportError:
        print("\n⚠️  Matplotlib not installed - skipping visualizations")
        print("   Install with: pip install matplotlib seaborn")


def create_examples_showcase(all_examples: dict) -> str:
    """Create a showcase report highlighting AI intelligence."""
    report = f"""# Multi-Agent System Intelligence Showcase
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This document showcases the advanced analytical capabilities of the RH2MAS Multi-Agent Trading System,
demonstrating how AI agents work together to make intelligent trading decisions.

## 🧠 Sentiment Analysis Excellence

The Sentiment Agent demonstrates sophisticated understanding of market news and events:

"""

    # Add top sentiment examples
    for i, example in enumerate(all_examples.get('sentiment_analysis', [])[:3], 1):
        report += f"""### Example {i}: {example.get('date', 'N/A')}
**Analysis**: {example.get('analysis', 'N/A')}

**Confidence**: {example.get('confidence', 0):.2%} | **Sentiment Score**: {example.get('score', 0):.2f}

---

"""

    report += """## 📊 Technical Analysis Mastery

The Technical Agent identifies complex patterns and market dynamics:

"""

    # Add top technical examples
    for i, example in enumerate(all_examples.get('technical_analysis', [])[:3], 1):
        report += f"""### Example {i}: {example.get('date', 'N/A')}
**Analysis**: {example.get('analysis', 'N/A')}

**Pattern Identified**: {example.get('pattern', 'N/A')}

---

"""

    report += """## 🎯 Intelligent Trading Decisions

The Strategy Agent synthesizes multiple inputs to make well-reasoned trading decisions:

"""

    # Add top decision examples
    for i, example in enumerate(all_examples.get('decision_reasoning', [])[:3], 1):
        report += f"""### Example {i}: {example.get('date', 'N/A')} - {example.get('action', 'N/A')}
**Reasoning**: {example.get('reasoning', 'N/A')}

**Confidence**: {example.get('confidence', 0):.2%}

---

"""

    report += """## 🔄 Market Synthesis

The Coordinator Agent demonstrates the power of multi-agent collaboration:

"""

    # Add synthesis examples
    for i, example in enumerate(all_examples.get('market_synthesis', [])[:2], 1):
        report += f"""### Example {i}: {example.get('date', 'N/A')}
**Synthesis**: {example.get('synthesis', 'N/A')}

---

"""

    report += """## 💡 Key Advantages Demonstrated

1. **Nuanced Understanding**: The system goes beyond simple keyword matching to understand context and implications
2. **Multi-Factor Analysis**: Seamlessly integrates sentiment, technical, and fundamental data
3. **Adaptive Reasoning**: Adjusts analysis based on market conditions and data availability
4. **Consistent Logic**: Maintains coherent decision-making framework across different scenarios
5. **Risk Awareness**: Incorporates risk considerations into every decision

## 🚀 Implementation Benefits

- **Scalability**: Can analyze multiple assets simultaneously
- **Speed**: Processes information faster than human analysts
- **Consistency**: No emotional bias or fatigue
- **Auditability**: Every decision is logged with clear reasoning
- **Continuous Learning**: System improves with more data

---
*This showcase demonstrates the advanced capabilities of AI-driven financial analysis*
"""

    return report


if __name__ == "__main__":
    main()
