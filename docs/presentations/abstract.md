# PhD Presentation Submission Package

## 1A. Intro/Abstract - Concise Version (for poster/quick reference)

**AutoTrader-AgentEdge** challenges the automation-centric paradigm in algorithmic trading. Rather than replacing human traders with black-box AI, we demonstrate that transparent multi-agent consensus combined with human-in-loop approval achieves superior risk-adjusted returns while preserving interpretability.

Our production VoterAgent implements democratic voting between MACD momentum and RSI extremes, generating transparent signals through an interactive CLI. Humans retain final approval on all trades - AI proposes, humans decide.

**Validated Results**: 0.856 Sharpe ratio (vs 0.841 single-indicator), 51.4% win rate, -10.10% max drawdown. Extended testing shows 11.2% better performance in volatile markets.

**Key Insight**: Augmentation outperforms automation. Transparent, interpretable AI builds trust and enables effective human-AI collaboration.

**(~750 characters)**

---

## 1B. Full Abstract (2000 char max - for submission portal)

This work presents AutoTrader-AgentEdge, a human-in-loop trading system that positions AI agents as collaborative partners rather than autonomous replacements. We demonstrate that multi-indicator consensus voting combined with human approval achieves superior risk-adjusted returns while maintaining interpretability and control.

**Core Contribution**: A production-ready VoterAgent implementing democratic voting between MACD momentum and RSI extremes, generating transparent trading signals for human evaluation. Unlike black-box automation, our interactive CLI augments trader expertise through interpretable consensus logic. The human retains final decision authority at all critical junctures.

**Validated Performance**: Empirical validation demonstrates multi-indicator voting superiority over single-indicator automation: Sharpe ratio 0.856 vs 0.841, max drawdown -10.10% vs -10.58%, win rate 51.4% vs 31.9%. Extended testing shows 11.2% better relative performance in volatile markets, validating risk management focus.

**Implementation**: Built on Microsoft AutoGen framework with extensible multi-agent architecture. SQLite caching achieves 8-10x performance improvement. Interactive CLI enables natural language trade discussion with human approval gates. Full Alpaca broker integration enables paper and live trading.

**Key Insight**: Transparent, interpretable methods build trust and enable effective human-AI collaboration. By prioritizing augmentation over automation, we demonstrate that AI serves traders best as a decision support tool that preserves human judgment while systematically reducing errors.

**Implications**: Contributes to augmented trading research - systems designed to enhance rather than replace human expertise. This work validates that human-in-loop architectures can achieve both superior risk-adjusted returns AND maintained trader control, challenging the "automation-at-all-costs" paradigm prevalent in algorithmic trading.

**(1,450 characters)**

---

## 2. Equipment Request

**Requested:**

- Monitor: 27-inch (preferred) or 20-inch
- Keyboard: USB/wireless
- Mouse: USB/wireless
- Power outlet

**Justification:**

Hey, so my project is a human-in-loop trading system - basically the whole point is that AI and humans work together, not AI doing everything alone. You can't really show that on a poster.

Here's what I'm thinking: when someone walks up, they can ask me to analyze any stock they want. I type it in, the system fetches real market data, shows them the MACD and RSI signals, explains why it's recommending buy/sell/hold, then waits for approval. That live interaction - where they pick the stock and see it work in real-time - that's what proves my research actually works.

**Why I need keyboard/mouse:** Without them, I can only show pre-recorded videos, which feels less real and doesn't let me respond to what people are actually curious about. When someone asks "What about Tesla?" I want to just type it in and show them right there.

**Why 27-inch over 20-inch:** Honestly, these sessions usually have a few people (2-5) standing around looking at the same time. 27-inch means everyone can actually read the terminal text from a couple feet back. With 20-inch I'd have to make the font huge and you'd barely see anything on screen at once. 27-inch is just easier for group viewing.

**Setup:** Really quick - under 5 minutes. Just plug in HDMI from my laptop, connect keyboard/mouse, launch the program. System works offline so I don't even need WiFi, though it'd be cool to pull live market data if available.

