# Leverage Rotation Strategy (LRS) Backtest Results
## 0. Strategy Mechanics
How the "Hybrid Sniper" manages risk and opportunity:

> **Note:** All moving averages (MA10, MA200) and RSI are calculated from the **S&P 500** price, not TQQQ.

**1. Trend Mode (The Shield)**
*   **Entry Condition:** `MA10 > MA200 * 1.02` (10-day MA crosses above the +2% buffer of the 200-day SMA).
*   **Action:** 100% Allocation to TQQQ.
*   **Goal:** Capture the bulk of long-term bull markets.
*   **Exit Condition:** `MA10 < MA200 * 0.98` (MA crosses below the -2% buffer).

**2. Sniper Mode (The Spear)**
*   **Entry Condition:** In Bear zone (`MA10 < MA200 * 0.98`) **AND** `RSI(14) < 30` (Panic Selling).
*   **Action:** 50% Allocation to TQQQ (Starter Position).
*   **Goal:** Catch "V-Bottom" reversals that the MA10/MA200 crossover is too slow to identify.
*   **Exit (Profit Take):** If `RSI(14) > 50` (Mean Reversion), sell the position and return to Cash.
*   **Promotion:** If the market rallies enough for `MA10 > MA200 * 1.02`, the position scales up to 100% (Trend Mode).


## Backtest Conventions
These apply to every result below (implemented once in `src/backtest_common.py`, tested in `tests/test_backtest_common.py`).

*   **Data:** daily bars from yfinance via `src/update_data.py`; `Close` is adjusted for splits and dividends (total return). Signals use the full S&P 500 history (from 1928), so the 200-day SMA has no warm-up gap inside the window.
*   **Fills (primary): decide at the close, trade at the next open.** All signal inputs come from closes up to the decision day. The trade is sized from the portfolio marked at the fill price (the open), and the day's return is split into the overnight leg (old position) and the intraday leg (new position).
*   **Market-on-close (MOC)** results are shown alongside as a labeled sensitivity (decide and fill at the same close). For the headline strategies the gap is 1–8%, in both directions, which is consistent with no lookahead; high-turnover rules differ more (see Section 1).
*   **Start:** \$10,000 in cash at the first close of the window. **Buy & Hold** final equity is exactly \$10,000 × last close / first close.
*   **Cash** earns a flat 3%/yr (a 0% cash run is shown as a sensitivity). The 50% Sniper weight is rebalanced at each fill. **No commissions or slippage.**
*   **Trades:** a trade starts at any change in allocation (e.g. Trend 100% → Sniper 50% closes one trade and opens another). Entry and exit dates are fill dates (opens); returns are open-to-open.
*   **Regenerate:** `python src/lrs_golden_cross.py`, `python src/lrs_hybrid_sniper.py`, `python src/lrs_soxl_backtest.py`, then `python src/summary_tables.py` and `python src/generate_final_report.py`.

## 1. Golden Cross Filter Optimization (TQQQ: 2010-02-11 to 2026-11-19)
Comparison of moving-average crossovers versus the 200-day SMA (all on the S&P 500) to time TQQQ, instead of raw Price.

**Trigger:** `MA(n) > MA(200)`; buffered variants enter above `SMA200 × (1 + b)` and exit below `SMA200 × (1 − b)`. Ordered by final equity (next-open fills).

