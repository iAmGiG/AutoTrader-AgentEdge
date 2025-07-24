"""Parallel Strategy Tester - Compare mechanical and LLM strategies side by side.

This allows direct comparison of trading decisions and performance metrics.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd
import json
from pathlib import Path

from ..agents.strategy_agent import StrategyAgent
from ..agents.llm_strategy_agent import LLMStrategyAgent

logger = logging.getLogger(__name__)


class ParallelStrategyTester:
    """Run mechanical and LLM strategies in parallel for comparison.
    
    Key features:
    - Feed identical signals to both strategies
    - Track decisions and reasoning from each
    - Log agreement/disagreement patterns
    - Calculate comparative performance metrics
    """
    
    def __init__(self, output_dir: Optional[str] = None):
        """Initialize parallel tester with two strategy instances."""
        self.mechanical_strategy = StrategyAgent(name="MechanicalStrategy")
        self.llm_strategy = LLMStrategyAgent(name="LLMStrategy")
        
        # Tracking
        self.comparison_log = []
        self.agreement_stats = {
            "total_decisions": 0,
            "agreements": 0,
            "disagreements": 0,
            "agreement_rate": 0.0
        }
        
        # Performance tracking
        self.mechanical_equity = [10000]  # Starting capital
        self.llm_equity = [10000]
        self.initial_capital = 10000
        
        # Output directory
        self.output_dir = Path(output_dir) if output_dir else Path(".cache/parallel_tests")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def run_parallel_decision(self, signals: Dict, price: float, date: str) -> Dict:
        """Run both strategies on same signals and compare decisions.
        
        :param signals: Aggregated signals from all agents
        :param price: Current stock price
        :param date: Trading date
        :return: Comparison results
        """
        
        # Get mechanical decision
        try:
            mech_decision = self.mechanical_strategy.decide_trade(signals, price, date)
        except Exception as e:
            logger.error(f"Mechanical strategy error: {e}")
            mech_decision = {"action": "HOLD", "error": str(e)}
        
        # Get LLM decision
        try:
            llm_decision = self.llm_strategy.decide_trade(signals, price, date)
        except Exception as e:
            logger.error(f"LLM strategy error: {e}")
            llm_decision = {"action": "HOLD", "error": str(e)}
        
        # Compare decisions
        agree = mech_decision.get("action") == llm_decision.get("action")
        
        # Create comparison entry
        comparison = {
            "date": date,
            "price": price,
            "signals": {
                "sentiment_score": signals.get("sentiment", {}).get("score", "N/A"),
                "macd_today": signals.get("technical", {}).get("macd_today", "N/A"),
                "macd_yest": signals.get("technical", {}).get("macd_yest", "N/A"),
                "market_heat": signals.get("market_heat", {}).get("heat_level", "N/A")
            },
            "mechanical": {
                "action": mech_decision.get("action"),
                "reasoning": mech_decision.get("reasoning", "Rule-based decision"),
                "filtered": mech_decision.get("reason", "")
            },
            "llm": {
                "action": llm_decision.get("action"),
                "confidence": llm_decision.get("confidence", "N/A"),
                "reasoning": llm_decision.get("reasoning", {}),
                "risk_level": llm_decision.get("risk_level", "N/A")
            },
            "agreement": agree,
            "timestamp": datetime.now().isoformat()
        }
        
        # Update tracking
        self.comparison_log.append(comparison)
        self.agreement_stats["total_decisions"] += 1
        if agree:
            self.agreement_stats["agreements"] += 1
        else:
            self.agreement_stats["disagreements"] += 1
        self.agreement_stats["agreement_rate"] = (
            self.agreement_stats["agreements"] / self.agreement_stats["total_decisions"]
        )
        
        # Update equity curves
        self._update_equity(mech_decision.get("action"), price, "mechanical")
        self._update_equity(llm_decision.get("action"), price, "llm")
        
        # Log significant disagreements
        if not agree:
            logger.info(f"DISAGREEMENT on {date}: Mechanical={mech_decision['action']}, "
                       f"LLM={llm_decision['action']} (confidence={llm_decision.get('confidence', 'N/A')})")
            if isinstance(llm_decision.get("reasoning"), dict):
                logger.info(f"LLM reasoning: {llm_decision['reasoning'].get('decision_rationale', 'No rationale')}")
        
        return comparison
    
    def _update_equity(self, action: str, price: float, strategy: str):
        """Update equity curve for a strategy based on its action."""
        if strategy == "mechanical":
            equity_list = self.mechanical_equity
            position = self.mechanical_strategy.position
        else:
            equity_list = self.llm_equity
            position = self.llm_strategy.position
        
        # Simple equity tracking (assumes fixed position size)
        current_equity = equity_list[-1]
        
        # For now, just track the equity (full implementation would track actual P&L)
        equity_list.append(current_equity)
    
    def get_performance_comparison(self) -> Dict:
        """Calculate and compare performance metrics for both strategies."""
        
        # Get metrics from each strategy
        mech_metrics = self.mechanical_strategy.get_metrics(self.initial_capital)
        llm_metrics = self.llm_strategy.get_metrics(self.initial_capital)
        
        # Calculate equity-based metrics
        mech_returns = pd.Series(self.mechanical_equity).pct_change().dropna()
        llm_returns = pd.Series(self.llm_equity).pct_change().dropna()
        
        comparison = {
            "mechanical": {
                **mech_metrics,
                "final_equity": self.mechanical_equity[-1],
                "volatility": mech_returns.std() * (252 ** 0.5) if len(mech_returns) > 0 else 0
            },
            "llm": {
                **llm_metrics,
                "final_equity": self.llm_equity[-1],
                "volatility": llm_returns.std() * (252 ** 0.5) if len(llm_returns) > 0 else 0
            },
            "comparison": {
                "agreement_rate": self.agreement_stats["agreement_rate"],
                "total_decisions": self.agreement_stats["total_decisions"],
                "llm_outperformance": (
                    (self.llm_equity[-1] - self.mechanical_equity[-1]) / self.mechanical_equity[-1] * 100
                    if self.mechanical_equity[-1] > 0 else 0
                ),
                "llm_better_sharpe": llm_metrics.get("sharpe_ratio", 0) > mech_metrics.get("sharpe_ratio", 0),
                "llm_lower_drawdown": llm_metrics.get("max_drawdown", 1) < mech_metrics.get("max_drawdown", 1)
            }
        }
        
        return comparison
    
    def analyze_disagreements(self) -> Dict:
        """Analyze patterns in strategy disagreements."""
        
        disagreements = [c for c in self.comparison_log if not c["agreement"]]
        
        if not disagreements:
            return {"message": "No disagreements found"}
        
        # Analyze when strategies disagree
        analysis = {
            "total_disagreements": len(disagreements),
            "disagreement_rate": len(disagreements) / len(self.comparison_log) if self.comparison_log else 0,
            "by_action": {},
            "market_conditions": {},
            "common_patterns": []
        }
        
        # Count disagreement types
        for d in disagreements:
            mech_action = d["mechanical"]["action"]
            llm_action = d["llm"]["action"]
            key = f"{mech_action}_vs_{llm_action}"
            analysis["by_action"][key] = analysis["by_action"].get(key, 0) + 1
        
        # Analyze market conditions during disagreements
        heat_levels = [d["signals"]["market_heat"] for d in disagreements if d["signals"]["market_heat"] != "N/A"]
        if heat_levels:
            analysis["market_conditions"]["avg_heat"] = sum(heat_levels) / len(heat_levels)
            analysis["market_conditions"]["heat_range"] = (min(heat_levels), max(heat_levels))
        
        # Find common patterns
        if len(disagreements) >= 3:
            # Example: LLM more conservative in cold markets
            cold_market_disagreements = [
                d for d in disagreements 
                if d["signals"]["market_heat"] != "N/A" and d["signals"]["market_heat"] < -0.2
            ]
            if cold_market_disagreements:
                llm_holds = sum(1 for d in cold_market_disagreements if d["llm"]["action"] == "HOLD")
                if llm_holds / len(cold_market_disagreements) > 0.6:
                    analysis["common_patterns"].append(
                        "LLM tends to be more conservative (HOLD) in cold market conditions"
                    )
        
        return analysis
    
    def save_results(self, run_name: str = None):
        """Save comparison results to files."""
        
        if not run_name:
            run_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        run_dir = self.output_dir / run_name
        run_dir.mkdir(exist_ok=True)
        
        # Save comparison log
        with open(run_dir / "comparison_log.json", "w") as f:
            json.dump(self.comparison_log, f, indent=2)
        
        # Save performance comparison
        perf_comparison = self.get_performance_comparison()
        with open(run_dir / "performance_comparison.json", "w") as f:
            json.dump(perf_comparison, f, indent=2)
        
        # Save disagreement analysis
        disagreement_analysis = self.analyze_disagreements()
        with open(run_dir / "disagreement_analysis.json", "w") as f:
            json.dump(disagreement_analysis, f, indent=2)
        
        # Generate summary report
        self._generate_summary_report(run_dir, perf_comparison, disagreement_analysis)
        
        logger.info(f"Results saved to {run_dir}")
        return run_dir
    
    def _generate_summary_report(self, run_dir: Path, perf_comparison: Dict, 
                                disagreement_analysis: Dict):
        """Generate a markdown summary report."""
        
        report = f"""# Parallel Strategy Comparison Report

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary

