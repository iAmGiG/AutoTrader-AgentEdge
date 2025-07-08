#!/usr/bin/env python3
"""Minimal test to verify strategy comparison works."""
from src.agents.strategy_agent_v2 import StrategyAgent as StrategyAgentV2
from src.agents.strategy_agent import StrategyAgent as StrategyAgentV1
import sys
import os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))


# Test data with known MACD < 0 recovery
test_signals = {
    'ok': True,
    'sentiment': {'score': 0.0},  # Neutral sentiment
    'technical': {
        'macd_today': -0.5,
        'macd_yest': -1.0,  # Was negative, now improving
        'signal_today': -0.6,
        'signal_yest': -0.8
    }
}

print("Testing strategy comparison with MACD recovery scenario:")
print(
    f"MACD: {test_signals['technical']['macd_yest']} → {test_signals['technical']['macd_today']}")
print(f"Sentiment: {test_signals['sentiment']['score']}")
print()

# Test V1
v1 = StrategyAgentV1()
v1_decision = v1.decide_trade(
    test_signals, price=100.0, trade_date="2024-01-01")
print(
    f"V1 Decision: {v1_decision['action']} - Reason: {v1_decision.get('reason', 'No reason')}")
print(
    f"   V1 sees - MACD_y: {test_signals['technical'].get('macd_yest')}, MACD_t: {test_signals['technical'].get('macd_today')}, Sentiment: {test_signals['sentiment']['score']}")

# Test V2
v2 = StrategyAgentV2()
v2_decision = v2.decide_trade(
    test_signals, price=100.0, trade_date="2024-01-01")
print(
    f"V2 Decision: {v2_decision['action']} - {v2_decision.get('reasoning', 'No reasoning')}")

print("\n✅ Key Difference:")
if v1_decision['action'] != v2_decision['action']:
    print(f"   V1 blocked the trade due to sentiment > 0 requirement")
    print(f"   V2 allowed the trade with sentiment >= 0 requirement")
else:
    print(f"   Both strategies made the same decision in this case")