| Strategy | Final Equity | Return | CAGR | Max DD | Sharpe | Alpha (TQQQ) | Beta (TQQQ) | Trades | Final Equity (MOC) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Buy & Hold TQQQ | \$2,388,574 | 23785.74% | 38.62% | -81.66% | 0.79 | +0.00% | 1.00 |  | \$2,388,574 |
| GC (10/200) + 2% Buffer | \$1,285,188 | 12751.88% | 33.59% | -51.47% | 0.79 | +9.61% | 0.59 | 9 | \$1,211,813 |
| Golden Cross (10/200) | \$934,409 | 9244.09% | 31.07% | -51.78% | 0.75 | +7.29% | 0.58 | 17 | \$841,678 |
| Asym (Entry 10/200+2%, Exit 10 < 100) | \$924,475 | 9144.75% | 30.99% | -45.05% | 0.78 | +10.92% | 0.48 | 93 | \$712,040 |
| Golden Cross (5/200) | \$862,009 | 8520.09% | 30.44% | -62.40% | 0.75 | +7.46% | 0.56 | 22 | \$888,004 |
| GC (10/200) + 1% Buffer | \$785,197 | 7751.97% | 29.72% | -62.87% | 0.73 | +5.59% | 0.59 | 12 | \$602,108 |
| Golden Cross (20/200) | \$682,370 | 6723.70% | 28.64% | -70.95% | 0.70 | +2.59% | 0.65 | 11 | \$631,417 |
| Original LRS (Price > SMA200) | \$571,121 | 5611.21% | 27.28% | -61.66% | 0.69 | +4.69% | 0.55 | 51 | \$666,404 |
| GC (10/200) + 3% Buffer | \$483,658 | 4736.58% | 26.02% | -63.47% | 0.66 | +0.41% | 0.63 | 8 | \$547,330 |
| Golden Cross (50/200) | \$288,646 | 2786.46% | 22.20% | -69.92% | 0.59 | -6.33% | 0.72 | 9 | \$254,620 |
| GC (10/200) + 4% Buffer | \$255,383 | 2453.83% | 21.32% | -62.09% | 0.58 | -4.45% | 0.64 | 8 | \$200,251 |
| GC (10/200) + 5% Buffer | \$94,612 | 846.12% | 14.34% | -69.88% | 0.46 | -12.30% | 0.66 | 8 | \$111,832 |

### Key Findings
1.  **The 2% buffer is still the best active rule:** GC (10/200) + 2% grows \$10k to **\$1.29M** with a -51% max drawdown, ahead of the plain 10/200 cross (\$934k). The 1% buffer (\$785k) filters too few whipsaws and 3%+ buffers react too late.
2.  **Asymmetric exit (exit when MA10 < SMA100)** has the smallest drawdown (-45%) and matches the plain 10/200 cross on return, but trades 93 times; with no trading costs modeled, that count flatters it.
3.  **No timing rule beats Buy & Hold TQQQ on final equity** (\$2.39M); they all trade lower return for a much smaller drawdown (-45% to -71% vs -82%).
4.  **Fill convention:** for the top rule (2% buffer) next-open vs MOC differs by 6% (\$1.29M vs \$1.21M). High-turnover rules are far more sensitive to the fill price: Asym (93 trades) is \$924k next-open vs \$712k MOC, the 1% buffer \$785k vs \$602k, and Original LRS \$571k vs \$666k. The top of the ranking does not change.

## 2. The "Hybrid Sniper" Strategy (RSI Re-Entry)
*(Backtest Range: 2010-02-11 to 2026-11-19, next-open fills)*

**Configuration:**
*   **Trend Entry (100% TQQQ):** `MA10 > MA200 * 1.02` (MA crosses above +2% buffer).
*   **Trend Exit (0% / Cash):** `MA10 < MA200 * 0.98` (MA crosses below -2% buffer).
*   **Sniper Entry (50% TQQQ):** While in Bear zone (MA10 < MA200 * 0.98) AND `RSI(14) < 30` (Deep Oversold).
*   **Sniper Exit:** Sell the 50% position if `RSI > 50` (Profit Take) OR hold until Trend Entry confirms (scale up to 100%).

### Performance (ordered by final equity)

