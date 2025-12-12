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
        
        # Calculate Signals on FULL history
        df['SMA_200'] = df['Close'].rolling(200).mean()
        
        # Calculate metrics for all windows
        for n in short_windows:
            sma_col = f'SMA_{n}'
            df[sma_col] = df['Close'].rolling(n).mean()
            
            # 1. Standard Signal: Short > Long
            sig_col = f'Signal_{n}'
            df[sig_col] = np.where(df[sma_col] > df['SMA_200'], 1, 0)
            
            # Position
            pos_col = f'Pos_{n}'
            df[pos_col] = df[sig_col].shift(1)
            
            # 2. Buffered Signal (Optimize for n=10)
            if n == 10:
                buffers = [0.01, 0.02, 0.03, 0.04, 0.05] # Testing range
                
                for buf in buffers:
                    upper = df['SMA_200'] * (1 + buf)
                    lower = df['SMA_200'] * (1 - buf)
                    
                    buf_sig_col = f'Signal_{n}_Buf_{buf}'
                    buf_pos_col = f'Pos_{n}_Buf_{buf}'
                    
                    # Hysteresis Logic
                    signals = []
                    state = 0 # Default Risk-Off
                    
                    # Convert to numpy for speed
                    ma_vals = df[sma_col].values
                    up_vals = upper.values
                    low_vals = lower.values
                    
                    for i in range(len(df)):
                        val = ma_vals[i]
                        if np.isnan(val):
                            signals.append(0)
                            continue
                            
                        if val > up_vals[i]:
                            state = 1
                        elif val < low_vals[i]:
                            state = 0
                        # else keep state
                        signals.append(state)
                    
                    df[buf_sig_col] = signals
                    df[buf_pos_col] = df[buf_sig_col].shift(1)

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
    results.append({
        'Strategy': 'Buy & Hold TQQQ',
        'CAGR': bh_metrics['CAGR'],
        'Max DD': bh_metrics['Max DD'],
        'Final Value': bh_metrics['Final Value']
    })
    
    for n in short_windows:
        res_df = run_backtest(df, n)
        
        # TQQQ Metrics
        m = calculate_metrics(res_df['Strat_TQQQ_Value'])
        results.append({
            'Strategy': f'Golden Cross ({n}/200) TQQQ',
            'CAGR': m['CAGR'],
            'Max DD': m['Max DD'],
            'Final Value': m['Final Value']
        })
        
        # Plotting
        plt.figure(figsize=(10, 6))
        plt.plot(res_df.index, res_df['Strat_TQQQ_Value'], label=f'GC {n}/200', color='blue')
        plt.plot(res_df.index, df['BH_TQQQ_Value'], label='Buy & Hold', color='gray', linestyle='--', alpha=0.5)
        plt.title(f'Golden Cross ({n}/200) vs Buy & Hold (TQQQ)')
        plt.yscale('log')
        plt.legend()
        plt.savefig(os.path.join(PLOTS_DIR, f'golden_cross_{n}_tqqq.png'))
        plt.close()
        
    # Buffered 10/200 Runs
    n_buf = 10
    buffers = [0.01, 0.02, 0.03, 0.04, 0.05]
    
    for buf in buffers:
        res_buf = run_backtest(df, n_buf, buffer_val=buf)
        m_buf = calculate_metrics(res_buf['Strat_TQQQ_Value'])
        results.append({
            'Strategy': f'GC ({n_buf}/200) + {int(buf*100)}% Buffer',
            'CAGR': m_buf['CAGR'],
            'Max DD': m_buf['Max DD'],
            'Final Value': m_buf['Final Value']
        })
        
        # Plot Buffered
        plt.figure(figsize=(10, 6))
        plt.plot(res_buf.index, res_buf['Strat_TQQQ_Value'], label=f'GC {n_buf}/200 + {int(buf*100)}% Buffer', color='green')
        plt.plot(res_buf.index, df['BH_TQQQ_Value'], label='Buy & Hold', color='gray', linestyle='--', alpha=0.5)
        plt.title(f'Golden Cross ({n_buf}/200) + {int(buf*100)}% Buffer vs Buy & Hold')
        plt.yscale('log')
        plt.legend()
        plt.savefig(os.path.join(PLOTS_DIR, f'golden_cross_{n_buf}_buffer_{int(buf*100)}_tqqq.png'))
        plt.close()

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
