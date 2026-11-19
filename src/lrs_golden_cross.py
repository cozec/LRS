#!/usr/bin/env python3
"""
LRS Golden Cross Strategy Backtest (TQQQ era).

Strategies (all signals from the S&P 500, decided at the close):
- Golden Cross n/200: risk-on when the n-day SMA > 200-day SMA.
- GC 10/200 + b% buffer: enter when SMA10 > SMA200 * (1 + b), exit when
  SMA10 < SMA200 * (1 - b), otherwise keep the state.
- Asymmetric exit: enter when SMA10 > SMA200 * 1.02, exit when SMA10 < SMA100.
- Original LRS: risk-on when Close > SMA200.

Risk-on holds TQQQ, risk-off holds cash. Primary results use next-open
fills; market-on-close results are reported alongside (see backtest_common).
"""

import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import backtest_common as bc

SHORT_WINDOWS = [5, 10, 20, 50]
BUFFERS = [0.01, 0.02, 0.03, 0.04, 0.05]


def hysteresis(values, upper, lower):
    """
    Two-threshold state machine: 1 above ``upper``, 0 below ``lower``,
    otherwise keep the previous state (start at 0).

    Parameters:
    values (pd.Series): Signal line (e.g. SMA10).
    upper (pd.Series): Entry threshold.
    lower (pd.Series): Exit threshold.

    Returns:
    pd.Series: Regime (0.0 or 1.0) decided at each close.
    """
    state = 0.0
    out = []
    for v, up, low in zip(values.values, upper.values, lower.values):
        if np.isnan(v) or np.isnan(up) or np.isnan(low):
            out.append(0.0)
            continue
        if v > up:
            state = 1.0
        elif v < low:
            state = 0.0
        out.append(state)
    return pd.Series(out, index=values.index)


def asymmetric_regime(sma10, sma200, sma100, buffer=0.02):
    """
    Enter when SMA10 > SMA200 * (1 + buffer); once in, exit when SMA10 < SMA100.

    Parameters:
    sma10 (pd.Series): 10-day SMA.
    sma200 (pd.Series): 200-day SMA.
    sma100 (pd.Series): 100-day SMA.
    buffer (float): Entry buffer above SMA200.

    Returns:
    pd.Series: Regime (0.0 or 1.0) decided at each close.
    """
    state = 0.0
    out = []
    for v, s200, s100 in zip(sma10.values, sma200.values, sma100.values):
        if np.isnan(v) or np.isnan(s200) or np.isnan(s100):
            out.append(0.0)
            continue
        if state == 0.0 and v > s200 * (1 + buffer):
            state = 1.0
        elif state == 1.0 and v < s100:
            state = 0.0
        out.append(state)
    return pd.Series(out, index=sma10.index)


def build_regimes(sp500):
    """
    Compute every strategy's regime on the full S&P 500 history.

    Parameters:
    sp500 (pd.DataFrame): S&P 500 bars with a Close column.

    Returns:
    dict: Strategy name -> regime Series decided at each close.
    """
    close = sp500['Close']
    sma = {n: close.rolling(n).mean() for n in SHORT_WINDOWS + [100, 200]}
    regimes = {}
    for n in SHORT_WINDOWS:
        valid = sma[n].notna() & sma[200].notna()
        regimes[f'Golden Cross ({n}/200)'] = ((sma[n] > sma[200]) & valid).astype(float)
    for buf in BUFFERS:
        regimes[f'GC (10/200) + {int(buf * 100)}% Buffer'] = hysteresis(
            sma[10], sma[200] * (1 + buf), sma[200] * (1 - buf))
    regimes['Asym (Entry 10/200+2%, Exit 10 < 100)'] = asymmetric_regime(sma[10], sma[200], sma[100])
    valid = sma[200].notna()
    regimes['Original LRS (Price > SMA200)'] = ((close > sma[200]) & valid).astype(float)
    return regimes


def plot_equity(name, values, bh_values, filename):
    """Save a log-scale equity plot of one strategy vs Buy & Hold TQQQ."""
    plt.figure(figsize=(10, 6))
    plt.plot(values.index, values, label=name, color='blue')
    plt.plot(bh_values.index, bh_values, label='Buy & Hold TQQQ', color='gray', linestyle='--', alpha=0.5)
    plt.title(f'{name} vs Buy & Hold (TQQQ, next-open fills)')
    plt.yscale('log')
    plt.legend()
    plt.savefig(os.path.join(bc.PLOTS_DIR, filename))
    plt.close()


def main():
    """Run all golden cross variants and save results/golden_cross_summary.csv."""
    print("Running Golden Cross Backtest (TQQQ Era)...")
    sp500 = bc.load_ohlcv('sp500')
    tqqq = bc.load_ohlcv('tqqq')

    regimes = pd.DataFrame(build_regimes(sp500))
    df = regimes.join(tqqq[['Open', 'Close']].rename(columns={'Open': 'TQQQ_Open', 'Close': 'TQQQ_Close'}),
                      how='inner')
    df = df.join(sp500[['Close']].rename(columns={'Close': 'SPX_Close'}), how='inner')
    start, end = df.index[0].date(), df.index[-1].date()
    print(f"Backtest window: {start} to {end}")

    bh_ret = df['TQQQ_Close'].pct_change().fillna(0.0)
    spx_ret = df['SPX_Close'].pct_change().fillna(0.0)
    bh_values = bc.buy_hold_equity(df['TQQQ_Close'])

    rows = []
    m = bc.performance_metrics(bh_values, bh_ret, bh_ret, spx_ret)
    rows.append({'Strategy': 'Buy & Hold TQQQ', **m, 'MOC_Final_Value': m['Final_Value'], 'MOC_CAGR': m['CAGR']})
    for name in regimes.columns:
        r = bc.strategy_returns(df[name], df['TQQQ_Open'], df['TQQQ_Close'], 'next_open')
        r_moc = bc.strategy_returns(df[name], df['TQQQ_Open'], df['TQQQ_Close'], 'moc')
        values = bc.equity_curve(r)
        m = bc.performance_metrics(values, r, bh_ret, spx_ret)
        m_moc = bc.performance_metrics(bc.equity_curve(r_moc), r_moc, bh_ret, spx_ret)
        trades = int((bc.held_weights(df[name])[1].diff() > 0).sum())
        rows.append({'Strategy': name, **m, 'MOC_Final_Value': m_moc['Final_Value'],
                     'MOC_CAGR': m_moc['CAGR'], 'Trades': trades})
        slug = name.lower().replace(' ', '_')
        for ch in '()/%+>,<.':
            slug = slug.replace(ch, '')
        plot_equity(name, values, bh_values, f'golden_cross_{slug}_tqqq.png')

    res = pd.DataFrame(rows).sort_values('Final_Value', ascending=False)
    res['Start'], res['End'] = start, end
    res.to_csv(os.path.join(bc.RESULTS_DIR, 'golden_cross_summary.csv'), index=False)

    print(f"\n--- Golden Cross Results ({start} to {end}; next-open fills, MOC alongside) ---")
    print(res[['Strategy', 'CAGR', 'Max_Drawdown', 'Sharpe', 'Final_Value', 'MOC_Final_Value']].to_string(
        index=False, formatters={'CAGR': '{:.2%}'.format, 'Max_Drawdown': '{:.2%}'.format,
                                 'Sharpe': '{:.2f}'.format, 'Final_Value': '${:,.0f}'.format,
                                 'MOC_Final_Value': '${:,.0f}'.format}))
    return res


if __name__ == "__main__":
    main()