| Strategy | Final Equity | Return | CAGR | Max DD | Volatility | Sharpe | Sortino | Calmar | Alpha (TQQQ) | Beta (TQQQ) | Alpha (SPX) | Beta (SPX) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Buy & Hold TQQQ | \$2,388,574 | 23785.74% | 38.62% | -81.66% | 61.37% | 0.79 | 1.02 | 0.47 | +0.00% | 1.00 | +5.87% | 3.32 |
| Hybrid Sniper | \$2,085,295 | 20752.95% | 37.50% | -52.75% | 48.47% | 0.84 | 0.99 | 0.71 | +11.01% | 0.66 | +15.75% | 2.09 |
| LRS Baseline | \$1,285,188 | 12751.88% | 33.59% | -51.47% | 47.04% | 0.79 | 0.91 | 0.65 | +9.61% | 0.59 | +14.40% | 1.81 |

*Alpha/Beta are Jensen's, from daily returns over a 3% risk-free rate, against Buy & Hold TQQQ and against the S&P 500.*

#### Sensitivity: Fill Convention and Cash Assumption

| Run | Fill | Final Equity | CAGR | Max DD | Sharpe |
| :--- | :--- | ---: | ---: | ---: | ---: |
| Hybrid Sniper (MOC) | moc | \$2,113,046 | 37.61% | -53.69% | 0.84 |
| Hybrid Sniper | next_open | \$2,085,295 | 37.50% | -52.75% | 0.84 |
| Hybrid Sniper (0% cash) | next_open | \$1,909,799 | 36.78% | -52.81% | 0.83 |
| LRS Baseline | next_open | \$1,285,188 | 33.59% | -51.47% | 0.79 |
| LRS Baseline (MOC) | moc | \$1,211,813 | 33.12% | -53.23% | 0.78 |

**Indicator Details:** RSI(14) with Wilder's smoothing on the S&P 500 daily close.

### Real-World Case Studies
Examples of the Sniper logic in action vs. the Baseline (fill dates are opens).

**Case Study 1: The COVID Crash (March 2020)**
*   **Scenario:** The market collapsed ~30% in weeks. The SMA trend signal turned bearish and stayed bearish for months, so the Baseline sat in cash and missed the bottom.
*   **Sniper Action:** RSI fell below 30; the strategy bought 50% TQQQ at the open on **2020-03-13** and sold at the open on **2020-04-09** after RSI crossed 50.
*   **Gain:** **+7.93%** in 27 days (TQQQ open-to-open: +7.06%), while the Baseline made only cash interest.

**Case Study 2: The Christmas Crash (Dec 2018)**
*   **Sniper Action:** Bought 50% TQQQ on **2018-12-20**, sold on **2019-01-09**.
*   **Gain:** **+5.77%** in 20 days.

**Conclusion:**
*   **Versus the Baseline:** the RSI re-entry adds **\$800k** (\$2.09M vs \$1.29M) and +3.9 points of CAGR for almost the same drawdown (-52.8% vs -51.5%). Every closed Sniper trade was profitable.
*   **Versus Buy & Hold TQQQ:** the Sniper **does not beat it on final equity** (\$2.09M vs \$2.39M; CAGR 37.5% vs 38.6%). It wins on risk: max drawdown -52.8% vs -81.7%, Sharpe 0.84 vs 0.79, Calmar 0.71 vs 0.47.
*   **Current weakness:** the open Trend trade (since 2026-04-17) is **-14.8%**. TQQQ has fallen 36% since June 2026 while the S&P 500's MA10 stayed above SMA200 × 0.98, so the S&P-based filter never signalled an exit. Signals come from the S&P 500, but the traded asset is a 3x Nasdaq-100 fund.

### Hybrid Sniper Trade Log
All 16 trades (fewer than 30, so each is listed). Entry/exit are fill dates at the open.

