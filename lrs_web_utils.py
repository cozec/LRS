import pandas as pd
import numpy as np
import os
from datetime import datetime, time
import pytz
import yfinance as yf
from lrs_hybrid_sniper import calculate_rsi, calculate_signals_sniper, calculate_returns

DATA_DIR = 'data'
INITIAL_CAPITAL = 10000
RISK_FREE_RATE = 0.03

def is_market_open():
    """Check if US stock market is currently open (9:30 AM - 4:00 PM ET, weekdays)."""
    et_tz = pytz.timezone('America/New_York')
    now = datetime.now(et_tz)
    
    # Check if it's a weekday
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    # Market hours: 9:30 AM - 4:00 PM ET
    market_open = time(9, 30)
    market_close = time(16, 0)
    current_time = now.time()
    
    return market_open <= current_time <= market_close

def fetch_live_prices():
    """Fetch current SPX and TQQQ prices from Yahoo Finance."""
    try:
        spx = yf.Ticker("^GSPC")
        tqqq = yf.Ticker("TQQQ")
        
        spx_price = spx.fast_info.get('lastPrice', None)
        tqqq_price = tqqq.fast_info.get('lastPrice', None)
        
        if spx_price and tqqq_price:
            return {
                'spx': spx_price,
                'tqqq': tqqq_price,
                'timestamp': datetime.now()
            }
    except Exception as e:
        print(f"Error fetching live prices: {e}")
    return None

def get_hybrid_sniper_data():
    """
    Load data, calculate Hybrid Sniper signals, and return a DataFrame 
    ready for visualization in the Web Dashboard.
    """
    sp500_path = os.path.join(DATA_DIR, 'sp500.csv')
    tqqq_path = os.path.join(DATA_DIR, 'tqqq.csv')
    upro_path = os.path.join(DATA_DIR, 'upro.csv')
    ndx_path = os.path.join(DATA_DIR, 'ndx.csv')
    
    if os.path.exists(sp500_path) and os.path.exists(tqqq_path):
        df = pd.read_csv(sp500_path, index_col=0, parse_dates=True)
        tqqq = pd.read_csv(tqqq_path, index_col=0, parse_dates=True)
        upro = pd.read_csv(upro_path, index_col=0, parse_dates=True)
        ndx = pd.read_csv(ndx_path, index_col=0, parse_dates=True)
    else:
        raise FileNotFoundError("Data files not found. Please run backtest first to download data.")
        
    # Align Data
    common_idx = df.index.intersection(tqqq.index)
    df = df.loc[common_idx].copy()
    
    # Preserve Real Prices for Plotting
    # Reindex TQQQ and UPRO Close to match df index
    df['TQQQ_Close'] = tqqq['Close'].reindex(df.index)
    
    # TQQQ Returns
    tqqq_returns = tqqq['Close'].pct_change()
    tqqq_returns = tqqq_returns.reindex(df.index)
    df['TQQQ_Returns'] = tqqq_returns
    
    # UPRO Returns (if needed)
    upro_returns = upro['Close'].pct_change()
    upro_returns = upro_returns.reindex(df.index)
    df['UPRO_Returns'] = upro_returns

    # === LIVE DATA APPEND (if market is open) ===
    if is_market_open():
        live = fetch_live_prices()
        if live:
            today = pd.Timestamp.now().normalize()  # Today's date at midnight
            last_date = df.index[-1]
            
            # Only append if today's data doesn't exist yet
            if today > last_date:
                # Create a new row with live prices
                new_row = pd.DataFrame({
                    'Close': [live['spx']],
                    'TQQQ_Close': [live['tqqq']],
                }, index=[today])
                
                # Calculate returns from previous close
                prev_spx = df['Close'].iloc[-1]
                prev_tqqq = df['TQQQ_Close'].iloc[-1]
                new_row['TQQQ_Returns'] = (live['tqqq'] - prev_tqqq) / prev_tqqq
                
                # Append to dataframe
                df = pd.concat([df, new_row])
                print(f"[LIVE] Appended today's data: SPX={live['spx']:.2f}, TQQQ={live['tqqq']:.2f}")

    # Calculate Hybrid Sniper Signals
    # This adds: SMA_200, MA_10, RSI, Regime, Signal
    df = calculate_signals_sniper(df)
    
    # Calculate Strategy Returns
    # Note: calculate_returns in lrs_hybrid_sniper expects 'Regime' to be processed
    # But wait, run_comparison does custom calculation for Sniper Return using Signal (0.0/0.5/1.0)
    # calculate_returns in lrs_hybrid_sniper uses Regime (0/1) for Standard LRS logic?
    # Let's verify lrs_hybrid_sniper.py logic again. 
    # run_comparison lines 597-606 manually calculate LRS_Sniper_Return using Signal * TQQQ + (1-Signal) * Cash.
    # calculate_returns uses Regime.shift(1).
    # Since calculate_signals_sniper sets Regime and Signal, we should replicate run_comparison's return logic.
    
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
    prev_row = df.iloc[-2]
    
    status = {
        'date': df.index[-1].strftime('%Y-%m-%d'),
        'price': last_row['Close'],
        'sma_200': last_row['SMA_200'],
        'rsi': last_row['RSI'],
        'signal_alloc': last_row['Signal'], # 0.0, 0.5, 1.0
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
