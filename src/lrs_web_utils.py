import pandas as pd
import numpy as np
import os
from datetime import datetime, time
import pytz
import yfinance as yf
from lrs_hybrid_sniper import calculate_rsi, calculate_signals_sniper, calculate_returns

# Use absolute path relative to project root (one level up from src/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
INITIAL_CAPITAL = 10000
RISK_FREE_RATE = 0.03

def download_fresh_data():
    """
    Download fresh data from yfinance for all required symbols.
    If market is open, current price is treated as 'close'.
    Returns dict of dataframes.
    """
    print("[REFRESH] Downloading fresh data from yfinance...")
    
    # Download S&P 500
    sp500 = yf.download('^GSPC', start='2000-01-01', progress=False, auto_adjust=False)
    if isinstance(sp500.columns, pd.MultiIndex):
        sp500.columns = sp500.columns.get_level_values(0)
    sp500 = sp500.ffill().bfill()
    
    # Download TQQQ
    tqqq = yf.download('TQQQ', start='2010-02-09', progress=False, auto_adjust=False)
    if isinstance(tqqq.columns, pd.MultiIndex):
        tqqq.columns = tqqq.columns.get_level_values(0)
    tqqq = tqqq.ffill().bfill()
    
    # Download VIX
    vix = yf.download('^VIX', start='2000-01-01', progress=False, auto_adjust=False)
    if isinstance(vix.columns, pd.MultiIndex):
        vix.columns = vix.columns.get_level_values(0)
    vix = vix.ffill().bfill()
    
    print(f"[REFRESH] SP500 last date: {sp500.index[-1]}, TQQQ last date: {tqqq.index[-1]}")
    
    return {
        'sp500': sp500,
        'tqqq': tqqq,
        'vix': vix
    }

def get_hybrid_sniper_data(force_refresh=False):
    """
    Load data, calculate Hybrid Sniper signals, and return a DataFrame 
    ready for visualization in the Web Dashboard.
    
    If force_refresh=True, download fresh data from yfinance.
    """
    if force_refresh:
        # Download fresh data from yfinance
        data = download_fresh_data()
        df = data['sp500'].copy()
        tqqq = data['tqqq']
        vix = data['vix']
        
        # Save to CSV for future use
        df.to_csv(os.path.join(DATA_DIR, 'sp500.csv'))
        tqqq.to_csv(os.path.join(DATA_DIR, 'tqqq.csv'))
        vix.to_csv(os.path.join(DATA_DIR, 'vix.csv'))
    else:
        # Load from CSV files
        sp500_path = os.path.join(DATA_DIR, 'sp500.csv')
        tqqq_path = os.path.join(DATA_DIR, 'tqqq.csv')
        
        if os.path.exists(sp500_path) and os.path.exists(tqqq_path):
            df = pd.read_csv(sp500_path, index_col=0, parse_dates=True)
            tqqq = pd.read_csv(tqqq_path, index_col=0, parse_dates=True)
        else:
            # Fallback to fresh download
            return get_hybrid_sniper_data(force_refresh=True)
        
    # Align Data
    common_idx = df.index.intersection(tqqq.index)
    df = df.loc[common_idx].copy()
    
    # Preserve Real Prices for Plotting
    df['TQQQ_Close'] = tqqq['Close'].reindex(df.index)
    
    # TQQQ Returns
    tqqq_returns = tqqq['Close'].pct_change()
    tqqq_returns = tqqq_returns.reindex(df.index)
    df['TQQQ_Returns'] = tqqq_returns

    # Calculate Hybrid Sniper Signals
    # This adds: SMA_200, MA_10, RSI, Regime, Signal
    df = calculate_signals_sniper(df)
    
    # Calculate Strategy Returns
    df['Cash_Return'] = RISK_FREE_RATE / 252
    signal = df['Signal'].fillna(0)
    tqqq_r = df['TQQQ_Returns'].fillna(0)
    cash_r = df['Cash_Return']
    
    df['LRS_Sniper_Return'] = signal * tqqq_r + (1 - signal) * cash_r
    
    # Cumulative Values
    df['LRS_Sniper_Value'] = INITIAL_CAPITAL * (1 + df['LRS_Sniper_Return']).cumprod()
    df['BH_TQQQ_Value'] = INITIAL_CAPITAL * (1 + df['TQQQ_Returns']).cumprod()
    
    # Filter for display (2010 onwards)
    df = df[df.index >= '2010-01-01']
    
    return df

def get_latest_signals(df):
    """Return the most recent signal status for the dashboard header."""
    last_row = df.iloc[-1]
    
    # Load VIX data
    vix_path = os.path.join(DATA_DIR, 'vix.csv')
    vix_value = None
    if os.path.exists(vix_path):
        vix_df = pd.read_csv(vix_path, index_col=0, parse_dates=True)
        if not vix_df.empty:
            vix_value = vix_df['Close'].iloc[-1]
    
    status = {
        'date': df.index[-1].strftime('%Y-%m-%d'),
        'price': last_row['Close'],
        'tqqq_price': last_row['TQQQ_Close'],
        'sma_200': last_row['SMA_200'],
        'ma_10': last_row['MA_10'],
        'rsi': last_row['RSI'],
        'vix': vix_value,
        'signal_alloc': last_row['Signal'],
        'regime': last_row['Regime'],
        'trend_signal': "BULL" if last_row['Close'] > last_row['SMA_200'] else "BEAR",
        'sniper_signal': "OVERSOLD" if last_row['RSI'] < 30 else "NEUTRAL"
    }
    
    # Determine Mode Text
    if status['signal_alloc'] == 1.0:
        status['mode'] = "TREND MODE (100% TQQQ)"
        status['mode_class'] = "mode-bull"
    elif status['signal_alloc'] == 0.5:
        status['mode'] = "SNIPER MODE (50% TQQQ)"
        status['mode_class'] = "mode-sniper"
    else:
        status['mode'] = "CASH / RISK-OFF"
        status['mode_class'] = "mode-cash"
        
    return status
