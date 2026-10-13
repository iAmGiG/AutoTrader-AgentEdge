# GEX Research: Literature and Methods Backlog

Added 2026-10-13 after the same-day regime look-ahead finding in #531 (see issue for details).

**Verification status:** entries marked *searched* were found by web search and their abstracts or summaries were read. Entries marked *from memory* were NOT looked up and must be verified (authors, year, venue) before being cited in any paper.

## Papers

| Paper | Status | Relevance |
|---|---|---|
| Barbon & Buraschi, "Gamma Fragility" (working paper) — <https://abarbon.com/papers/gamma-fragility> | searched, full PDF not read | Dealer gamma imbalance linked to intraday momentum (negative gamma) and reversal (positive gamma), strongest in illiquid stocks. Basis for intraday tests (#530) and a regime x liquidity split. |
| Maurer, "Dealer Gamma Exposure and Overnight Gap Risk" (OptionMetrics working paper) — <https://optionmetrics.com/research/dealer-gamma-exposure-and-overnight-gap-risk-incremental-information-in-low-volatility-regimes/> | searched, abstract only; peer-review status unknown | Gamma adds no out-of-sample volatility signal over a HAR baseline, except overnight gaps on calm low-VIX days. Motivates HAR benchmark and VIX-conditioned tests. |
| Ni, Pearson & Poteshman (2005), "Stock price clustering on option expiration dates", JFE 78(1) — <https://ideas.repec.org/a/eee/jfinec/v78y2005i1p49-87.html> | searched | Closing prices cluster at strikes on expiration dates (at least 16.5 bps average return impact). Testable: expiry days, distance to high-OI strike. |
| Bailey & Lopez de Prado, "The Deflated Sharpe Ratio" (2014) — <https://papers.ssrn.com/abstract=2460551> | searched | Corrects Sharpe for multiple testing and non-normality. Needs an honest trial count N. |
| Probability of Backtest Overfitting (Bailey, Borwein, Lopez de Prado, Zhu) | from memory | Combinatorially symmetric cross-validation; needs the full trial-by-trial return matrix including failed runs. |
| Baltussen, Da, Lammers & Martens, "Hedging demand and market intraday momentum", JFE (2021) | from memory | Intraday momentum from hedging demand; companion to Barbon-Buraschi. |
| Ni, Pearson, Poteshman & White, "Does Option Trading Have a Pervasive Impact on Underlying Stock Prices?", RFS (2021) | from memory | Follow-up to the 2005 clustering paper. |
| White (2000) Reality Check; Hansen (2005) Superior Predictive Ability test | from memory | Test whether the best of many strategies beats a benchmark. |
| Politis & Romano (1994) stationary bootstrap | from memory | Time-series-aware resampling for dependent daily returns. |
| Harvey, Liu & Zhu, "...and the Cross-Section of Expected Returns" | from memory | Argues for t-statistic hurdles near 3 after multiple testing. |

## Data-quality caveats (vendor material, not validated error rates)

- OI-based GEX assumes dealers are long calls and short puts; public open interest cannot identify dealer vs customer. SpotGamma: <https://spotgamma.com/gamma-exposure-gex/>
- Open interest is a prior-night snapshot, so intraday estimates go stale. A flow-signed alternative exists: <https://flashalpha.com/articles/flow-signed-gex-polarity-dealers-long-or-short-gamma>
- gex-database-infrastructure Issue #74: stored equity GEX omits 0DTE contracts; `gex.gex_strike_profile` includes them.
- Vendor break: Alpha Vantage through 2026-10-09, Cboe delayed quotes from 2026-10-12 (GEX level break). Research clamps at 2026-10-09.

## Methods to add to the runners

1. Report regime effects at lags 0, 1, 2, 5 (lag 0 is look-ahead and is for comparison only).
2. Block bootstrap or Newey-West standard errors instead of Welch's t-test.
3. Out-of-sample split (pre-2020 vs 2020 onward) and a VIX-conditioned version.
4. HAR realized-volatility baseline for volatility claims.
5. Deflated Sharpe Ratio and Reality Check / SPA across all strategies, with a logged trial count.
6. Intraday tests on `intraday_gex_summary` (watch the `Long Gamma`/`Short Gamma` label change from 2026-02-06 and the 2026-10-12 break).
7. Expiry-day and distance-to-strike pinning tests.
8. Regime x liquidity split.
