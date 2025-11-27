"""
Generate Multi-Agent Architecture Diagram for AutoTrader-AgentEdge

This script creates a professional Graphviz diagram showing the multi-agent
system architecture with VoterAgent, Scanner, Risk, Executor, and Orchestrator.
"""

import os

import graphviz


def generate_architecture_diagram():
    """Generate the multi-agent architecture diagram."""

    # Create a new directed graph
    dot = graphviz.Digraph(
        name="AutoTrader Architecture",
        comment="Multi-Agent Trading System Architecture",
        format="png",
    )

    # Graph attributes for professional appearance
    dot.attr(rankdir="TB", size="12,18", dpi="300", ranksep="1.0", nodesep="0.8")
    dot.attr(
        "node",
        shape="box",
        style="rounded,filled",
        fontname="Arial",
        fontsize="11",
        margin="0.3,0.2",
    )
    dot.attr("edge", fontname="Arial", fontsize="10", color="#424242")

    # Color scheme
    PRODUCTION = "#2E7D32"  # Green - Production ready
    DEVELOPMENT = "#1976D2"  # Blue - In development
    INFRASTRUCTURE = "#757575"  # Gray - Infrastructure
    DATA_SOURCE = "#F57C00"  # Orange - External data

    # Top level - External Data Sources
    with dot.subgraph(name="cluster_data") as c:
        c.attr(label="External Data Sources", style="filled", color="lightgrey")
        c.node(
            "alpaca",
            "Alpaca Markets\n(Trading & Market Data)",
            fillcolor=DATA_SOURCE,
            fontcolor="white",
        )
        c.node("polygon", "Polygon.io\n(Real-time Data)", fillcolor=DATA_SOURCE, fontcolor="white")
        c.node("alpha", "Alpha Vantage\n(Fallback Data)", fillcolor=DATA_SOURCE, fontcolor="white")

    # Core Infrastructure Layer
    with dot.subgraph(name="cluster_infra") as c:
        c.attr(label="Infrastructure Layer", style="filled", color="lightgrey")
        c.node(
            "cache",
            "SQLite Cache\n(8-10x Performance)",
            fillcolor=INFRASTRUCTURE,
            fontcolor="white",
        )
        c.node(
            "config",
            "YAML Configuration\n(Dynamic Parameters)",
            fillcolor=INFRASTRUCTURE,
            fontcolor="white",
        )
        c.node(
            "tools",
            "AutoGen Tools\n(Market Data & Indicators)",
            fillcolor=INFRASTRUCTURE,
            fontcolor="white",
        )

    # AutoGen Agent Layer
    with dot.subgraph(name="cluster_agents") as c:
        c.attr(
            label="AgentEdge Multi-Agent System",
            style="filled,bold",
            color="#1976D2",
            fontsize="14",
            margin="20",
        )

        # Production-ready agent
        c.node(
            "voter",
            "VoterAgent ✓\nMACD+RSI Voting\n(0.856 Sharpe)",
            fillcolor=PRODUCTION,
            fontcolor="white",
            penwidth="3",
        )

        # Agents in development
        c.node(
            "scanner",
            "ScannerAgent\nMarket Scanning\n(In Development)",
            fillcolor=DEVELOPMENT,
            fontcolor="white",
            style="rounded,filled,dashed",
        )
        c.node(
            "risk",
            "RiskAgent\nPosition Sizing\n(In Development)",
            fillcolor=DEVELOPMENT,
            fontcolor="white",
            style="rounded,filled,dashed",
        )
        c.node(
            "executor",
            "ExecutorAgent\nTrade Execution\n(In Development)",
            fillcolor=DEVELOPMENT,
            fontcolor="white",
            style="rounded,filled,dashed",
        )

    # Orchestration Layer
    dot.node(
        "orchestrator",
        "Trading Orchestrator\n(Multi-Agent Coordination)",
        shape="hexagon",
        fillcolor="#6A1B9A",
        fontcolor="white",
        fontsize="12",
        penwidth="2",
    )

    # Human Interface Layer - positioned lower with more space
    with dot.subgraph(name="cluster_ui") as c:
        c.attr(rank="sink")  # Force to bottom
        c.node(
            "cli",
            "Interactive CLI\n(Approve → Auto-Manage)",
            shape="rectangle",
            fillcolor="#C62828",
            fontcolor="white",
            fontsize="12",
            penwidth="2",
        )
        c.node(
            "approval",
            "Human Approval Gate\n(Initial Trade Decision)",
            shape="diamond",
            fillcolor="#F57C00",
            fontcolor="white",
            fontsize="11",
            penwidth="2",
        )

    # Connections - Data Sources to Infrastructure
    dot.edge("alpaca", "cache", label="market data")
    dot.edge("polygon", "cache", label="real-time")
    dot.edge("alpha", "cache", label="fallback")
    dot.edge("cache", "tools", label="cached data")
    dot.edge("config", "tools", label="parameters")

    # Connections - Infrastructure to Agents
    dot.edge("tools", "voter", label="MACD+RSI\ncalculations")
    dot.edge("tools", "scanner", label="screening\ndata", style="dashed")
    dot.edge("tools", "risk", label="portfolio\nmetrics", style="dashed")
    dot.edge("tools", "executor", label="order\nmanagement", style="dashed")

    # Connections - Agents to Orchestrator
    dot.edge("scanner", "orchestrator", label="opportunities", style="dashed")
    dot.edge("voter", "orchestrator", label="signals")
    dot.edge("risk", "orchestrator", label="approvals", style="dashed")
    dot.edge("executor", "orchestrator", label="confirmations", style="dashed")

    # Connection flow: Orchestrator → CLI → Approval → Orchestrator
    dot.edge("orchestrator", "cli", label="trade proposal")
    dot.edge("cli", "approval", label="present to user")
    dot.edge("approval", "orchestrator", label="approved:\nauto-manage", color="#2E7D32")
    dot.edge("approval", "cli", label="rejected", color="#C62828", style="dashed")

    # Add legend
    with dot.subgraph(name="cluster_legend") as c:
        c.attr(label="Legend", style="filled", color="white")
        c.node(
            "leg_prod",
            "✓ Production Ready",
            fillcolor=PRODUCTION,
            fontcolor="white",
            shape="box",
            style="rounded,filled",
        )
        c.node(
            "leg_dev",
            "In Development",
            fillcolor=DEVELOPMENT,
            fontcolor="white",
            shape="box",
            style="rounded,filled,dashed",
        )
        c.attr(rank="same")

    # Output directory
    output_dir = os.path.join(os.path.dirname(__file__), "figures")
    os.makedirs(output_dir, exist_ok=True)

    # Render the diagram
    output_path = os.path.join(output_dir, "architecture")
    dot.render(output_path, cleanup=True)

    print(f"Architecture diagram generated: {output_path}.png")
    return output_path + ".png"


if __name__ == "__main__":
    generate_architecture_diagram()