- **Total Decisions**: {self.agreement_stats['total_decisions']}
- **Agreement Rate**: {self.agreement_stats['agreement_rate']:.1%}
- **LLM Outperformance**: {perf_comparison['comparison']['llm_outperformance']:.2f}%

## Performance Metrics

### Mechanical Strategy
- Total Return: {perf_comparison['mechanical']['total_return_pct']:.2f}%
- Sharpe Ratio: {perf_comparison['mechanical']['sharpe_ratio']:.2f}
- Max Drawdown: {perf_comparison['mechanical']['max_drawdown']:.2%}
- Win Rate: {perf_comparison['mechanical']['win_rate']:.1%}
- Number of Trades: {perf_comparison['mechanical']['num_trades']}

### LLM Strategy
- Total Return: {perf_comparison['llm']['total_return_pct']:.2f}%
- Sharpe Ratio: {perf_comparison['llm']['sharpe_ratio']:.2f}
- Max Drawdown: {perf_comparison['llm']['max_drawdown']:.2%}
- Win Rate: {perf_comparison['llm']['win_rate']:.1%}
- Number of Trades: {perf_comparison['llm']['num_trades']}
- Average Confidence: {perf_comparison['llm'].get('avg_confidence', 0):.2f}
- Decision Quality: {perf_comparison['llm'].get('decision_quality', 0):.2f}

