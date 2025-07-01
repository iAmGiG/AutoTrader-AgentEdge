"""Output Manager for organized test results and LLM reasoning capture.

This module provides functionality to:
1. Create organized directory structures for test outputs
2. Save LLM reasoning and analysis
3. Generate individual run reports
4. Extract best analysis examples
"""

import os
import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


class OutputManager:
    """Manages organized output structure for backtest results and LLM analysis."""

    def __init__(self, base_dir: str = ".cache/backtests"):
        """Initialize OutputManager with base directory."""
        self.base_dir = Path(base_dir)
        self.current_run_id = None
        self.current_run_dir = None

    def create_run_directory(self, symbol: str, start_date: str, end_date: str) -> Path:
        """Create organized directory structure for a backtest run.

        Structure:
        .cache/backtests/
        ├── runs/
        │   └── SYMBOL_STARTDATE_ENDDATE_TIMESTAMP/
        │       ├── data/
        │       │   ├── trades.csv
        │       │   ├── equity.csv
        │       │   └── metrics.csv
        │       ├── analysis/
        │       │   ├── daily_reasoning/
        │       │   │   ├── 2023-01-01.json
        │       │   │   └── ...
        │       │   ├── agent_responses/
        │       │   │   ├── sentiment/
        │       │   │   ├── technical/
        │       │   │   └── risk/
        │       │   └── best_insights.json
        │       ├── reports/
        │       │   ├── executive_summary.md
        │       │   ├── detailed_analysis.md
        │       │   └── trade_journal.md
        │       └── metadata.json
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"{symbol}_{start_date}_{end_date}_{timestamp}"
        self.current_run_id = run_id

        # Create main run directory
        run_dir = self.base_dir / "runs" / run_id
        self.current_run_dir = run_dir

        # Create subdirectories
        dirs = [
            run_dir / "data",
            run_dir / "analysis" / "daily_reasoning",
            run_dir / "analysis" / "agent_responses" / "sentiment",
            run_dir / "analysis" / "agent_responses" / "technical",
            run_dir / "analysis" / "agent_responses" / "risk",
            run_dir / "analysis" / "agent_responses" / "strategy",
            run_dir / "reports",
            run_dir / "visualizations"
        ]

        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Create metadata file
        metadata = {
            "run_id": run_id,
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "timestamp": timestamp,
            "created_at": datetime.now().isoformat(),
            "status": "in_progress"
        }

        self.save_json(run_dir / "metadata.json", metadata)

        return run_dir

    def save_llm_reasoning(self, date: str, agent_type: str, reasoning: Dict[str, Any]) -> None:
        """Save LLM reasoning for a specific date and agent.

        Args:
            date: Trading date
            agent_type: Type of agent (sentiment, technical, risk, strategy)
            reasoning: Dict containing LLM response and analysis
        """
        if not self.current_run_dir:
            raise ValueError(
                "No active run directory. Call create_run_directory first.")

        # Save to daily reasoning file
        daily_file = self.current_run_dir / "analysis" / \
            "daily_reasoning" / f"{date}.json"

        # Load existing daily data or create new
        if daily_file.exists():
            daily_data = self.load_json(daily_file)
        else:
            daily_data = {
                "date": date,
                "agents": {},
                "coordinator_summary": None,
                "trading_decision": None
            }

        # Add agent reasoning
        daily_data["agents"][agent_type] = {
            "timestamp": datetime.now().isoformat(),
            "reasoning": reasoning,
            "tools_called": reasoning.get("tools_called", []),
            "data_sources": reasoning.get("data_sources", [])
        }

        self.save_json(daily_file, daily_data)

        # Also save to agent-specific directory
        agent_file = (self.current_run_dir / "analysis" / "agent_responses" /
                      agent_type / f"{date}.json")
        self.save_json(agent_file, reasoning)

    def save_coordinator_analysis(self, date: str, analysis: Dict[str, Any]) -> None:
        """Save coordinator's aggregated analysis for a date."""
        if not self.current_run_dir:
            raise ValueError(
                "No active run directory. Call create_run_directory first.")

        daily_file = self.current_run_dir / "analysis" / \
            "daily_reasoning" / f"{date}.json"

        if daily_file.exists():
            daily_data = self.load_json(daily_file)
        else:
            daily_data = {"date": date, "agents": {}}

        daily_data["coordinator_summary"] = analysis
        self.save_json(daily_file, daily_data)

    def save_trading_decision(self, date: str, decision: Dict[str, Any]) -> None:
        """Save trading decision with reasoning."""
        if not self.current_run_dir:
            raise ValueError(
                "No active run directory. Call create_run_directory first.")

        daily_file = self.current_run_dir / "analysis" / \
            "daily_reasoning" / f"{date}.json"

        if daily_file.exists():
            daily_data = self.load_json(daily_file)
        else:
            daily_data = {"date": date, "agents": {}}

        daily_data["trading_decision"] = decision
        self.save_json(daily_file, daily_data)

    def extract_best_insights(self) -> Dict[str, List[Dict]]:
        """Extract best LLM insights from all daily analyses."""
        if not self.current_run_dir:
            raise ValueError("No active run directory.")

        best_insights = {
            "sentiment_analysis": [],
            "technical_patterns": [],
            "risk_assessments": [],
            "market_narratives": [],
            "trading_rationale": []
        }

        # Scan all daily files
        daily_dir = self.current_run_dir / "analysis" / "daily_reasoning"

        for daily_file in sorted(daily_dir.glob("*.json")):
            daily_data = self.load_json(daily_file)
            date = daily_data.get("date", daily_file.stem)

            # Extract notable insights based on criteria
            # (This is a placeholder - actual implementation would use scoring)

            # Check sentiment insights
            if "sentiment" in daily_data.get("agents", {}):
                sentiment = daily_data["agents"]["sentiment"]
                if sentiment.get("reasoning", {}).get("confidence", 0) > 0.8:
                    best_insights["sentiment_analysis"].append({
                        "date": date,
                        "insight": sentiment["reasoning"],
                        "score": sentiment["reasoning"].get("score", 0)
                    })

            # Check for interesting technical patterns
            if "technical" in daily_data.get("agents", {}):
                technical = daily_data["agents"]["technical"]
                if "pattern_detected" in technical.get("reasoning", {}):
                    best_insights["technical_patterns"].append({
                        "date": date,
                        "pattern": technical["reasoning"]["pattern_detected"],
                        "significance": technical["reasoning"].get("significance", "medium")
                    })

            # Check trading decisions
            if daily_data.get("trading_decision"):
                decision = daily_data["trading_decision"]
                if decision.get("action") in ["BUY", "SELL"]:
                    best_insights["trading_rationale"].append({
                        "date": date,
                        "action": decision["action"],
                        "reasoning": decision.get("reasoning", ""),
                        "confidence": decision.get("confidence", 0)
                    })

        # Save best insights
        insights_file = self.current_run_dir / "analysis" / "best_insights.json"
        self.save_json(insights_file, best_insights)

        return best_insights

    def generate_executive_summary(self, metrics: Dict[str, Any]) -> str:
        """Generate executive summary of backtest results."""
        if not self.current_run_dir:
            raise ValueError("No active run directory.")

        metadata = self.load_json(self.current_run_dir / "metadata.json")
        best_insights = self.extract_best_insights()

        summary = f"""# Executive Summary: {metadata['symbol']} Backtest

**Period**: {metadata['start_date']} to {metadata['end_date']}  
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Performance Overview

- **Total Return**: {metrics.get('total_return', 0):.2f}%
- **Sharpe Ratio**: {metrics.get('sharpe_ratio', 0):.2f}
- **Max Drawdown**: {metrics.get('max_drawdown', 0):.2f}%
- **Win Rate**: {metrics.get('win_rate', 0):.2f}%

## Key Insights

### Top Sentiment Findings
"""

        # Add top 3 sentiment insights
        for insight in best_insights["sentiment_analysis"][:3]:
            summary += f"\n- **{insight['date']}**: Score {insight['insight'].get('score', 0):.2f} - "
            summary += f"{insight['insight'].get('summary', 'Strong sentiment detected')}\n"

        summary += "\n### Notable Technical Patterns\n"

        # Add technical patterns
        for pattern in best_insights["technical_patterns"][:3]:
            summary += f"\n- **{pattern['date']}**: {pattern['pattern']} "
            summary += f"(Significance: {pattern['significance']})\n"

        summary += "\n### Trading Decisions\n"
        summary += f"\nTotal Trades: {len(best_insights['trading_rationale'])}\n"

        # Add example trades
        for trade in best_insights["trading_rationale"][:5]:
            summary += f"\n- **{trade['date']}**: {trade['action']} - {trade['reasoning'][:100]}...\n"

        # Save summary
        summary_file = self.current_run_dir / "reports" / "executive_summary.md"
        summary_file.write_text(summary)

        return summary

    def save_json(self, filepath: Path, data: Dict) -> None:
        """Save data as JSON with pretty formatting."""
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    def load_json(self, filepath: Path) -> Dict:
        """Load JSON data from file."""
        with open(filepath, 'r') as f:
            return json.load(f)

    def get_run_directory(self) -> Optional[Path]:
        """Get current run directory."""
        return self.current_run_dir

    def finalize_run(self, status: str = "completed") -> None:
        """Finalize the run by updating metadata."""
        if not self.current_run_dir:
            return

        metadata_file = self.current_run_dir / "metadata.json"
        metadata = self.load_json(metadata_file)
        metadata["status"] = status
        metadata["completed_at"] = datetime.now().isoformat()
        self.save_json(metadata_file, metadata)


# Legacy compatibility functions
def create_output_directory(symbol: str, start_date: str, end_date: str) -> Path:
    """Create organized output directory (legacy compatibility)."""
    manager = OutputManager()
    return manager.create_run_directory(symbol, start_date, end_date)


def save_llm_reasoning(date: str, agent_type: str, reasoning: Dict) -> None:
    """Save LLM reasoning (legacy compatibility)."""
    # This would need to be integrated with the actual backtest script
    # to maintain the OutputManager instance
    pass
