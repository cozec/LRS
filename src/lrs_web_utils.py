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

def should_fetch_live_data():
    """
    Check if we should fetch live/latest data.
    Returns True if it is a weekday AND time is >= 9:30 AM ET.
    This allows fetching live data during market hours AND closing data after market close.
    """
    et_tz = pytz.timezone('America/New_York')
    now = datetime.now(et_tz)
    
    # Check if it's a weekday
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    
    # Market Open: 9:30 AM ET
    market_open = time(9, 30)
    current_time = now.time()
    
    # Allow fetching if time >= 9:30 AM
    return current_time >= market_open

def fetch_live_prices():
    """Fetch current SPX, TQQQ and VIX prices from Yahoo Finance using history() for reliability.
    Returns OHLC data for candlestick chart compatibility.
    """
    try:
        # Use history() method which is more reliable than fast_info
        spx = yf.Ticker("^GSPC")
        tqqq = yf.Ticker("TQQQ")
        vix = yf.Ticker("^VIX")
        
        # Get last 2 days of data to ensure we have today's price
        spx_hist = spx.history(period='2d')
        tqqq_hist = tqqq.history(period='2d')
        vix_hist = vix.history(period='2d')
        
        if not spx_hist.empty and not tqqq_hist.empty:
            # Get the latest row (today's data if market is open)
            latest_spx = spx_hist.iloc[-1]
            latest_tqqq = tqqq_hist.iloc[-1]
            latest_vix = vix_hist.iloc[-1] if not vix_hist.empty else None
            
            return {
                'spx_open': latest_spx['Open'],
                'spx_high': latest_spx['High'],
                'spx_low': latest_spx['Low'],
                'spx_close': latest_spx['Close'],
                'tqqq': latest_tqqq['Close'],
                'vix': latest_vix['Close'] if latest_vix is not None else None,
                'date': spx_hist.index[-1].normalize(),  # Get the date without time
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

    # === LIVE DATA APPEND/UPDATE (if market is open or closed today) ===
    if should_fetch_live_data():
        live = fetch_live_prices()
        if live:
            # Normalize to tz-naive for comparison with CSV data
            live_date = live['date'].tz_localize(None) if live['date'].tzinfo else live['date']
            last_date = df.index[-1].tz_localize(None) if df.index[-1].tzinfo else df.index[-1]
            
            # Check if we need to append or update
            if live_date > last_date:
                # Append new row for today
                new_row = pd.DataFrame({
                    'Open': [live['spx_open']],
                    'High': [live['spx_high']],
                    'Low': [live['spx_low']],
                    'Close': [live['spx_close']],
                    'TQQQ_Close': [live['tqqq']],
                }, index=[live_date])
                
                # Calculate returns from previous close
                prev_tqqq = df['TQQQ_Close'].iloc[-1]
                new_row['TQQQ_Returns'] = (live['tqqq'] - prev_tqqq) / prev_tqqq
                
                # Append to dataframe
                df = pd.concat([df, new_row])
                print(f"[LIVE] Appended today's data: SPX={live['spx_close']:.2f}, TQQQ={live['tqqq']:.2f}")
            elif live_date == last_date:
                # Update today's row with latest intraday data
                df.loc[live_date, 'Open'] = live['spx_open']
                df.loc[live_date, 'High'] = max(df.loc[live_date, 'High'], live['spx_high']) if pd.notna(df.loc[live_date, 'High']) else live['spx_high']
                df.loc[live_date, 'Low'] = min(df.loc[live_date, 'Low'], live['spx_low']) if pd.notna(df.loc[live_date, 'Low']) else live['spx_low']
                df.loc[live_date, 'Close'] = live['spx_close']
                df.loc[live_date, 'TQQQ_Close'] = live['tqqq']
                print(f"[LIVE] Updated today's data: SPX={live['spx_close']:.2f}, TQQQ={live['tqqq']:.2f}")

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
        'rsi': last_row['RSI'],
        'vix': vix_value,  # Add VIX value
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