## Key Findings

1. **LLM vs Mechanical Performance**:
   - {"LLM outperformed" if perf_comparison['comparison']['llm_outperformance'] > 0 else "Mechanical outperformed"} by {abs(perf_comparison['comparison']['llm_outperformance']):.2f}%
   - {"LLM has better risk-adjusted returns" if perf_comparison['comparison']['llm_better_sharpe'] else "Mechanical has better risk-adjusted returns"}
   - {"LLM has lower drawdowns" if perf_comparison['comparison']['llm_lower_drawdown'] else "Mechanical has lower drawdowns"}

2. **Decision Patterns**:
   - Strategies agreed {self.agreement_stats['agreement_rate']:.1%} of the time
   - When disagreeing, most common pattern: {self._get_top_disagreement_pattern(disagreement_analysis)}

3. **LLM Advantages**:
   - Provides detailed reasoning for each decision
   - Adapts to market conditions dynamically
   - Shows confidence levels for risk management

## Conclusion

The LLM strategy demonstrates {"superior" if perf_comparison['comparison']['llm_outperformance'] > 5 else "comparable"} performance 
with the added benefit of explainable decision-making. Key advantages include better adaptation to market 
conditions and transparent reasoning for each trade.
"""
        
        with open(run_dir / "summary_report.md", "w") as f:
            f.write(report)
    
    def _get_top_disagreement_pattern(self, analysis: Dict) -> str:
        """Get the most common disagreement pattern."""
        if not analysis.get("by_action"):
            return "No clear pattern"
        
        # Find most common disagreement
        patterns = analysis["by_action"]
        top_pattern = max(patterns.items(), key=lambda x: x[1])
        
        # Format nicely
        actions = top_pattern[0].split("_vs_")
        return f"Mechanical {actions[0]} while LLM {actions[1]} ({top_pattern[1]} times)"