| # | Entry (open) | Exit (open) | Days | Type | Exit Reason | Return (Strat) | Return (TQQQ) |
| ---: | :--- | :--- | ---: | :--- | :--- | ---: | ---: |
| 1 | 2010-02-12 | 2010-06-04 | 112 | Trend (SMA) | SMA break | +12.79% | +12.79% |
| 2 | 2010-10-04 | 2011-08-09 | 309 | Trend (SMA) | SMA break -> Sniper | +7.80% | +7.80% |
| 3 | 2011-08-09 | 2011-08-30 | 21 | **Sniper (RSI)** | RSI target | +8.09% | +14.55% |
| 4 | 2012-01-18 | 2015-08-26 | 1316 | Trend (SMA) | SMA break -> Sniper | +337.64% | +337.64% |
| 5 | 2015-08-26 | 2015-09-17 | 22 | **Sniper (RSI)** | RSI target | +8.67% | +16.91% |
| 6 | 2016-01-14 | 2016-02-18 | 35 | **Sniper (RSI)** | RSI target | +0.57% | -0.82% |
| 7 | 2016-04-11 | 2018-11-01 | 934 | Trend (SMA) | SMA break | +206.70% | +206.70% |
| 8 | 2018-12-20 | 2019-01-09 | 20 | **Sniper (RSI)** | RSI target | +5.77% | +9.89% |
| 9 | 2019-03-22 | 2020-03-11 | 355 | Trend (SMA) | SMA break | +11.78% | +11.78% |
| 10 | 2020-03-13 | 2020-04-09 | 27 | **Sniper (RSI)** | RSI target | +7.93% | +7.06% |
| 11 | 2020-06-09 | 2022-02-28 | 629 | Trend (SMA) | SMA break | +122.07% | +122.07% |
| 12 | 2022-09-26 | 2022-10-24 | 28 | **Sniper (RSI)** | RSI target | +0.12% | -2.50% |
| 13 | 2023-02-03 | 2025-03-24 | 780 | Trend (SMA) | SMA break | +166.15% | +166.15% |
| 14 | 2025-04-07 | 2025-04-25 | 18 | **Sniper (RSI)** | RSI target | +21.85% | +41.61% |
| 15 | 2025-05-27 | 2026-04-06 | 314 | Trend (SMA) | SMA break | +27.28% | +27.28% |
| 16 | 2026-04-17 | 2026-11-19 (still open) | 216 | Trend (SMA) | Still open | -14.82% | -14.82% |

### Trade Statistics

| Category | Metric | Value |
| :--- | :--- | :--- |
| **Count** | Total Trades | 16 (15 closed, 1 open) |
|  | Trend Trades | 9 |
|  | Sniper Trades | 7 |
| **Holding Period** | Mean (All) | 321 days |
|  | Mean (Trend) | 552 days |
|  | Mean (Sniper) | 24 days |
|  | Longest Trade | 1,316 days (2012-01-18 to 2015-08-26) |
|  | Shortest Trade | 18 days |
| **Wait Time** | Mean Wait in Cash Between Trades | 76 days |
|  | Max Wait | 210 days |
| **Returns** | Mean Return (All) | +58.15% |
|  | Mean Return (Trend) | +97.49% |
|  | Mean Return (Sniper) | +7.57% |
|  | Win Rate (closed trades) | 15/15 (100%) |
|  | Best Trade | +337.64% |
|  | Worst Trade | -14.82% |
| **Exposure** | Total Period | 16.8 years |
|  | Time in Market | 83.9% |
|  | Time in Cash | 16.1% |

## 3. SOXL Expansion Backtest (Inception - Present)
*(Backtest Range: 2010-03-11 to 2026-11-19, next-open fills)*

To test the robustness of the Hybrid Sniper across sector-leveraged products, the same S&P 500 signals (MA10, SMA200, RSI) were used to trade **SOXL** (3x Bull Semiconductor ETF) from its inception.

### Performance (ordered by final equity)

