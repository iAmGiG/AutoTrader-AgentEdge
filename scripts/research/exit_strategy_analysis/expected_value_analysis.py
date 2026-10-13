#!/usr/bin/env python3
"""
Expected Value Analysis
Verify the mathematical concerns about negative expected value.
"""


def analyze_expected_value(win_rate, take_profit, stop_loss):
    """Calculate expected value per trade."""
    expected_value = win_rate * take_profit + (1 - win_rate) * (-stop_loss)
    return expected_value


def calculate_kelly_criterion(win_rate, win_loss_ratio):
    """Calculate Kelly Criterion (optimal bet size)."""
    # Kelly % = W - (1-W)/R
    # where W = win probability, R = win/loss ratio
    if win_loss_ratio == 0:
        return 0
    return win_rate - (1 - win_rate) / win_loss_ratio


def main():
    print("=" * 60)
    print("EXPECTED VALUE ANALYSIS")
    print("=" * 60)

    configurations = [
        (0.566, 0.06, 0.08, "Conservative (56.6% WR, 6% TP, 8% SL)"),
        (0.667, 0.06, 0.08, "Actual Test (66.7% WR, 6% TP, 8% SL)"),
        (0.50, 0.08, 0.05, "Balanced (50% WR, 8% TP, 5% SL)"),
        (0.333, 0.10, 0.03, "Aggressive (33.3% WR, 10% TP, 3% SL)"),
    ]

    print("\n" + "-" * 60)
    print(f"{'Configuration':<40} {'EV/Trade':<10} {'Kelly %':<10} {'Status'}")
    print("-" * 60)

    for win_rate, tp, sl, name in configurations:
        ev = analyze_expected_value(win_rate, tp, sl)
        status = "✅ Positive" if ev > 0 else "❌ Negative"

        # Calculate Kelly
        win_loss_ratio = tp / sl
        kelly = calculate_kelly_criterion(win_rate, win_loss_ratio)
        kelly_str = f"{kelly * 100:>6.2f}%" if kelly > 0 else "   0.00%"

        print(f"{name:<40} {ev * 100:>6.2f}%    {kelly_str:<10} {status}")

        if ev < 0:
            print("  ⚠️  WARNING: Negative Expectancy. Kelly suggests betting 0%.")
        print()

    print("=" * 60)
    print("KEY FINDINGS:")
    print("=" * 60)
    print("1. You were RIGHT - at 56.6% win rate with 6%/8%, EV is NEGATIVE!")
    print("2. The actual test showed 66.7% win rate, making EV positive")
    print("3. Win rate is CRITICAL with these parameters")
    print("4. Need >57.1% win rate for positive EV with 6% TP / 8% SL")
    print("5. Need >38.5% win rate for positive EV with 8% TP / 5% SL")
    print("6. Kelly Criterion shows optimal position size (Full Kelly is aggressive!)")

    # Calculate breakeven win rates
    print("\n" + "=" * 60)
    print("BREAKEVEN WIN RATES:")
    print("=" * 60)

    configs = [
        (0.06, 0.08, "6% TP / 8% SL"),
        (0.08, 0.05, "8% TP / 5% SL"),
        (0.10, 0.03, "10% TP / 3% SL"),
    ]

    for tp, sl, name in configs:
        breakeven = sl / (tp + sl)
        print(f"{name}: Need >{breakeven:.1%} win rate for positive EV")
        print(f"  Formula: {sl:.1%} / ({tp:.1%} + {sl:.1%}) = {breakeven:.1%}")

    print("\n" + "=" * 60)
    print("CONCLUSION:")
    print("=" * 60)
    print("The 0.373 Sharpe ratio from earlier tests was misleading!")
    print("With realistic win rates, the Conservative system is borderline.")
    print("The Balanced (8%/5%) system has better expected value.")
    print("=" * 60)


if __name__ == "__main__":
    main()
