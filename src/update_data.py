import yfinance as yf
import pandas as pd
import os
import datetime

# Use absolute path relative to project root (one level up from src/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def update_data():
    # Set end_date to tomorrow to ensure we capture today's data if available
    end_date = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    start_date = '1928-01-01'
    
    # 1. S&P 500
    print(f"Downloading S&P 500 (^GSPC) from {start_date} to {end_date}...")
    print(f"Downloading S&P 500 (^GSPC) from {start_date} to {end_date}...")
    sp500 = yf.download('^GSPC', start=start_date, end=end_date, auto_adjust=False, multi_level_index=False)
    # yfinance often returns MultiIndex columns in recent versions, specific fix might be needed
    if isinstance(sp500.columns, pd.MultiIndex):
        sp500.columns = sp500.columns.get_level_values(0)
    sp500.to_csv(os.path.join(DATA_DIR, 'sp500.csv'))
    print(f"Saved sp500.csv. Last date: {sp500.index[-1]}")

    # 2. TQQQ
    print(f"Downloading TQQQ from {start_date} to {end_date}...")
    print(f"Downloading TQQQ from {start_date} to {end_date}...")
    tqqq = yf.download('TQQQ', start='2010-02-09', end=end_date, auto_adjust=False, multi_level_index=False)
    if isinstance(tqqq.columns, pd.MultiIndex):
        tqqq.columns = tqqq.columns.get_level_values(0)
    tqqq.to_csv(os.path.join(DATA_DIR, 'tqqq.csv'))
    print(f"Saved tqqq.csv. Last date: {tqqq.index[-1]}")
    
    # 3. NASDAQ 100 (NDX) - Optional but good for reference
    print("Downloading NASDAQ 100 (^NDX)...")
    print("Downloading NASDAQ 100 (^NDX)...")
    ndx = yf.download('^NDX', start='1985-01-01', end=end_date, auto_adjust=False, multi_level_index=False)
    if isinstance(ndx.columns, pd.MultiIndex):
        ndx.columns = ndx.columns.get_level_values(0)
    ndx.to_csv(os.path.join(DATA_DIR, 'ndx.csv'))

    # 4. UPRO (Simulated) - Optional
    print("Downloading UPRO...")
    print("Downloading UPRO...")
    upro = yf.download('UPRO', start='2009-06-25', end=end_date, auto_adjust=False, multi_level_index=False)
    if isinstance(upro.columns, pd.MultiIndex):
         upro.columns = upro.columns.get_level_values(0)
    upro.to_csv(os.path.join(DATA_DIR, 'upro.csv'))

    # 5. VIX (Volatility Index)
    print("Downloading VIX (^VIX)...")
    vix = yf.download('^VIX', start='1990-01-01', end=end_date, auto_adjust=False, multi_level_index=False)
    if isinstance(vix.columns, pd.MultiIndex):
         vix.columns = vix.columns.get_level_values(0)
    vix.to_csv(os.path.join(DATA_DIR, 'vix.csv'))
    print(f"Saved vix.csv. Last date: {vix.index[-1]}")

if __name__ == "__main__":
    update_data()
