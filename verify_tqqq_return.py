import pandas as pd
import numpy as np

# Constants from lrs_backtest.py
INITIAL_CAPITAL = 10000
DAILY_FEE = 0.01 / 252

def verify_tqqq():
    print("Verifying TQQQ Buy & Hold Calculation...")
    
    # Load Data
    tqqq = pd.read_csv('data/tqqq.csv', index_col='Date', parse_dates=True)
    ndx = pd.read_csv('data/ndx.csv', index_col='Date', parse_dates=True)
    
    start_date = '2010-01-01'
    end_date = '2025-12-11' # Current date in simulation
    
    print(f"\nAnalysis Period: {start_date} to {end_date}")
    
    # 1. Real TQQQ Returns
    tqqq_returns = tqqq['Close'].pct_change()
    
    # 2. Synthetic Returns (NDX * 3 - fee) - For filling gaps (pre-Feb 2010)
    ndx_returns = ndx['Close'].pct_change()
    synthetic_returns = (ndx_returns * 3) - DAILY_FEE
    
    # 3. Combine
    # Reindex to NDX index (which covers full history)
    combined_returns = tqqq_returns.reindex(ndx.index)
    # Fill NA with synthetic
    final_returns = combined_returns.fillna(synthetic_returns)
    
    # 4. Filter for Period
    period_returns = final_returns.loc[start_date:end_date]
    
    # 5. Calculate Growth
    cumulative_returns = (1 + period_returns).cumprod()
    final_multiplier = cumulative_returns.iloc[-1]
    final_value = INITIAL_CAPITAL * final_multiplier
    
    print(f"\n--- Calculation Steps ---")
    print(f"Initial Capital: ${INITIAL_CAPITAL:,.2f}")
    print(f"Total Trading Days: {len(period_returns)}")
    print(f"Cumulative Growth Factor: {final_multiplier:,.4f}x")
    print(f"Final Value: ${final_value:,.2f}")
    
    # Breakdown
    tqqq_start = tqqq.index[0]
    print(f"\n--- Data Composition ---")
    print(f"Synthetic Data (NDX 3x): {start_date} -> {tqqq_start} (Before TQQQ Launch)")
    
    # Check split
    pre_tqqq = period_returns.loc[:'2010-02-08'] # TQQQ started Feb 9 2010?
    post_tqqq = period_returns.loc['2010-02-09':]
    
    growth_pre = (1 + pre_tqqq).cumprod().iloc[-1]
    growth_post = (1 + post_tqqq).cumprod().iloc[-1]
    
    print(f"Growth during Synthetic period: {growth_pre:.4f}x")
    print(f"Growth during Real TQQQ period: {growth_post:.4f}x")
    print(f"Total: {growth_pre:.4f} * {growth_post:.4f} = {growth_pre * growth_post:.4f}x")

if __name__ == "__main__":
    verify_tqqq()
