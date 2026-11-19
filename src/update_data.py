"""
Single downloader for all market data used by the LRS project.

Every CSV in data/ is written through ``download_ohlcv`` and ``save_csv``
so all files share one format:

* columns ``Open, High, Low, Close, Volume`` with a ``Date`` index;
* ``Close`` is dividend/split adjusted (yfinance ``auto_adjust=True``),
  so close-to-close returns are total returns;
* the current session's bar is never saved while the market is open
  (an intraday price is not a close);
* files are replaced atomically, so readers never see a partial file.
"""
import os
import datetime

import pandas as pd
import pytz
import yfinance as yf

# Use absolute path relative to project root (one level up from src/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')

OHLCV_COLUMNS = ['Open', 'High', 'Low', 'Close', 'Volume']
ET = pytz.timezone('America/New_York')
# yfinance's daily bar is treated as final this long after the 16:00 ET close.
BAR_FINAL_TIME = datetime.time(16, 15)

# file name -> (yfinance symbol, start date)
TICKERS = {
    'sp500': ('^GSPC', '1928-01-01'),
    'tqqq': ('TQQQ', '2010-02-09'),
    'ndx': ('^NDX', '1985-01-01'),
    'upro': ('UPRO', '2009-06-25'),
    'vix': ('^VIX', '1990-01-01'),
    'soxl': ('SOXL', '2010-03-11'),
    'shv': ('SHV', '2007-01-01'),
    'tmf': ('TMF', '2009-04-16'),
    'spy': ('SPY', '1993-01-29'),
}


def download_ohlcv(symbol, start):
    """
    Download daily OHLCV bars for one symbol from yfinance.

    Parameters:
    symbol (str): yfinance ticker, e.g. '^GSPC' or 'TQQQ'.
    start (str): First date to request, 'YYYY-MM-DD'.

    Returns:
    pd.DataFrame: Columns Open, High, Low, Close, Volume (Close adjusted
    for splits and dividends), indexed by a naive ``Date`` DatetimeIndex.
    May include the current, still-trading session as its last row.

    Raises:
    ValueError: If yfinance returns no rows (it does not raise on network
    failures or unknown symbols), so callers never save an empty file.
    """
    df = yf.download(symbol, start=start, auto_adjust=True,
                     multi_level_index=False, progress=False)
    if df is None or df.empty:
        raise ValueError(f"yfinance returned no data for {symbol}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[OHLCV_COLUMNS].ffill()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = 'Date'
    return df


def last_bar_is_final(df, now=None):
    """
    Tell whether the last row of ``df`` is a completed daily bar.

    A bar dated today (US/Eastern) is only final once the market has
    closed; earlier rows are always final.

    Parameters:
    df (pd.DataFrame): Daily bars indexed by date.
    now (datetime, optional): Current time; defaults to now in US/Eastern.
    Naive values are taken as US/Eastern.

    Returns:
    bool: True if the last bar is a final close.
    """
    if df.empty:
        return True
    now = now or datetime.datetime.now(ET)
    if now.tzinfo is None:
        now = ET.localize(now)
    now = now.astimezone(ET)
    last_date = pd.Timestamp(df.index[-1]).date()
    if last_date < now.date():
        return True
    return now.time() >= BAR_FINAL_TIME


def drop_incomplete_bar(df, now=None):
    """
    Remove the last row if it is today's still-trading session.

    Parameters:
    df (pd.DataFrame): Daily bars indexed by date.
    now (datetime, optional): Current time, see ``last_bar_is_final``.

    Returns:
    pd.DataFrame: ``df`` with only completed bars.
    """
    if last_bar_is_final(df, now):
        return df
    return df.iloc[:-1]


def save_csv(df, path, now=None):
    """
    Save completed bars to ``path`` atomically.

    Writes to a temporary file in the same directory and renames it over
    the target, so a concurrent reader sees either the old or the new
    file, never a half-written one.

    Parameters:
    df (pd.DataFrame): Daily bars indexed by date.
    path (str): Destination CSV path.
    now (datetime, optional): Current time, see ``last_bar_is_final``.

    Raises:
    ValueError: If there is nothing to save.
    """
    df = drop_incomplete_bar(df, now).rename_axis('Date')
    if df.empty:
        raise ValueError(f"refusing to write empty data to {path}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp{os.getpid()}"
    df.to_csv(tmp_path)
    os.replace(tmp_path, path)


def update_ticker(name):
    """
    Download one ticker from ``TICKERS`` and save it to data/<name>.csv.

    Parameters:
    name (str): Key in ``TICKERS``, e.g. 'sp500'.

    Returns:
    pd.DataFrame: The downloaded bars (including any intraday bar).
    """
    symbol, start = TICKERS[name]
    print(f"Downloading {symbol} from {start}...")
    df = download_ohlcv(symbol, start)
    path = os.path.join(DATA_DIR, f'{name}.csv')
    save_csv(df, path)
    print(f"Saved {name}.csv. Last completed date: "
          f"{drop_incomplete_bar(df).index[-1].date()}")
    return df


def update_data():
    """Download every ticker in ``TICKERS``; report failures and continue."""
    failed = []
    for name in TICKERS:
        try:
            update_ticker(name)
        except Exception as e:
            print(f"ERROR updating {name}: {e}")
            failed.append(name)
    if failed:
        print(f"Failed: {', '.join(failed)} (existing files left unchanged)")


if __name__ == "__main__":
    update_data()
