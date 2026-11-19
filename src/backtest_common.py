"""
Shared backtest mechanics for the reported LRS backtests.

Conventions (see summary.md, "Backtest Conventions"):

* ``weight[t]`` is the allocation *decided* at the close of day t from
  data up to and including that close.
* Primary fill: **next open**. The decision at close t-1 is filled at the
  open of day t. Day t's return is the overnight leg (close t-1 -> open t)
  at the weight held overnight, then the intraday leg (open t -> close t)
  at the newly filled weight. The trade is sized from the portfolio marked
  at that open, never from a later close.
* Comparison fill: **market-on-close (MOC)**, labeled as such: the
  decision at close t-1 is filled at close t-1, so day t earns the full
  close-to-close return at that weight.
* The un-invested fraction earns ``RISK_FREE_RATE`` (flat, applied on the
  overnight leg). A fractional weight (e.g. 0.5) is rebalanced at each
  fill. No commissions or slippage.
* Every backtest starts with ``INITIAL_CAPITAL`` in cash at the first
  close of the window. Buy & hold equity is exactly
  ``INITIAL_CAPITAL * close / first_close``.
"""
import os

import numpy as np
import pandas as pd

INITIAL_CAPITAL = 10000
RISK_FREE_RATE = 0.03
TRADING_DAYS = 252

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results')
PLOTS_DIR = os.path.join(PROJECT_ROOT, 'plots')

LEVEL_TYPES = {1.0: 'Trend (SMA)', 0.5: 'Sniper (RSI)'}


def load_ohlcv(name):
    """
    Load data/<name>.csv as written by update_data.py.

    Parameters:
    name (str): File stem, e.g. 'sp500'.

    Returns:
    pd.DataFrame: OHLCV bars indexed by Date, sorted ascending.
    """
    df = pd.read_csv(os.path.join(DATA_DIR, f'{name}.csv'),
                     index_col=0, parse_dates=True)
    return df.sort_index()


def held_weights(weight):
    """
    Weights actually held during each day under next-open fills.

    Parameters:
    weight (pd.Series): Allocation decided at each close.

    Returns:
    tuple: (overnight, session) Series. ``session[t]`` is filled at the
    open of day t (= decision at close t-1); ``overnight[t]`` is the weight
    carried from close t-1 to open t. Both are 0 before the first decision
    inside the window, because the backtest starts in cash.
    """
    session = weight.shift(1).fillna(0.0)
    session.iloc[0] = 0.0
    overnight = session.shift(1).fillna(0.0)
    return overnight, session


def strategy_returns(weight, asset_open, asset_close, fill='next_open',
                     cash_rate=RISK_FREE_RATE):
    """
    Daily strategy returns for a weight series traded in one asset.

    Parameters:
    weight (pd.Series): Allocation decided at each close (0..1).
    asset_open (pd.Series): Asset open prices on the same index.
    asset_close (pd.Series): Asset close prices on the same index.
    fill (str): 'next_open' (primary) or 'moc' (market-on-close).
    cash_rate (float): Annual return on the un-invested fraction.

    Returns:
    pd.Series: Daily returns; the first day is 0 (start in cash at close).
    """
    cash = cash_rate / TRADING_DAYS
    overnight_w, session_w = held_weights(weight)
    if fill == 'moc':
        # Decision at close t-1 filled at close t-1: weight for day t is session_w
        asset_ret = asset_close.pct_change()
        ret = session_w * asset_ret + (1 - session_w) * cash
    elif fill == 'next_open':
        gap = asset_open / asset_close.shift(1) - 1
        intraday = asset_close / asset_open - 1
        ret = (1 + overnight_w * gap + (1 - overnight_w) * cash) * \
              (1 + session_w * intraday) - 1
    else:
        raise ValueError(f"unknown fill convention: {fill}")
    ret.iloc[0] = 0.0
    return ret


def equity_curve(returns):
    """
    Compound daily returns into an equity curve starting at INITIAL_CAPITAL.

    Parameters:
    returns (pd.Series): Daily returns with 0 on the first day.

    Returns:
    pd.Series: Portfolio value at each close.
    """
    return INITIAL_CAPITAL * (1 + returns).cumprod()


def buy_hold_equity(close):
    """
    Buy & hold equity: INITIAL_CAPITAL * close / first_close.

    Parameters:
    close (pd.Series): Asset close prices over the backtest window.

    Returns:
    pd.Series: Buy & hold value at each close.
    """
    return INITIAL_CAPITAL * close / close.iloc[0]


