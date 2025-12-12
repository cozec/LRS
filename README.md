# Leverage Rotation Strategy (LRS) Backtest

This project implements and backtests the "Leverage Rotation Strategy" described in the paper "Leverage for the Long Run" by Michael A. Gayed.

## Core Strategy
- **Risk-On**: When S&P 500 is ABOVE its 200-day Simple Moving Average (SMA), hold a leveraged S&P 500 ETF (2x or 3x).
- **Risk-Off**: When S&P 500 is BELOW its 200-day SMA, switch to cash/T-Bills.

## Project Structure
- `lrs_backtest.py`: Main script to download data, run backtest, and generate results.
- `data/`: Stores downloaded S&P 500 historical data.
- `plots/`: Contains generated performance charts.
- `results/`: Contains performance metrics and trade logs.

## Usage
1.  Ensure you have Python installed and the virtual environment activated.
2.  Install dependencies (if not already):
    ```bash
    pip install pandas numpy yfinance matplotlib
    ```
3.  Run the backtest:
    ```bash
    python lrs_backtest.py
    ```

## Results
The script generates results for both 2x and 3x leverage scenarios. Check the `results/` folder for CSV summaries and `plots/` for visual performance comparisons.
