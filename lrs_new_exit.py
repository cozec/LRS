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
        
        # Calculate 100-day SMA for Exit
        df['SMA_100'] = df['Close'].rolling(100).mean()

        # Asymmetric Strategy Scan
        # Entry: MA_10 > SMA_200 * (1 + BUFFER)
        # Exit:  MA_10 < SMA_100
        
        n = 10 
        buf = 0.02
        sma_col = f'SMA_{n}'
        df[sma_col] = df['Close'].rolling(n).mean()
        
        upper = df['SMA_200'] * (1 + buf)
        # No lower buffer needed for entry, logic is separate
        
        asym_sig_col = f'Signal_Asym'
        asym_pos_col = f'Pos_Asym'
        
        signals = []
        state = 0 # Default Risk-Off
        
        ma_vals = df[sma_col].values
        sma200_vals = df['SMA_200'].values
        sma100_vals = df['SMA_100'].values
        up_vals = upper.values
        
        for i in range(len(df)):
            val = ma_vals[i]
            s200 = sma200_vals[i]
            s100 = sma100_vals[i]
            
            if np.isnan(val) or np.isnan(s200) or np.isnan(s100):
                signals.append(0)
                continue
                
            if state == 0: # Checks for Entry
                if val > up_vals[i]:
                    state = 1
            elif state == 1: # Checks for Exit
                if val < s100:
                    state = 0
            
            signals.append(state)
        
        df[asym_sig_col] = signals
        df[asym_pos_col] = df[asym_sig_col].shift(1)

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
    
    # Asymmetric Strategy Run
    # run_backtest expects a pos_col name or generic column
    
    # Actually, let's just make a small helper or manually do it here since it's one run
    res_asym = df.copy()
    res_asym['Strat_TQQQ_Return'] = np.where(res_asym['Pos_Asym'] == 1, res_asym['TQQQ_Return'], res_asym['Cash_Return'])
    res_asym['Strat_TQQQ_Value'] = INITIAL_CAPITAL * (1 + res_asym['Strat_TQQQ_Return']).cumprod()
    
    m_asym = calculate_metrics(res_asym['Strat_TQQQ_Value'])
    results.append({
        'Strategy': 'Asym (Entry:10/200+2%, Exit:10/100)',
        'CAGR': m_asym['CAGR'],
        'Max DD': m_asym['Max DD'],
        'Final Value': m_asym['Final Value']
    })

    # Plot
    plt.figure(figsize=(10, 6))
    plt.plot(res_asym.index, res_asym['Strat_TQQQ_Value'], label='Asymmetric Exit', color='green')
    plt.plot(res_asym.index, df['BH_TQQQ_Value'], label='Buy & Hold', color='gray', linestyle='--', alpha=0.5)
    plt.title('Asymmetric Exit Strategy (Entry: MA10 > SMA200+2%, Exit: MA10 < SMA100)')
    plt.yscale('log')
    plt.legend()
    plt.savefig(os.path.join(PLOTS_DIR, 'asym_exit_tqqq.png'))
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
