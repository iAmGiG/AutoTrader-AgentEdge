# GEX Research: Literature and Methods Backlog

Added 2026-10-13 after the same-day regime look-ahead finding in #531 (see issue for details).

**Verification status:** *searched* means found by web search with abstracts or summaries read. *Citation verified* (2026-10-13) means authors, venue, volume and pages were confirmed by search, but the full text was not read. Confirm wording against the published text before quoting.

## Papers

| Paper | Status | Relevance |
|---|---|---|
| Barbon & Buraschi, "Gamma Fragility" (working paper) — <https://abarbon.com/papers/gamma-fragility> | searched, full PDF not read | Dealer gamma imbalance linked to intraday momentum (negative gamma) and reversal (positive gamma), strongest in illiquid stocks. Basis for intraday tests (#530) and a regime x liquidity split. |
| Maurer, "Dealer Gamma Exposure and Overnight Gap Risk" (OptionMetrics working paper) — <https://optionmetrics.com/research/dealer-gamma-exposure-and-overnight-gap-risk-incremental-information-in-low-volatility-regimes/> | searched, abstract only; peer-review status unknown | Gamma adds no out-of-sample volatility signal over a HAR baseline, except overnight gaps on calm low-VIX days. Motivates HAR benchmark and VIX-conditioned tests. |
| Ni, Pearson & Poteshman (2005), "Stock price clustering on option expiration dates", JFE 78(1) — <https://ideas.repec.org/a/eee/jfinec/v78y2005i1p49-87.html> | searched | Closing prices cluster at strikes on expiration dates (at least 16.5 bps average return impact). Testable: expiry days, distance to high-OI strike. |
| Bailey & Lopez de Prado, "The Deflated Sharpe Ratio" (2014) — <https://papers.ssrn.com/abstract=2460551> | searched | Corrects Sharpe for multiple testing and non-normality. Needs an honest trial count N. |
| Bailey, Borwein, Lopez de Prado & Zhu, "The Probability of Backtest Overfitting", Journal of Computational Finance 20(4) (2017), doi:10.21314/JCF.2016.322 — <https://papers.ssrn.com/abstract=2326253> | citation verified | Combinatorially symmetric cross-validation (CSCV); needs the full trial-by-trial return matrix including failed runs. |
| Baltussen, Da, Lammers & Martens, "Hedging demand and market intraday momentum", JFE 142 (2021) 377-403, doi:10.1016/j.jfineco.2021.04.029 — <https://www3.nd.edu/~zda/intramom.pdf> | citation verified | The last 30 minutes are predicted by the rest of the day across 60+ futures (1974-2020), linked to gamma hedging by option market makers and leveraged ETFs. The design used in `intraday_gamma_momentum.py`. |
| Ni, Pearson, Poteshman & White, "Does Option Trading Have a Pervasive Impact on Underlying Stock Prices?", RFS 34(4) (2021) 1952-1986, doi:10.1093/rfs/hhaa082 — <https://ideas.repec.org/a/oup/rfinst/v34y2021i4p1952-1986..html> | citation verified | Market makers' hedge rebalancing affects stock return volatility and the chance of large moves (a noninformational channel). Consistent with the 40-symbol panel: negative GEX goes with higher next-day variance. |
| White, "A Reality Check for Data Snooping", Econometrica 68(5) (2000) 1097-1126; Hansen, "A Test for Superior Predictive Ability", JBES 23 (2005) 365-380 | citation verified | Test whether the best of many models beats a benchmark; SPA reduces sensitivity to poor alternatives. |
| Politis & Romano, "The Stationary Bootstrap", JASA 89(428) (1994) 1303-1313 | citation verified | Resampling blocks of geometric random length for weakly dependent stationary data. |
| Harvey, Liu & Zhu, "...and the Cross-Section of Expected Returns", RFS 29(1) (2016) 5-68, doi:10.1093/rfs/hhv059 | citation verified | Argues new factors should clear t > 3 after multiple testing. Contested by later work (arXiv 2206.15365). |

## Data-quality caveats (vendor material, not validated error rates)

- OI-based GEX assumes dealers are long calls and short puts; public open interest cannot identify dealer vs customer. SpotGamma: <https://spotgamma.com/gamma-exposure-gex/>
- Open interest is a prior-night snapshot, so intraday estimates go stale. A flow-signed alternative exists: <https://flashalpha.com/articles/flow-signed-gex-polarity-dealers-long-or-short-gamma>
- gex-database-infrastructure Issue #74: stored equity GEX omits 0DTE contracts; `gex.gex_strike_profile` includes them.
- Vendor break: Alpha Vantage through 2026-10-09, Cboe delayed quotes from 2026-10-12 (GEX level break). Research clamps at 2026-10-09.

## Methods to add to the runners

Status as of 2026-10-13. Results are in [regime_lookahead_revalidation.md](regime_lookahead_revalidation.md).

| # | Method | Status |
|---|---|---|
| 1 | Report regime effects at lags 0, 1, 2, 5 (lag 0 is look-ahead, comparison only) | Done for MACD+RSI (`--regime-lags`) |
| 2 | Newey-West errors instead of Welch's t-test | Done (`research_cli.py`); block bootstrap not done |
| 3 | Out-of-sample split (pre-2020 vs 2020 onward) and VIX conditioning | Done (`var_vol_baseline.py`, `gex_vol_panel.py`) |
| 4 | HAR realized-volatility baseline, plus leverage controls | Done (log-HAR on Parkinson variance) |
| 5 | Multiple-testing correction | Holm, BH and \|t\| > 3 done (`multiple_testing_audit.py`); Deflated Sharpe and Reality Check / SPA not done (no trading overlay was significant) |
| 6 | Intraday tests on `intraday_gex_summary` (label change 2026-02-06, vendor break 2026-10-12) | Done (`intraday_gamma_momentum.py`): null |
| 7 | Expiry-day and distance-to-strike pinning tests | Done (`expiry_pinning.py`): tiny effect when dealers long gamma |
| 8 | Regime × liquidity split | Done (`gex_vol_panel.py`): effect scales with \|GEX\|/dollar volume, not illiquidity |
| 9 | Verify the from-memory citations | Done 2026-10-13 (citation level) |
