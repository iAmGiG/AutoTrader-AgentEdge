#!/usr/bin/env python3
"""
Compare MACD line vs MACD histogram values to understand the difference.
"""

import sys
sys.path.append(".")

import pandas as pd
import numpy as np
from src.tools.processors.indicator_library import macd

def compare_macd_values():
    """Generate synthetic data and compare MACD line vs histogram."""
    
    # Create trending price data
    dates = pd.date_range(start='2024-01-01', periods=200, freq='D')
    
    # Create a price series with trend and volatility
    trend = np.linspace(100, 120, 200)
    cycle = 5 * np.sin(np.linspace(0, 8 * np.pi, 200))
    noise = np.random.normal(0, 1, 200)
    prices = trend + cycle + noise
    
    df = pd.DataFrame({'Close': prices}, index=dates)
    
    # Calculate MACD
    macd_df = macd(df['Close'])
    
    print("MACD Comparison Analysis")
    print("="*60)
    
    # Statistics
    print("\nMACD Line Statistics:")
    print(f"  Range: {macd_df['MACD_line'].min():.4f} to {macd_df['MACD_line'].max():.4f}")
    print(f"  Mean: {macd_df['MACD_line'].mean():.4f}")
    print(f"  Std Dev: {macd_df['MACD_line'].std():.4f}")
    
    print("\nMACD Histogram Statistics:")
    print(f"  Range: {macd_df['MACD_hist'].min():.4f} to {macd_df['MACD_hist'].max():.4f}")
    print(f"  Mean: {macd_df['MACD_hist'].mean():.4f}")
    print(f"  Std Dev: {macd_df['MACD_hist'].std():.4f}")
    
    # Count crossings
    macd_line = macd_df['MACD_line']
    macd_hist = macd_df['MACD_hist']
    
    # Line crossings (crosses zero)
    line_crossings = 0
    for i in range(1, len(macd_line)):
        if pd.notna(macd_line.iloc[i]) and pd.notna(macd_line.iloc[i-1]):
            if (macd_line.iloc[i] > 0) != (macd_line.iloc[i-1] > 0):
                line_crossings += 1
    
    # Histogram crossings (crosses zero)
    hist_crossings = 0
    for i in range(1, len(macd_hist)):
        if pd.notna(macd_hist.iloc[i]) and pd.notna(macd_hist.iloc[i-1]):
            if (macd_hist.iloc[i] > 0) != (macd_hist.iloc[i-1] > 0):
                hist_crossings += 1
    
    print(f"\nCrossing Analysis:")
    print(f"  MACD Line zero crossings: {line_crossings}")
    print(f"  MACD Histogram zero crossings: {hist_crossings}")
    
    # Show some actual values
    print("\nSample Values (last 10 days):")
    print("Date         MACD Line   MACD Hist   Signal")
    print("-"*50)
    for i in range(-10, 0):
        date = macd_df.index[i].strftime('%Y-%m-%d')
        line_val = macd_df['MACD_line'].iloc[i]
        hist_val = macd_df['MACD_hist'].iloc[i]
        signal_val = macd_df['MACD_signal'].iloc[i]
        print(f"{date}   {line_val:8.4f}   {hist_val:8.4f}   {signal_val:8.4f}")
    
    # Key insight
    print("\n" + "="*60)
    print("KEY INSIGHTS:")
    print("="*60)
    print("1. MACD Line values are typically larger in magnitude")
    print("2. MACD Histogram values are smaller (difference between line and signal)")
    print("3. Histogram crossings are more frequent (more sensitive to momentum changes)")
    print("4. Using histogram with 0.01 threshold is appropriate for catching crossings")
    
    # Trading strategy implications
    print("\nTRADING STRATEGY IMPLICATIONS:")
    print("-"*60)
    print("Entry Signal (Histogram < 0.01 → Histogram > previous):")
    
    # Find example entry signals
    entries = []
    for i in range(1, len(macd_hist)-1):
        if pd.notna(macd_hist.iloc[i]) and pd.notna(macd_hist.iloc[i-1]):
            if macd_hist.iloc[i-1] < 0.01 and macd_hist.iloc[i] > macd_hist.iloc[i-1]:
                entries.append({
                    'date': macd_hist.index[i],
                    'hist_prev': macd_hist.iloc[i-1],
                    'hist_curr': macd_hist.iloc[i],
                    'price': df['Close'].iloc[i]
                })
    
    print(f"\nFound {len(entries)} potential entry signals")
    if entries:
        print("\nFirst 3 entry signals:")
        for i, entry in enumerate(entries[:3]):
            print(f"{i+1}. {entry['date'].strftime('%Y-%m-%d')}: "
                  f"Hist {entry['hist_prev']:.4f} → {entry['hist_curr']:.4f} "
                  f"(Price: ${entry['price']:.2f})")

if __name__ == "__main__":
    compare_macd_values()