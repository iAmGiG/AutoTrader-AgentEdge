"""
Generate a single consolidated conclusions/key findings visual for the poster
"""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import os

# Colors
GREEN = '#2E7D32'
BLUE = '#1976D2'
AMBER = '#FFB300'
PURPLE = '#6A1B9A'


def add_box(ax, x, y, w, h, text, color, textcolor='white', fontsize=10):
    """Add a rounded box with text."""
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                         edgecolor='black', facecolor=color, linewidth=2)
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, text, ha='center', va='center',
            fontsize=fontsize, fontweight='bold', color=textcolor,
            wrap=True)


def generate_conclusions():
    """Generate a single consolidated visual for conclusions."""
    fig, ax = plt.subplots(figsize=(8, 8), dpi=300)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')

    # Title
    ax.text(5, 9, 'Key Findings: Human-in-Loop Trading', ha='center',
            fontsize=28, fontweight='bold')

    # Three main achievements - larger boxes
    add_box(ax, 0.45, 7.2, 9.25, 1.2,
            'Better Risk-Adjusted Returns\nSharpe Ratio: 0.856 | Win Rate: 51.4%',
            GREEN, fontsize=18)

    add_box(ax, 0.45, 5.55, 9.25, 1.2,
            'Maintained Interpretability\nTransparent \nMACD+RSI Signals | Full Reasoning',
            BLUE, fontsize=18)

    add_box(ax, 0.45, 3.85, 9.25, 1.2,
            'Preserved Trader Control\nHuman Approval Required \n AI Proposes, Human Decides',
            AMBER, 'black', fontsize=18)

    # Core insight box
    add_box(ax, 0.45, 2.2, 9.25, 1.2,
            'Augmentation > Automation\nProduction-Ready System \n11.2% Better in Volatile Markets',
            PURPLE, fontsize=18)

    # Bottom metrics strip
    ax.text(5, 0.5, 'Validated: 36.6% Return (2024-2025) | Max Drawdown: -10.10% | Open Source (AGPL-3.0)',
            ha='center', fontsize=16, style='italic')

    # Save
    output_dir = os.path.join(os.path.dirname(__file__), 'figures')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'key_findings.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

    print("=" * 70)
    print("Key Findings Visual Generated!")
    print("=" * 70)
    print(f"Saved to: {output_path}")
    print("Size: 800x800 @ 300 DPI")
    print()
    print("This consolidates:")
    print("  - Better risk-adjusted returns (Sharpe 0.856)")
    print("  - Maintained interpretability (transparent signals)")
    print("  - Preserved trader control (human approval)")
    print("  - Core insight: Augmentation > Automation")
    print("=" * 70)


if __name__ == '__main__':
    generate_conclusions()
