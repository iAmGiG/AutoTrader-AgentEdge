# AutoTrader-AgentEdge Demo Speaker Notes

## 30-Second Lightning Demo

### Script

"AutoTrader-AgentEdge: An AI-powered automated trading system using Microsoft AutoGen's multi-agent framework. Watch as I interact with it through natural language."

### Terminal Actions (20 seconds)

```bash
# Launch CLI
python main.py

# Show natural language understanding
> check my portfolio

# Show order management with grouped display
> check open orders

# Exit
> exit
```

### Closing (5 seconds)

"Multi-agent coordination, real-time market data, and intelligent decision-making - all through conversational AI."

---

## 1-2 Minute Standard Demo

### Opening (15 seconds)

"AutoTrader-AgentEdge is a production-ready automated trading platform built on Microsoft AutoGen's multi-agent architecture. It combines validated MACD+RSI voting strategies with intelligent AI agents for market analysis, risk management, and trade execution. Let me show you how it works."

### Terminal Demo (60-75 seconds)

#### 1. Launch & Welcome (10 sec)

```bash
python main.py
```

**Say:** "The system initializes with Alpaca paper trading integration. Notice the natural language interface - no complex commands needed."

#### 2. Portfolio Status (15 sec)

```bash
> what's my portfolio looking like?
```

**Say:** "Natural language understanding. The system shows real-time positions with P&L, entry prices, and targets. Notice the clean, scannable format."

#### 3. Grouped Order Display (20 sec)

```bash
> check open orders
```

**Say:** "Orders grouped by ticker with visual hierarchy. The asterisk indicates stop-loss orders tracked locally - Alpaca's API hides these 'held' bracket legs. System maintains a local state copy for complete visibility. See the PT and SL labels - profit targets and stop-loss protection."

#### 4. Trading Intelligence (Optional, 15 sec)

```bash
> analyze SPY
```

**Say:** "Behind the scenes: VoterAgent with MACD+RSI consensus. 0.856 Sharpe ratio validated across 2024-2025. Multi-agent system coordinates scanning, risk, and execution."

#### 5. Scheduler System (Optional, 10 sec)

```bash
> /scheduler
> status
> exit
```

**Say:** "Automated daily routines - morning pre-market analysis at 9:20 AM, evening reconciliation at 3:50 PM Eastern."

### Closing (10 seconds)

"Production-ready system: validated strategies, multi-agent coordination, comprehensive state management, and natural language control. Built with AutoGen, deployed on Alpaca."

---

## Key Talking Points (Choose 2-3 based on audience)

### Technical Audience

- **Multi-Agent Architecture**: Scanner, Voter, Risk, Executor agents coordinate via AutoGen
- **Validated Strategy**: 0.856 Sharpe, 36.6% return over 2024-2025 extended testing
- **State Management**: Local state tracking overcomes Alpaca API limitations (held orders)
- **Fibonacci MACD**: 13/34/8 parameters optimized across tech stocks

### Business Audience

- **Automated Trading**: Schedule routines, set-and-forget operation
- **Risk Management**: Stop-loss protection, position sizing, profit targets
- **Natural Language**: Conversational interface, no coding required
- **Paper Trading First**: Test strategies safely before live capital

### Academic/Research Audience

- **Framework**: Microsoft AutoGen multi-agent coordination
- **Validation**: Rigorous backtesting across multiple market regimes
- **Technical Indicators**: MACD + RSI voting consensus outperforms single indicators
- **Market Insight**: Better performance in volatile markets (-14.6% gap) vs bull markets (-25.8% gap)

---

## Pro Tips

### Visual Impact

- **Use dark terminal theme** - better contrast for projectors
- **Increase font size** - `Ctrl +` or terminal settings
- **Clear screen between commands** - keeps focus on current output
- **Practice timing** - know exactly which commands to run

### What to Avoid

- Don't show errors or debugging
- Don't get stuck in configuration menus
- Don't try to place real orders during demo
- Don't show API keys or sensitive data

### Backup Plan

- Have screenshots ready if terminal acts up
- Pre-record terminal session as fallback
- Know your data - memorize 2-3 key metrics (Sharpe ratio, return %)

### Questions You'll Get

**"Is this live trading?"**
→ "Paper trading mode - real API, simulated capital. Flip one config flag for live."

**"What's the Sharpe ratio?"**
→ "0.856 validated over 2024-2025 period with 36.6% returns."

**"What happens if it fails?"**
→ "Multi-layer safety: stop-loss orders, position limits, error handling, and daily reconciliation reports."

**"Can I customize strategies?"**
→ "Yes - modular architecture. Swap agents, adjust parameters, or add new indicators through config files."

---

## Suggested Variations

### For PhD/Academic Setting

- Emphasize validation methodology
- Show the voting consensus mechanism
- Discuss regime-based performance differences
- Reference archived experiments (docs/archived/experiments/)

### For Hackathon/Demo Day

- Lead with live terminal interaction
- Show the grouped order display (most visual impact)
- Emphasize natural language interface
- Quick mention of AutoGen framework

### For Technical Interview

- Discuss architecture decisions (why AutoGen?)
- Explain local state workaround for Alpaca API limitation
- Show code structure briefly (`src/autogen_agents/`)
- Discuss testing strategy and validation process
