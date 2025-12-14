# Leverage Rotation Strategy (LRS) Backtest suite

This project implements, optimizes, and backtests various "Leverage Rotation Strategies" inspired by Michael A. Gayed's paper "Leverage for the Long Run".

## Key Strategies Implemented

### 1. Baseline LRS (The Standard)
*   **Logic:** Long TQQQ (3x) when S&P 500 Price > MA200. Cash when Price < MA200.
*   **Verdict:** Reduces drawdown significantly (-53% vs -81%) but lagged Buy & Hold TQQQ in the post-2010 bull run due to whipsaws.

### 2. Golden Cross LRS (Robustness)
*   **Logic:** Uses MA10 crossing MA200 instead of Price crossing MA200. 
*   **Finding:** A **2% Hysteresis Buffer** on the MA10 provided the most robust signals, filtering out noise.

### 3. Hedged LRS (Real World Assets)
*   **Logic:** Rotates into **SHV (Short Treasuries)** or **TMF (3x Long Treasuries)** instead of theoretical Cash.
*   **Verdict:** SHV works perfectly as a Cash proxy. TMF **FAILED** due to the 2022 stock/bond correlation breakdown.

### 4. Hybrid Sniper (THE WINNER)
*   **Logic:** Solves the "MA Lag" problem using RSI for early entries.
    *   **Trend Entry:** 100% TQQQ if `MA10 > MA200 * 1.02`.
    *   **Trend Exit:** Cash if `MA10 < MA200 * 0.98`.
    *   **Sniper Entry:** 50% TQQQ if in Bear zone AND `RSI(14) < 30` (Oversold).
    *   **Sniper Exit:** Sell if `RSI(14) > 50` (Profit Take).
*   **Note:** All indicators (MA10, MA200, RSI) are calculated from S&P 500 price.
*   **Verdict:** **Active Alpha.** Beats Buy & Hold TQQQ while maintaining the safety profile of the Baseline LRS.
    *   **CAGR:** 43.46% (vs 42% Buy & Hold)
    *   **Max Drawdown:** -53.69% (vs -81.66% Buy & Hold)

## Project Structure
*   `lrs_backtest.py`: Standard Baseline backtest.
*   `lrs_hybrid_sniper.py`: **Main Script.** Runs the Hybrid Sniper strategy backtest and generates detailed trade plots.
*   `generate_final_report.py`: Generates a high-level PDF Executive Summary.
*   `summary.md`: Detailed research notes, trade logs, and analysis.

## Usage

### 1. Run the Winning Strategy
This generates trade plots in `plots/trades_comparison.pdf` and `plots/custom_plot_covid.pdf`.
```bash
python lrs_hybrid_sniper.py
```

### 2. Generate Executive Report
This creates `results/LRS_Hybrid_Sniper_Report.pdf`.
```bash
python generate_final_report.py
```

### 3. Launch Web Dashboard (Live Monitor)
Host a local interactive website to visualize the strategy with Entry/Exit flags.
```bash
python web/app.py
```
Then open your browser to: [http://127.0.0.1:8050](http://127.0.0.1:8050)

## Requirements
*   pandas
*   numpy
*   yfinance
*   matplotlib
*   reportlab
*   flask