| Strategy | Final Equity | Return | CAGR | Max DD | Volatility | Sharpe | Sortino | Calmar | Alpha (SOXL) | Beta (SOXL) | Alpha (SPX) | Beta (SPX) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Hybrid Sniper | \$920,590 | 9105.90% | 31.12% | -86.40% | 77.38% | 0.71 | 0.87 | 0.36 | +9.00% | 0.72 | +4.47% | 2.75 |
| Buy & Hold SOXL | \$754,409 | 7444.09% | 29.56% | -90.46% | 93.01% | 0.72 | 0.99 | 0.33 | +0.00% | 1.00 | -10.42% | 4.30 |
| LRS Baseline | \$543,751 | 5337.51% | 27.05% | -86.40% | 75.82% | 0.66 | 0.80 | 0.31 | +6.37% | 0.67 | +3.46% | 2.40 |

*Alpha/Beta are Jensen's, from daily returns over a 3% risk-free rate, against Buy & Hold SOXL and against the S&P 500.*

#### Sensitivity: Fill Convention and Cash Assumption

| Run | Fill | Final Equity | CAGR | Max DD | Sharpe |
| :--- | :--- | ---: | ---: | ---: | ---: |
| Hybrid Sniper (MOC) | moc | \$988,973 | 31.68% | -86.40% | 0.71 |
| Hybrid Sniper | next_open | \$920,590 | 31.12% | -86.40% | 0.71 |
| Hybrid Sniper (0% cash) | next_open | \$843,115 | 30.43% | -86.40% | 0.70 |
| LRS Baseline | next_open | \$543,751 | 27.05% | -86.40% | 0.66 |
| LRS Baseline (MOC) | moc | \$523,021 | 26.75% | -86.40% | 0.66 |

### Key Findings
1. **Return:** the Hybrid Sniper ends at **\$921k**, ahead of Buy & Hold SOXL (\$754k) and the Baseline (\$544k).
2. **No real drawdown protection:** all three strategies lose at least 86% at their worst. The strategies' -86.4% drawdown is the 2026 semiconductor crash (SOXL -83% from late June to November) while the S&P 500 stayed in Trend mode, so the filter kept them fully invested. The open Trend trade is **-51.4%**.
3. **Takeaway:** a broad-market (S&P 500) regime filter does not protect a sector fund from a sector-specific crash. A filter on the traded asset's own index (e.g. SOX) would be the next test.

### Hybrid Sniper SOXL Trade Log
All 16 trades (fewer than 30, so each is listed). Entry/exit are fill dates at the open.

| # | Entry (open) | Exit (open) | Days | Type | Exit Reason | Return (Strat) | Return (SOXL) |
| ---: | :--- | :--- | ---: | :--- | :--- | ---: | ---: |
| 1 | 2010-03-12 | 2010-06-04 | 84 | Trend (SMA) | SMA break | -4.84% | -4.84% |
| 2 | 2010-10-04 | 2011-08-09 | 309 | Trend (SMA) | SMA break -> Sniper | -19.93% | -19.93% |
| 3 | 2011-08-09 | 2011-08-30 | 21 | **Sniper (RSI)** | RSI target | +6.71% | +11.36% |
| 4 | 2012-01-18 | 2015-08-26 | 1316 | Trend (SMA) | SMA break -> Sniper | +137.81% | +137.81% |
| 5 | 2015-08-26 | 2015-09-17 | 22 | **Sniper (RSI)** | RSI target | +12.35% | +24.65% |
| 6 | 2016-01-14 | 2016-02-18 | 35 | **Sniper (RSI)** | RSI target | +4.49% | +6.34% |
| 7 | 2016-04-11 | 2018-11-01 | 934 | Trend (SMA) | SMA break | +303.10% | +303.10% |
| 8 | 2018-12-20 | 2019-01-09 | 20 | **Sniper (RSI)** | RSI target | +5.45% | +8.74% |
| 9 | 2019-03-22 | 2020-03-11 | 355 | Trend (SMA) | SMA break | +7.53% | +7.53% |
| 10 | 2020-03-13 | 2020-04-09 | 27 | **Sniper (RSI)** | RSI target | +6.22% | -0.30% |
| 11 | 2020-06-09 | 2022-02-28 | 629 | Trend (SMA) | SMA break | +224.27% | +224.27% |
| 12 | 2022-09-26 | 2022-10-24 | 28 | **Sniper (RSI)** | RSI target | -4.09% | -12.82% |
| 13 | 2023-02-03 | 2025-03-24 | 780 | Trend (SMA) | SMA break | +23.92% | +23.92% |
| 14 | 2025-04-07 | 2025-04-25 | 18 | **Sniper (RSI)** | RSI target | +27.56% | +47.59% |
| 15 | 2025-05-27 | 2026-04-06 | 314 | Trend (SMA) | SMA break | +222.20% | +222.20% |
| 16 | 2026-04-17 | 2026-11-19 (still open) | 216 | Trend (SMA) | Still open | -51.36% | -51.36% |