def performance_metrics(values, returns, bench_returns, spx_returns,
                        rf=RISK_FREE_RATE):
    """
    Professional metrics for one equity curve.

    Alpha and beta are Jensen's: beta from daily-return covariance, alpha
    from annualized returns over ``rf``.

    Parameters:
    values (pd.Series): Equity curve (starts at INITIAL_CAPITAL).
    returns (pd.Series): Daily strategy returns (first day 0).
    bench_returns (pd.Series): Daily returns of the traded asset (B&H).
    spx_returns (pd.Series): Daily returns of the S&P 500.
    rf (float): Annual risk-free rate.

    Returns:
    dict: Final_Value, Total_Return, CAGR, Max_Drawdown, Volatility,
    Sharpe, Sortino, Calmar, Worst_Day, Beta/Alpha vs the asset and vs
    the S&P 500.
    """
    r = returns.iloc[1:]
    years = (values.index[-1] - values.index[0]).days / 365.25
    final_value = values.iloc[-1]
    total_return = final_value / values.iloc[0] - 1
    cagr = (final_value / values.iloc[0]) ** (1 / years) - 1

    drawdown = values / values.cummax() - 1
    max_dd = drawdown.min()

    volatility = r.std() * np.sqrt(TRADING_DAYS)
    excess = r - rf / TRADING_DAYS
    sharpe = excess.mean() * TRADING_DAYS / volatility if volatility > 0 else 0.0
    downside = r[r < 0].std() * np.sqrt(TRADING_DAYS)
    sortino = excess.mean() * TRADING_DAYS / downside if downside > 0 else 0.0
    calmar = cagr / abs(max_dd) if max_dd != 0 else 0.0

    def ann(x):
        return (1 + x).prod() ** (TRADING_DAYS / len(x)) - 1

    def jensen(bench):
        pair = pd.DataFrame({'s': r, 'b': bench.iloc[1:]}).dropna()
        cov = np.cov(pair['s'], pair['b'])
        beta = cov[0, 1] / cov[1, 1] if cov[1, 1] != 0 else 0.0
        alpha = (ann(pair['s']) - rf) - beta * (ann(pair['b']) - rf)
        return beta, alpha

    beta_bh, alpha_bh = jensen(bench_returns)
    beta_spx, alpha_spx = jensen(spx_returns)

    return {
        'Final_Value': final_value,
        'Total_Return': total_return,
        'CAGR': cagr,
        'Max_Drawdown': max_dd,
        'Volatility': volatility,
        'Sharpe': sharpe,
        'Sortino': sortino,
        'Calmar': calmar,
        'Worst_Day': r.min(),
        'Beta_BH': beta_bh,
        'Alpha_BH': alpha_bh,
        'Beta_SPX': beta_spx,
        'Alpha_SPX': alpha_spx,
    }


def _exit_reason(old, new):
    """Describe why a position at level ``old`` changed to ``new``."""
    if old == 1.0:
        return 'SMA break' if new == 0.0 else 'SMA break -> Sniper'
    if new == 1.0:
        return 'Promoted to Trend'
    return 'RSI target'


def trade_log(weight, returns, asset_open, asset_close, level_types=None):
    """
    List trades under next-open fills; a new trade starts at any change in
    the held allocation (e.g. Trend 1.0 -> Sniper 0.5 closes one trade and
    opens another).

    Entry and exit dates are fill dates (the open after the deciding
    close). Returns are fill-to-fill: strategy equity at the exit open over
    equity at the entry open, and asset open-to-open. A trade still held
    at the end is marked OPEN and valued at the last close.

    Parameters:
    weight (pd.Series): Allocation decided at each close.
    returns (pd.Series): Next-open strategy returns from ``strategy_returns``.
    asset_open (pd.Series): Asset open prices.
    asset_close (pd.Series): Asset close prices.
    level_types (dict, optional): Allocation level -> trade type label.

    Returns:
    pd.DataFrame: Entry_Date, Exit_Date, Duration_Days, Type, Allocation,
    Status, Exit_Reason, Return_Strategy, Return_Asset.
    """
    level_types = level_types or LEVEL_TYPES
    overnight_w, session_w = held_weights(weight)
    equity = equity_curve(returns)
    prev_equity = equity.shift(1).fillna(INITIAL_CAPITAL)
    gap = (asset_open / asset_close.shift(1) - 1).fillna(0.0)
    cash = RISK_FREE_RATE / TRADING_DAYS
    equity_at_open = prev_equity * (1 + overnight_w * gap + (1 - overnight_w) * cash)

    trades = []
    levels = session_w.values
    dates = session_w.index
    start = None
    for i in range(len(levels)):
        prev = levels[i - 1] if i > 0 else 0.0
        if levels[i] == prev:
            continue
        if start is not None:
            trades.append(_make_trade(start, i, prev, levels[i], dates,
                                      equity_at_open, asset_open, level_types))
            start = None
        if levels[i] > 0:
            start = i
    if start is not None:
        level = levels[start]
        entry = dates[start]
        exit_date = dates[-1]
        trades.append({
            'Entry_Date': entry.date(),
            'Exit_Date': exit_date.date(),
            'Duration_Days': (exit_date - entry).days,
            'Type': level_types.get(level, f'{level:.0%}'),
            'Allocation': level,
            'Status': 'OPEN',
            'Exit_Reason': 'Still open',
            'Return_Strategy': equity.iloc[-1] / equity_at_open.iloc[start] - 1,
            'Return_Asset': asset_close.iloc[-1] / asset_open.iloc[start] - 1,
        })
    return pd.DataFrame(trades)


def _make_trade(start, end, level, new_level, dates, equity_at_open,
                asset_open, level_types):
    """Build one closed-trade record filled at the opens of start and end."""
    return {
        'Entry_Date': dates[start].date(),
        'Exit_Date': dates[end].date(),
        'Duration_Days': (dates[end] - dates[start]).days,
        'Type': level_types.get(level, f'{level:.0%}'),
        'Allocation': level,
        'Status': 'CLOSED',
        'Exit_Reason': _exit_reason(level, new_level),
        'Return_Strategy': equity_at_open.iloc[end] / equity_at_open.iloc[start] - 1,
        'Return_Asset': asset_open.iloc[end] / asset_open.iloc[start] - 1,
    }