**Bottom line:** Interactive demo lets people engage with an actual working system, not just read about it. They can test it with stocks they care about and see the human-in-loop part actually happening.

**(1,500 characters)**

---

## 3. Additional Comments

**Presentation Format:** Interactive live demonstration on monitor (not traditional poster)

**Why Interactive?** The research question is: "Can multi-agent consensus with human-in-loop achieve superior risk-adjusted returns while preserving interpretability?"

Interpretability and human collaboration cannot be shown on static posters - they must be experienced. When a visitor asks "How would this analyze Tesla?", I type `analyze TSLA` and the system:

1. Fetches real market data
2. Calculates MACD and RSI
3. Shows transparent reasoning
4. Generates consensus vote
5. Waits for human approval

That 30-second interaction proves the research contribution better than any chart.

**What Visitors Experience:**

- Request any stock symbol for live analysis
- See transparent MACD signals, RSI levels, confidence scoring
- Witness human approval gates (AI proposes, human decides)
- View portfolio management, alerts, validated performance (0.856 Sharpe)

**Engagement:** Natural language interface accessible to all technical backgrounds. Technical researchers can examine architecture/caching. Finance faculty can analyze stocks they trade. Fellow students engage with working system vs theoretical concepts.

**Production System:** Not a prototype - full Alpaca broker integration, validated performance, daily automation, open source. Live demo proves it works as documented.

**Fallback:** If technical issues occur, I have static diagrams and pre-recorded video. However, primary value is live human-in-loop demonstration.

**GitHub:** QR code available for deeper technical access to complete implementation.

**(1,400 characters)**

---

## 4. Day-of Demo Guide

### Setup (5 min)

1. Connect monitor via HDMI
2. Connect keyboard/mouse
3. Set terminal font: 16-18pt
4. Launch: `python main.py`
5. Position monitor for group viewing

### 30-Second Pitch

"AutoTrader-AgentEdge is a human-in-loop trading system. AI analyzes stocks using MACD+RSI consensus and proposes trades, but you maintain final approval. It's augmentation, not automation. Want to see it analyze a stock?"

### Essential Commands

```bash
analyze AAPL          # Most common - stock analysis
show portfolio        # Portfolio view
check my alerts       # Position alerts
/validation          # Performance results
```

### Key Metrics

- Sharpe: 0.856
- Win Rate: 51.4%
- Max DD: -10.10%
- Cache: 8-10x speedup

### Common Questions

**"Is it automated?"** → "No - humans approve every trade. It's decision support."
**"Performance?"** → "0.856 Sharpe, validated in backtesting."
**"Analyze [stock]?"** → Type: `analyze [stock]`

### Engagement Tips

- Ask: "Do you trade any stocks?"
- Let THEM pick the symbol
- Point to screen: "See the MACD crossover here..."
- Emphasize: "You maintain control"
- End with GitHub QR code

### If Something Breaks

- Use cached symbols: SPY, AAPL, MSFT
- Fall back to laptop screen
- Show GitHub repo in browser

---

## File Summary

**For submission:**

- Abstract: Section 1 above
- Equipment request: Section 2 above
- Additional comments: Section 3 above

**For demo day:**

- Quick guide: Section 4 above (print this)

**That's it. Keep it simple.**

---

## 5. Key References

**Primary Citations (for poster/presentation):**

1. **Wu, Q., et al.** (2023). "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation." *arXiv:2308.08155*. Microsoft Research.
   - Framework used for multi-agent coordination

2. **Xiao, Y., Sun, E., Luo, D., & Wang, W.** "TradingAgents: Multi-Agents LLM Financial Trading Framework." UCLA/MIT/Tauric Research.
   - Multi-agent consensus voting approach

**Supporting (optional):**

3. **Yu, Y., et al.** (2024). "FINCON: A Synthesized LLM Multi-Agent System for Enhanced Financial Decision Making." *arXiv:2407.06567*. Stevens Institute/Harvard.

---

**Use on poster:** AutoGen (framework) + TradingAgents (voting concept)
