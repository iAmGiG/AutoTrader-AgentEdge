"""
Generate Simple Uniform Diagrams for Tri-Fold Poster

All diagrams are square (800x800) or double (1600x800) for easy arrangement.
No Graphviz needed - uses matplotlib only.
"""

import os

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

# Colors
GREEN = "#2E7D32"
BLUE = "#1976D2"
RED = "#C62828"
AMBER = "#FFB300"
GRAY = "#757575"
LIGHT_GRAY = "#F5F5F5"


def setup_figure(size=(8, 8), dpi=300):
    """Create a square figure."""
    fig, ax = plt.subplots(figsize=size, dpi=dpi)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    return fig, ax


def add_box(ax, x, y, w, h, text, color, textcolor="white", fontsize=10):
    """Add a rounded box with text."""
    box = FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.1", edgecolor="black", facecolor=color, linewidth=2
    )
    ax.add_patch(box)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        fontweight="bold",
        color=textcolor,
        wrap=True,
    )


def add_arrow(ax, x1, y1, x2, y2, label=""):
    """Add an arrow between boxes."""
    ax.annotate(
        "", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", lw=2, color="black")
    )
    if label:
        mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mid_x + 0.3, mid_y, label, fontsize=8, style="italic")


# ============= DIAGRAM 1: System Architecture (800x800) =============