### Trade Statistics (SOXL)

| Category | Metric | Value |
| :--- | :--- | :--- |
| **Count** | Total Trades | 16 (15 closed, 1 open) |
|  | Trend Trades | 9 |
|  | Sniper Trades | 7 |
| **Holding Period** | Mean (All) | 319 days |
|  | Mean (Trend) | 549 days |
|  | Mean (Sniper) | 24 days |
|  | Longest Trade | 1,316 days (2012-01-18 to 2015-08-26) |
|  | Shortest Trade | 18 days |
| **Wait Time** | Mean Wait in Cash Between Trades | 76 days |
|  | Max Wait | 210 days |
| **Returns** | Mean Return (All) | +56.34% |
|  | Mean Return (Trend) | +93.63% |
|  | Mean Return (Sniper) | +8.39% |
|  | Win Rate (closed trades) | 12/15 (80%) |
|  | Best Trade | +303.10% |
|  | Worst Trade | -51.36% |
| **Exposure** | Total Period | 16.7 years |
|  | Time in Market | 83.8% |
|  | Time in Cash | 16.2% |

## 4. Live Monitoring System
A robust automated monitoring system tracks the 'Hybrid Sniper' strategy in real-time.

### Features
- **Frequency:** Once per completed daily bar, after 16:15 ET (the loop wakes every 30 min and re-checks until the day's final close is available).
- **Signal Tracking:** Downloads from `yfinance` and evaluates only final closes; intraday bars are never used for decisions or saved to `data/`.
- **Timing:** An alert reports the decision made at that close, to be executed at the **next open**.
- **Reliability:** State for an alert is only updated after its email is sent, so a failed send is retried. The first run records the current state without alerting.
- **State Management:** Persists current signal status in `results/monitor_state.json` to ensure alerts are sent only once per event.

### Alerts Monitored
The system sends automated email notifications for the following events:
- 🚀 **Entry/Increase:** Strategy allocation increases (e.g., Cash ➔ Sniper or Sniper ➔ Trend).
- 📉 **Exit/Decrease:** Strategy allocation decreases (e.g., Trend ➔ Cash or Sniper ➔ Cash).
- ⚠️ **Trend Warning:** Triggered when the close puts **MA10 below SMA200** (Pre-warning before strategy exit).
- ✅ **Trend Recovery:** Triggered when **MA10 moves back above SMA200**.

### Setup & Management
The monitor is configured as a persistent macOS background service.

**1. Service Management:**
- **Install (once):** `cp com.user.hybrid_sniper_monitor.plist ~/Library/LaunchAgents/` (requires a filled-in `.env`)
- **Status:** `launchctl list | grep hybrid_sniper`
- **Stop:** `launchctl unload ~/Library/LaunchAgents/com.user.hybrid_sniper_monitor.plist`
- **Start:** `launchctl load ~/Library/LaunchAgents/com.user.hybrid_sniper_monitor.plist`

**2. Logs:**
- **Real-time monitoring:** `tail -f logs/monitor.log`
- **Standard output:** `tail -f logs/launchd_stdout.log`

**3. Implementation:**
- Core script: `src/monitor_hybrid_sniper.py`
- Configuration: `.env` file (SMTP and recipient settings)

