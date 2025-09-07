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

### System Architecture Intent
1. **Human decides**: "I want to trade AAPL based on external signal"
2. **System manages**: Entry timing, position sizing, exit strategy
3. **Tools provide**: Risk management, regime awareness, execution optimization

### Development Priorities
1. **Trade Management Tools** - Help execute human decisions better
2. **Risk Controls** - Protect capital during trades
3. **Execution Optimization** - Better entries/exits for human-initiated trades
4. **NOT**: Autonomous signal generation

### For GitHub Issues
When creating new issues, remember:
- Compare performance to savings rates (2-5%), not buy-and-hold
- Focus on tools that help manage human-initiated trades
- Prioritize risk management over signal generation
- This is a trade management system, not an autonomous bot

---
*This context should guide all future development decisions.*