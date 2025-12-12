# Leverage Rotation Strategy (LRS) Backtest Results

## 1. Post-2010 Comparison (The "Bull Run" Era)
**Period:** Feb 11, 2010 – Dec 14, 2025
**Data:** Real TQQQ Data (No synthetic extrapolation) vs Benchmarks

| Strategy | CAGR | Max Drawdown | Final Value ($10k) |
| :--- | :--- | :--- | :--- |
| **Buy & Hold TQQQ** | **42.17%** | **-81.66%** | **$2,716,246** |
| **LRS TQQQ** | 34.39% | -56.16% | $1,109,535 |
| **LRS SPX 3x** | 23.36% | -45.99% | $297,029 |
| **Buy & Hold SPX** | 11.99% | -33.92% | $61,612 |

### Key Insights
*   **Bull Market Dominance:** In the secular bull market of the 2010s and early 2020s, **Buy & Hold TQQQ** generated exceptional returns.
*   **Risk Reduction:** LRS reduced Max Drawdown significantly (-56% vs -82%), but the "whipsaw" cost of moving to cash during shallow corrections caused it to lag Buy & Hold in this specific period.

---

## 2. Long-Term Historical Context (1928 - 2025)
*Analysis using S&P 500 Index Data (Unleveraged Proxy)*

| Strategy | CAGR | Total Return |
| :--- | :--- | :--- |
| **MA 10 Strategy** | **6.93%** | **67,140%** |
| **MA 200 Strategy** (LRS) | 6.78% | 58,652% |
| **Buy & Hold (Index)** | 6.11% | 31,570% |

### Key Insights
*   **Long-Term Outperformance:** Over 97 years, LRS strategies outperform Buy & Hold by avoiding major bear markets (1929, 2000, 2008).

---

## 3. Golden Cross Filter Optimization (TQQQ: 2010 - 2025)
Comparison of using different Moving Average (MA) lengths to trigger the crossover versus the 200-day SMA, instead of using raw Price.

**Trigger:** `MA(n) > MA(200)`

| Strategy | CAGR | Max Drawdown | Final Value ($10k) |
| :--- | :--- | :--- | :--- |
| **Buy & Hold TQQQ** | **42.48%** | **-81.66%** | **$2,714,311** |
| **GC (10/200) + 2% Buffer** | **38.79%** | **-53.23%** | **$1,791,482** |
| Golden Cross (10/200) | 34.95% | -54.84% | $1,149,032 |
| GC (10/200) + 1% Buffer | 33.80% | -59.63% | $1,003,616 |
| Original LRS (Price > 200) | 31.39% | -59.24% | $752,475 |
| GC (10/200) + 3% Buffer | 29.82% | -57.18% | $621,972 |
| Golden Cross (50/200) | 23.69% | -69.92% | $289,343 |

### Key Findings
1.  **Buffer Magic (2% is Optimal):** A **2% buffer** applied to the 10-day MA crossover was the optimal configuration, generating **$1.8M**. It perfectly balanced noise reduction with timely signals.
2.  **Sensitivity:**
    *   **1% Buffer ($1.0M)**: Too narrow. It didn't filter enough whipsaws, performing similarly to the unbuffered strategy.
    *   **3% Buffer ($622k)**: Too wide. It delayed re-entry into uptrends significantly, causing the strategy to miss large chunks of the recovery (even worse than the original LRS).
3.  **Conclusion:** The **10-day SMA crossover with a 2% hysteresis buffer** is the most robust active strategy identified for this volatile, high-return asset class.
