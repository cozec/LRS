# Leverage Rotation Strategy (LRS) Backtest suite

📊 **[Detailed Strategy Summary & Results](summary.md)**

This project implements, optimizes, and backtests various "Leverage Rotation Strategies" inspired by Michael A. Gayed's paper "Leverage for the Long Run".

Video reference: https://www.youtube.com/watch?v=cuYIx3ZxNr4&t=1s

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

### 4. Hybrid Sniper (Best Active Strategy)
*   **Logic:** Solves the "MA Lag" problem using RSI for early entries.
    *   **Trend Entry:** 100% TQQQ if `MA10 > MA200 * 1.02`.
    *   **Trend Exit:** Cash if `MA10 < MA200 * 0.98`.
    *   **Sniper Entry:** 50% TQQQ if in Bear zone AND `RSI(14) < 30` (Oversold).
    *   **Sniper Exit:** Sell if `RSI(14) > 50` (Profit Take).
*   **Note:** All indicators (MA10, MA200, RSI) are calculated from S&P 500 price.
*   **Verdict (2010-02-11 to 2026-11-19, next-open fills):** Best risk-adjusted result, but it does **not** beat Buy & Hold TQQQ on final equity. See `summary.md` for full metrics.
    *   **Final Equity:** \$2.09M (vs \$2.39M Buy & Hold, \$1.29M Baseline)
    *   **CAGR:** 37.50% (vs 38.62% Buy & Hold)
    *   **Max Drawdown:** -52.75% (vs -81.66% Buy & Hold); Sharpe 0.84 vs 0.79

## Project Structure
*   `lrs_backtest.py`: Standard Baseline backtest.
*   `lrs_hybrid_sniper.py`: **Main Script.** Runs the Hybrid Sniper strategy backtest and generates detailed trade plots.
*   `lrs_soxl_backtest.py`: Runs the SOXL backtest suite (Buy & Hold, Baseline, Hybrid Sniper).
*   `generate_final_report.py`: Generates a high-level PDF Executive Summary.
*   `summary.md`: Detailed research notes, trade logs, and analysis.

## Usage

### Market Data
All CSVs in `data/` come from one downloader:
```bash
python src/update_data.py      # all tickers; or e.g. python src/get_tqqq.py for one
```
Each file has columns `Date, Open, High, Low, Close, Volume`, with `Close` adjusted for splits and dividends (total return). Today's bar is only saved after the close, and files are replaced atomically. If a download fails, the existing file is left unchanged and the dashboard falls back to it.

### Live Monitoring and Alerts

The project includes an automated monitoring system for the 'Hybrid Sniper' strategy. After each market close (16:15 ET) it evaluates the completed daily bar and emails an alert when the close's decision changes the allocation, for execution at the next open. A failed email is retried on the next check (every 30 min).

### Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   Copy `.env.example` to `.env` and fill in your SMTP details:
   ```bash
   cp .env.example .env
   ```

3. **Run the monitor:**
   ```bash
   python src/monitor_hybrid_sniper.py
   ```

### Background Service (macOS)

The monitor can be set up to run automatically in the background on login.

- **Install (once):** `cp com.user.hybrid_sniper_monitor.plist ~/Library/LaunchAgents/`
- **Start/Load Service:**
   ```bash
   launchctl load ~/Library/LaunchAgents/com.user.hybrid_sniper_monitor.plist
   ```
- **Stop/Unload Service:**
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.user.hybrid_sniper_monitor.plist
   ```
- **Check Status:**
   ```bash
   launchctl list | grep hybrid_sniper
   ```
- **View Logs:**
   ```bash
   tail -f logs/monitor.log
   ```

### Command Line Options

- `--dry-run`: Run the monitor without sending emails.
- `--test-email`: Send a test email to verify configuration.
- `--once`: Check the latest completed close now and exit (first run records the state without alerting).

### 1. Run the Hybrid Sniper Backtest (TQQQ)
This generates trade plots in `plots/trades_comparison.pdf` and `plots/custom_plot_covid.pdf`.
```bash
python src/lrs_hybrid_sniper.py
```

### 2. Run the SOXL Backtest
This loads data from `data/`, executes the backtest, saves CSV results, and generates plots in `plots/soxl_equity_comparison.png` and `plots/soxl_trades.pdf`.
```bash
python src/lrs_soxl_backtest.py
```

### 3. Generate Executive Report
This creates `results/LRS_Hybrid_Sniper_Report.pdf` from the latest backtest results (run step 1 first). `python src/summary_tables.py` prints the markdown tables used in `summary.md`.
```bash
python src/generate_final_report.py
```

### 4. Launch Web Dashboard (Live Monitor)
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

