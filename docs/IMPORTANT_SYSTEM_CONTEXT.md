# Important System Context for Development

## System Purpose - Human-Guided Trading

**This is NOT an autonomous trading bot.**

### Core Concept
- The system manages trades requested by a human operator
- Human has external tools and network of traders for trade ideas
- System's role: Execute and manage trades with proper risk controls
- Goal: Beat savings account returns (2-5% APY), not buy-and-hold

### Correct Performance Comparison
❌ **WRONG**: Compare to buy-and-hold returns  
✅ **RIGHT**: Compare to savings account returns (2-5% APY)

### Example Success Metrics
- Savings account: 4% APY
- Our system: 8-12% annual return = SUCCESS
- Risk-adjusted returns matter more than raw returns

### System Architecture Intent (Simplified September 7, 2025)
1. **Human decides**: "I want to trade based on external signals"
2. **System provides**: Simple MACD+RSI voting for entry timing
3. **System exits**: Fixed percentages (+8%/-5%) or momentum reversals
4. **NO COMPLEXITY**: No Fibonacci, no percentiles, no ensembles

### Development Priorities (Reality Check)
1. **Keep It Simple** - Complex systems failed (17.7% win rate, -1.260 Sharpe)
2. **Use What Works** - MACD+RSI voting = 0.856 Sharpe, 51.4% win rate
3. **Fixed Exit Rules** - No adaptive/complex exit strategies
4. **Test Reality** - Validate on 2024-2025 data with simple rules only

### For GitHub Issues
When creating new issues, remember:
- Compare performance to savings rates (2-5%), not buy-and-hold
- Focus on tools that help manage human-initiated trades
- Prioritize risk management over signal generation
- This is a trade management system, not an autonomous bot

---
*This context should guide all future development decisions.*