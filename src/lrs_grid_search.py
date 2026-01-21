#!/usr/bin/env python3
"""
LRS Golden Cross Strategy Backtest

Strategy:
- Buy (Risk-On) when n-day SMA > 200-day SMA.
- Sell (Risk-Off) when n-day SMA < 200-day SMA.
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# Configuration
INITIAL_CAPITAL = 10000
DAILY_FEE = 0.01 / 252
RISK_FREE_RATE = 0.03
DATA_DIR = 'data'
PLOTS_DIR = 'plots'
RESULTS_DIR = 'results'

def load_data_and_signals(short_windows):
    """Load data and calculate signals on full history to avoid warm-up loss."""
    try:
        sp500 = pd.read_csv(os.path.join(DATA_DIR, 'sp500.csv'), index_col=0, parse_dates=True).sort_index()
        tqqq = pd.read_csv(os.path.join(DATA_DIR, 'tqqq.csv'), index_col=0, parse_dates=True).sort_index()
        upro = pd.read_csv(os.path.join(DATA_DIR, 'upro.csv'), index_col=0, parse_dates=True).sort_index()
        
        df = sp500.copy()
        
        # Grid Search Setup
        sma_periods = [50, 100, 200]
        
        # Pre-calculate all SMAs
        for p in sma_periods:
            df[f'SMA_{p}'] = df['Close'].rolling(p).mean()
            
        # Signal Line
        n = 10
        ma_col = f'MA_{n}'
        df[ma_col] = df['Close'].rolling(n).mean()
        
        buffer = 0.02
        
        # Grid Search Loops
        for entry_p in sma_periods:
            for exit_p in sma_periods:
                
                sig_col = f'Signal_In{entry_p}_Out{exit_p}'
                pos_col = f'Pos_In{entry_p}_Out{exit_p}'
                
                entry_sma_col = f'SMA_{entry_p}'
                exit_sma_col = f'SMA_{exit_p}'
                
                # Logic:
                # Enter if MA_10 > EntrySMA * (1 + 0.02)
                # Exit  if MA_10 < ExitSMA * (1 - 0.02)  <-- Using symmetric buffer logic per plan
                
                upper = df[entry_sma_col] * (1 + buffer)
                lower = df[exit_sma_col] * (1 - buffer)
                
                signals = []
                state = 0 # Risk-Off
                
                ma_vals = df[ma_col].values
                up_vals = upper.values
                low_vals = lower.values
                
                for i in range(len(df)):
                    val = ma_vals[i]
                    u = up_vals[i]
                    l = low_vals[i]
                    
                    if np.isnan(val) or np.isnan(u) or np.isnan(l):
                        signals.append(0)
                        continue
                        
                    if state == 0: # Check Entry
                        if val > u:
                            state = 1
                    elif state == 1: # Check Exit
                        if val < l:
                            state = 0
                    
                    signals.append(state)
                
                df[sig_col] = signals
                df[pos_col] = df[sig_col].shift(1)

        # Original LRS (Price > SMA 200)
        df['LRS_Original_Signal'] = np.where(df['Close'] > df['SMA_200'], 1, 0)
        df['LRS_Original_Pos'] = df['LRS_Original_Signal'].shift(1)
        
        # Align with TQQQ/UPRO
        # We only care about the period where we have TQQQ data
        # Inner join on index
        
        # Prepare returns
        tqqq_ret = tqqq['Close'].pct_change()
        upro_ret = upro['Close'].pct_change()
        
        df['TQQQ_Return'] = tqqq_ret
        df['UPRO_Return'] = upro_ret
        df['Cash_Return'] = RISK_FREE_RATE / 252
        
        # Filter to TQQQ start
        start_date = '2010-02-12'
        df = df.loc[start_date:].copy()
        
        return df
        
    except Exception as e:
        print(f"Error loading data: {e}")
        return None

def run_backtest(df, n, buffer_val=None):
    """Run backtest using pre-calculated positions."""
    df_res = df.copy()
    
    if buffer_val is not None:
        pos_col = f'Pos_{n}_Buf_{buffer_val}'
    else:
        pos_col = f'Pos_{n}'
    
    # Calculate Strategy Returns
    # TQQQ Strategy
    df_res['Strat_TQQQ_Return'] = np.where(df_res[pos_col] == 1, df_res['TQQQ_Return'], df_res['Cash_Return'])
    
    # Calculate Values
    df_res['Strat_TQQQ_Value'] = INITIAL_CAPITAL * (1 + df_res['Strat_TQQQ_Return']).cumprod()
    
    return df_res

def calculate_metrics(series):
    """Calculate basic metrics."""
    series = series.dropna()
    if series.empty: return {}
    
    # CAGR
    years = (series.index[-1] - series.index[0]).days / 365.25
    final_val = series.iloc[-1]
    cagr = (final_val / INITIAL_CAPITAL) ** (1/years) - 1
    
    # Max DD
    running_max = series.cummax()
    dd = (series - running_max) / running_max
    max_dd = dd.min()
    
    return {'CAGR': cagr, 'Max DD': max_dd, 'Final Value': final_val}

def main():
    print("Running Golden Cross Backtest (TQQQ Era)...")
    
    short_windows = [5, 10, 20, 50]
    df = load_data_and_signals(short_windows)
    
    if df is None: return

    results = []
    
    # Benchmarks
    df['BH_TQQQ_Value'] = INITIAL_CAPITAL * (1 + df['TQQQ_Return']).cumprod()
    bh_metrics = calculate_metrics(df['BH_TQQQ_Value'])
    
    # Grid Search Results
    sma_periods = [50, 100, 200]
    results = []

    print("-" * 80)
    print(f"{'Entry (SMA)':<12} {'Exit (SMA)':<12} {'Final Value':>15} {'CAGR':>10} {'Max DD':>10}")
    print("-" * 80)

    for entry_p in sma_periods:
        for exit_p in sma_periods:
            pos_col = f'Pos_In{entry_p}_Out{exit_p}'
            
            # Run Backtest logic
            res = df.copy()
            res['Strat_Return'] = np.where(res[pos_col] == 1, res['TQQQ_Return'], res['Cash_Return'])
            res['Strat_Value'] = INITIAL_CAPITAL * (1 + res['Strat_Return']).cumprod()
            
            m = calculate_metrics(res['Strat_Value'])
            
            print(f"{entry_p:<12} {exit_p:<12} ${m['Final Value']:>14,.0f} {m['CAGR']:>9.2%} {m['Max DD']:>9.2%}")
            
            results.append({
                'Entry': entry_p,
                'Exit': exit_p,
                'Final Value': m['Final Value'],
                'CAGR': m['CAGR'],
                'Max DD': m['Max DD']
            })
            
            # Plot specific interesting cases (e.g., diagonals or best performer)
            # For now, let's just save the plot if it beats the current best (approx check) or just the 200/200 reference
            if entry_p == 200 and exit_p == 200:
                 plt.figure(figsize=(10, 6))
                 plt.plot(res.index, res['Strat_Value'], label=f'GC ({entry_p}/{exit_p})', color='blue')
                 plt.plot(res.index, df['BH_TQQQ_Value'], label='Buy & Hold', color='gray', linestyle='--', alpha=0.5)
                 plt.title(f'Grid Search: Entry {entry_p} / Exit {exit_p}')
                 plt.yscale('log')
                 plt.legend()
                 plt.savefig(os.path.join(PLOTS_DIR, f'grid_{entry_p}_{exit_p}.png'))
                 plt.close()
    
    print("-" * 80)
    
    # Identify Best Performer
    best_res = max(results, key=lambda x: x['Final Value'])
    print(f"\nBEST CONFIGURATION: Entry {best_res['Entry']} / Exit {best_res['Exit']}")
    print(f"Final Value: ${best_res['Final Value']:,.0f} | CAGR: {best_res['CAGR']:.2%} | Max DD: {best_res['Max DD']:.2%}")
   
    # Also print BH for reference
    bh = calculate_metrics(df['BH_TQQQ_Value'])
    print(f"\nReference (Buy & Hold): ${bh['Final Value']:,.0f} | {bh['CAGR']:.2%} | {bh['Max DD']:.2%}")

    # Original LRS (Price > SMA 200)
    # Using pre-calculated column
    df['LRS_Ret'] = np.where(df['LRS_Original_Pos'] == 1, df['TQQQ_Return'], df['Cash_Return'])
    df['LRS_Val'] = INITIAL_CAPITAL * (1 + df['LRS_Ret']).cumprod()
    
    lrs_m = calculate_metrics(df['LRS_Val'])
    results.append({
        'Strategy': 'Original LRS (Price > SMA200)',
        'CAGR': lrs_m['CAGR'],
        'Max DD': lrs_m['Max DD'],
        'Final Value': lrs_m['Final Value']
    })

    # Display Table
    res_df = pd.DataFrame(results).sort_values('Final Value', ascending=False)
    
    print("\n--- Golden Cross Results (2010 - 2025) ---")
    print(res_df.to_string(index=False, formatters={
        'CAGR': '{:.2%}'.format,
        'Max DD': '{:.2%}'.format,
        'Final Value': '${:,.0f}'.format
    }))
    
    res_df.to_csv(os.path.join(RESULTS_DIR, 'golden_cross_summary.csv'), index=False)

if __name__ == "__main__":
    main()