def generate_architecture():
    fig, ax = setup_figure()

    # Title
    ax.text(5, 9.5, "Production System Architecture", ha="center", fontsize=28, fontweight="bold")

    # Arrows - render BEFORE boxes
    # Data flow: Alpaca -> Cache -> Indicators
    add_arrow(ax, 5, 8.7, 5, 8.3)
    add_arrow(ax, 3, 7.5, 2.5, 6.8)
    add_arrow(ax, 7, 7.5, 7.5, 6.8)
    # Indicators -> VoterAgent
    add_arrow(ax, 2, 6, 3, 5.3)
    add_arrow(ax, 8, 6, 7, 5.3)
    # VoterAgent -> CLI -> Human
    add_arrow(ax, 5, 4.5, 5, 3.8)
    add_arrow(ax, 5, 3.75, 5, 2.7)

    # Top - Data Source
    add_box(ax, 2, 8.75, 6, 0.5, "Alpaca Markets API", GRAY, fontsize=18)

    # Cache Layer
    add_box(ax, 2, 7.5, 6, 0.7, "SQLite Cache Layer", "#9C27B0", fontsize=18)

    # Technical Indicators (side by side)
    add_box(ax, 0.5, 6, 4, 0.7, "MACD Calculator\n(13/34/8)", BLUE, fontsize=16)
    add_box(ax, 5.5, 6, 4, 0.7, "RSI Calculator\n(14/30/70)", BLUE, fontsize=16)

    # VoterAgent - Main Decision Engine
    add_box(ax, 1.5, 4.5, 7, 0.8, "VoterAgent: Consensus Voting Engine", GREEN, fontsize=14)

    # Agent Logic Detail
    add_box(ax, 0.5, 3.55, 3, 0.4, "Signal\nGeneration", GREEN, "white", fontsize=12)
    add_box(ax, 3.7, 3.55, 2.6, 0.4, "Confidence\nScoring", GREEN, "white", fontsize=12)
    add_box(ax, 6.5, 3.55, 3, 0.4, "Position\nSizing", GREEN, "white", fontsize=12)

    # Interactive CLI
    add_box(ax, 2, 2.25, 6, 0.5, "Interactive CLI", AMBER, "black", fontsize=16)

    # Human Decision Layer
    add_box(
        ax,
        2,
        1,
        6,
        0.7,
        "Human Approval Gate\n0.856 Sharpe Performance",
        AMBER,
        "black",
        fontsize=16,
    )

    output_dir = os.path.join(os.path.dirname(__file__), "figures")
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(
        os.path.join(output_dir, "1_architecture.png"),
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close()
    print("Generated: 1_architecture.png (800x800)")


# ============= DIAGRAM 2: Voting Logic (800x800) =============


def generate_voting():
    fig, ax = setup_figure()

    ax.text(5, 9.5, "MACD + RSI Voting Logic", ha="center", fontsize=28, fontweight="bold")

    # Input
    add_box(ax, 3.5, 8, 3, 0.7, "Market Data", GRAY, fontsize=16)

    # Indicators
    add_box(ax, 1, 6.5, 3.5, 0.8, "MACD\n(13/34/8)", BLUE, fontsize=18)
    add_box(ax, 5.5, 6.5, 3.5, 0.8, "RSI\n(14/30/70)", BLUE, fontsize=18)

    # Signals
    add_box(ax, 0.5, 5.25, 2, 0.6, "BUY", "#C8E6C9", "black", fontsize=16)
    add_box(ax, 2.7, 5.25, 2, 0.6, "SELL", "#FFCDD2", "black", fontsize=16)
    add_box(ax, 5.3, 5.25, 2, 0.6, "BUY", "#C8E6C9", "black", fontsize=16)
    add_box(ax, 7.5, 5.25, 2, 0.6, "HOLD", "#E0E0E0", "black", fontsize=16)

    # Voting
    add_box(ax, 2.5, 3, 5, 0.8, "Consensus Voting", "#6A1B9A", fontsize=18)

    # Outcomes
    add_box(ax, 0.5, 1, 2.8, 0.7, "STRONG\n100%", GREEN, fontsize=14)
    add_box(ax, 3.6, 1, 2.8, 0.7, "WEAK\n50%", "#66BB6A", fontsize=14)
    add_box(ax, 6.7, 1, 2.8, 0.7, "HOLD\n0%", GRAY, fontsize=14)

    # Arrows - adjusted Y positions to avoid text overlap
    add_arrow(ax, 5, 8, 2.75, 7.3)
    add_arrow(ax, 5, 8, 7.25, 7.3)
    add_arrow(ax, 1.5, 5.25, 5, 3.8)
    add_arrow(ax, 3.7, 5.25, 5, 3.8)
    add_arrow(ax, 6.3, 5.25, 5, 3.8)
    add_arrow(ax, 8.5, 5.25, 5, 3.8)
    add_arrow(ax, 3.5, 3, 1.9, 1.7)
    add_arrow(ax, 5, 3, 5, 1.7)
    add_arrow(ax, 6.5, 3, 8.1, 1.7)

    ax.text(
        5,
        0.3,
        "Both Agree → Strong | One Signals → Weak | Conflict → Hold",
        ha="center",
        fontsize=18,
        style="italic",
    )

    output_dir = os.path.join(os.path.dirname(__file__), "figures")
    plt.savefig(
        os.path.join(output_dir, "2_voting_logic.png"),
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close()
    print("Generated: 2_voting_logic.png (800x800)")


# ============= DIAGRAM 3: Performance Comparison (1600x800 - DOUBLE WIDTH) =============


def generate_performance_simple():
    fig, ax = setup_figure(size=(16, 8))
    ax.set_xlim(0, 20)

    ax.text(
        10,
        9.5,
        "Validated Performance: Voting vs Single Indicator",
        ha="center",
        fontsize=14,
        fontweight="bold",
    )

    # Table headers - more compact spacing with color
    metrics = ["Sharpe Ratio", "Win Rate", "Max Drawdown", "Volatility"]
    macd_vals = ["0.841", "31.9%", "-10.58%", "16.58%"]
    voting_vals = ["0.856", "51.4%", "-10.10%", "15.30%"]

    y_start = 8.2

    # Header row with amber color for metric column
    add_box(ax, 2, y_start - 0.4, 4, 0.8, "Metric", AMBER, "black", fontsize=11)
    add_box(ax, 7, y_start - 0.4, 5, 0.8, "MACD Only", BLUE, fontsize=11)
    add_box(ax, 13, y_start - 0.4, 5, 0.8, "Voting (MACD+RSI)", GREEN, fontsize=11)

    # Draw table - tighter spacing
    for i, (metric, macd, voting) in enumerate(zip(metrics, macd_vals, voting_vals)):
        y = y_start - 1.3 - (i * 1.3)

        # Metric name with amber color
        add_box(ax, 2, y - 0.4, 4, 0.8, metric, AMBER, "black", fontsize=10)

        # MACD value
        add_box(ax, 7, y - 0.4, 5, 0.8, macd, BLUE, fontsize=10)

        # Voting value (better)
        add_box(ax, 13, y - 0.4, 5, 0.8, voting + " [BEST]", GREEN, fontsize=10)

    # Bottom note - in a box for emphasis
    add_box(
        ax,
        4,
        1.5,
        12,
        0.9,
        "Extended Testing: 11.2% better in volatile markets",
        GREEN,
        fontsize=11,
    )

    output_dir = os.path.join(os.path.dirname(__file__), "figures")
    plt.savefig(
        os.path.join(output_dir, "3_performance.png"),
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close()
    print("Generated: 3_performance.png (1600x800 - DOUBLE WIDTH)")


# ============= DIAGRAM 4: Human-in-Loop Workflow (800x800) =============


def generate_workflow():
    fig, ax = setup_figure()

    ax.text(5, 9, "Human-in-Loop Workflow", ha="center", fontsize=28, fontweight="bold")

    # Step 1
    add_box(ax, 2, 7.5, 6, 0.8, '1. User: "analyze AAPL"', GRAY, fontsize=18)

    # Step 2
    add_box(ax, 2, 6, 6, 0.8, "2. Fetch Market Data", BLUE, fontsize=18)

    # Step 3
    add_box(ax, 2, 4.5, 6, 0.8, "3. Calculate MACD+RSI", BLUE, fontsize=18)

    # Step 4
    add_box(ax, 2, 3, 6, 0.8, "4. Generate Signal \n& Reasoning", BLUE, fontsize=18)

    # Step 5 - HUMAN APPROVAL
    add_box(ax, 2, 1.5, 6, 1, '5. HUMAN APPROVES/REJECTS\n"Execute? [yes/no]"', AMBER, fontsize=16)

    # Bottom tagline in box for visibility (amber on white is hard to see)
    add_box(ax, 2.5, 0.2, 5, 0.6, "AI Proposes, Human Decides", AMBER, "black", fontsize=14)

    # Arrows - render last to avoid overlap
    add_arrow(ax, 5, 7.5, 5, 6.8)
    add_arrow(ax, 5, 6, 5, 5.3)
    add_arrow(ax, 5, 4.5, 5, 3.8)
    add_arrow(ax, 5, 3, 5, 2.5)

    output_dir = os.path.join(os.path.dirname(__file__), "figures")
    plt.savefig(
        os.path.join(output_dir, "4_workflow.png"), dpi=300, bbox_inches="tight", facecolor="white"
    )
    plt.close()
    print("Generated: 4_workflow.png (800x800)")


# ============= DIAGRAM 5: Key Metrics Badge (800x800) =============


def generate_metrics():
    fig, ax = setup_figure()

    ax.text(5, 9.2, "Production-Validated Results", ha="center", fontsize=18, fontweight="bold")

    # Big metrics - larger font for convention center visibility (28+ recommended)
    add_box(ax, 1, 7, 8, 1.4, "Sharpe Ratio: 0.856", GREEN, fontsize=22)
    add_box(ax, 1, 5, 8, 1.4, "Win Rate: 51.4%", GREEN, fontsize=22)
    add_box(ax, 1, 3, 8, 1.4, "Max Drawdown: -10.10%", GREEN, fontsize=22)

    # Context - larger font for visibility
    ax.text(5, 1.8, "Extended Period: 36.6% Return (2024-2025)", ha="center", fontsize=14)
    ax.text(
        5,
        1.0,
        "11.2% Better in Volatile Markets",
        ha="center",
        fontsize=16,
        color=GREEN,
        fontweight="bold",
    )

    output_dir = os.path.join(os.path.dirname(__file__), "figures")
    plt.savefig(
        os.path.join(output_dir, "5_metrics.png"), dpi=300, bbox_inches="tight", facecolor="white"
    )
    plt.close()
    print("Generated: 5_metrics.png (800x800)")


# ============= DIAGRAM 6: Technical Stack (800x800) =============


def generate_stack():
    fig, ax = setup_figure()

    ax.text(5, 9.5, "Technology Stack", ha="center", fontsize=14, fontweight="bold")

    # Stack layers
    add_box(ax, 1.5, 7.5, 7, 0.9, "Microsoft AutoGen Framework", BLUE, fontsize=10)
    add_box(ax, 1.5, 6.2, 7, 0.9, "Python 3.10+ | OpenAI", BLUE, fontsize=10)
    add_box(ax, 1.5, 4.9, 7, 0.9, "Alpaca Markets (Trading)", "#F57C00", fontsize=10)
    add_box(ax, 1.5, 3.6, 7, 0.9, "Polygon.io (Market Data)", "#F57C00", fontsize=10)
    add_box(ax, 1.5, 2.3, 7, 0.9, "SQLite Cache (90%+ hit rate)", "#9C27B0", fontsize=10)

    ax.text(
        5,
        1,
        "Production-Ready • Open Source (AGPL-3.0)",
        ha="center",
        fontsize=10,
        fontweight="bold",
    )

    output_dir = os.path.join(os.path.dirname(__file__), "figures")
    plt.savefig(
        os.path.join(output_dir, "6_stack.png"), dpi=300, bbox_inches="tight", facecolor="white"
    )
    plt.close()
    print("Generated: 6_stack.png (800x800)")


# ============= MAIN =============


def main():
    print("=" * 70)
    print("Generating Simple Uniform Diagrams for Tri-Fold Poster")
    print("All diagrams: 800x800 (square) or 1600x800 (double width)")
    print("300 DPI for print quality")
    print("=" * 70)
    print()

    generate_architecture()
    # generate_voting()
    # generate_performance_simple()
    # generate_workflow()
    # generate_metrics()
    # generate_stack()  # Skipping - using icons in Tools Utilized section instead

    print()
    print("=" * 70)
    print("All diagrams saved to: docs/presentations/figures/")
    print("=" * 70)
    print()
    print("Files for CENTER COLUMN of tri-fold:")
    print("  1_architecture.png      (800x800) - System overview")
    # print("  2_voting_logic.png      (800x800) - Core algorithm")
    # print("  3_performance.png       (1600x800 WIDE) - Results table")
    # print("  4_workflow.png          (800x800) - Human-in-loop steps")
    # print("  5_metrics.png           (800x800) - Key numbers")
    # print("  6_stack.png             (800x800) - Technology")
    # print()
    # print("Layout suggestion:")
    # print("  Row 1: [1_architecture] [2_voting_logic]")
    # print("  Row 2: [3_performance - SPANS FULL WIDTH]")
    # print("  Row 3: [4_workflow] [5_metrics]")
    # print("  Row 4: [6_stack] [YOUR CONSOLE OUTPUT]")
    # print()


if __name__ == "__main__":
    main()
