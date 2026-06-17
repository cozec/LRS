#!/usr/bin/env python3
"""
Plot the latest 5 trades for the Hybrid Sniper strategy on TQQQ.
Generates a detailed PDF report visualizing the trade contexts, S&P 500 signals,
RSI values, and TQQQ returns.
"""

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

warnings.filterwarnings('ignore')

# Directories
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
PLOTS_DIR = os.path.join(PROJECT_ROOT, 'plots')
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results')


def load_backtest_data():
    """Load TQQQ backtest data from the hybrid sniper backtest.

    Since lrs_hybrid_sniper.py doesn't save a daily CSV, we reconstruct
    the needed data by running the signal calculation on the raw data.

    Returns:
        tuple: (df, trades) DataFrames
    """
    # Load SP500 and TQQQ raw data
    sp500_path = os.path.join(DATA_DIR, 'sp500.csv')
    tqqq_path = os.path.join(DATA_DIR, 'tqqq.csv')

    sp500 = pd.read_csv(sp500_path, index_col=0, parse_dates=True)
    tqqq = pd.read_csv(tqqq_path, index_col=0, parse_dates=True)

    # Handle MultiIndex artifacts
    for d in [sp500, tqqq]:
        if not d.empty and (d.index[0] == 'Ticker' or str(d.index[0]) == 'nan'):
            d.index = pd.to_datetime(d.index, errors='coerce')
            d.dropna(how='all', inplace=True)
        for col in d.columns:
            d[col] = pd.to_numeric(d[col], errors='coerce')
        d.sort_index(inplace=True)

    # Calculate indicators on S&P 500
    sp500['SMA_200'] = sp500['Close'].rolling(window=200).mean()
    sp500['MA_10'] = sp500['Close'].rolling(window=10).mean()

    # RSI using Wilder's Smoothing
    delta = sp500['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(com=13, min_periods=14).mean()
    avg_loss = loss.ewm(com=13, min_periods=14).mean()
    rs = avg_gain / avg_loss
    sp500['RSI'] = 100 - (100 / (1 + rs))

    sp500['Upper_Band'] = sp500['SMA_200'] * 1.02
    sp500['Lower_Band'] = sp500['SMA_200'] * 0.98

    # Build combined DataFrame
    df = sp500[['Close', 'SMA_200', 'MA_10', 'RSI', 'Upper_Band', 'Lower_Band']].copy()
    df.columns = ['SP500_Close', 'SMA_200', 'MA_10', 'RSI', 'Upper_Band', 'Lower_Band']
    df = df.join(tqqq[['Close']].rename(columns={'Close': 'TQQQ_Close'}), how='inner')
    df = df.dropna(subset=['TQQQ_Close'])

    # Calculate Sniper Regime
    regime = []
    current_state = 0.0
    for i in range(len(df)):
        ma10 = df['MA_10'].iloc[i]
        upper = df['Upper_Band'].iloc[i]
        lower = df['Lower_Band'].iloc[i]
        rsi = df['RSI'].iloc[i]

        if pd.isna(ma10) or pd.isna(upper) or pd.isna(rsi):
            regime.append(0.0)
            continue

        if ma10 > upper:
            current_state = 1.0
        elif ma10 < lower:
            if current_state == 1.0:
                current_state = 0.0
            if current_state == 0.0:
                if rsi < 30:
                    current_state = 0.5
            elif current_state == 0.5:
                if rsi > 50:
                    current_state = 0.0

        regime.append(current_state)

    df['Sniper_Regime'] = regime
    df['Sniper_Signal'] = df['Sniper_Regime'].shift(1)

    # Filter to TQQQ era (2010+)
    df = df[df.index >= '2010-01-01']
    df = df.dropna(subset=['SMA_200'])

    # Load transactions
    trans_path = os.path.join(RESULTS_DIR, 'transactions_hybrid_sniper.csv')
    trades = pd.read_csv(trans_path)

    return df, trades


def plot_trade(ax1, ax2, ax3, subset, df, trade, idx, entry_date, exit_date):
    """Plot a single trade across three panels.

    Parameters:
        ax1: Top panel (S&P 500 signals)
        ax2: Middle panel (RSI)
        ax3: Bottom panel (TQQQ price)
        subset: Windowed data slice
        df: Full DataFrame for lookups
        trade: Trade row from transaction log
        idx: Trade index (1-based)
        entry_date: Trade entry date
        exit_date: Trade exit date
    """
    trade_type = trade['Type']

    # --- Top Panel: S&P 500 Signals ---
    ax1.plot(subset.index, subset['SP500_Close'], label='S&P 500 Close',
             color='#1a1a1a', linewidth=1.2, alpha=0.8)
    ax1.plot(subset.index, subset['MA_10'], label='MA 10',
             color='#007bff', linewidth=1.0)
    ax1.plot(subset.index, subset['SMA_200'], label='SMA 200',
             color='#ff7f0e', linestyle='--', linewidth=1.0)

    # Buffer bands (±2%)
    upper_band = subset['SMA_200'] * 1.02
    lower_band = subset['SMA_200'] * 0.98
    ax1.fill_between(subset.index, lower_band, upper_band,
                     color='#ff7f0e', alpha=0.12, label='Buffer Zone (±2%)')

    # Entry/Exit S&P 500 values
    spx_entry_s = subset.loc[subset.index >= entry_date, 'SP500_Close']
    spx_exit_s = subset.loc[subset.index >= exit_date, 'SP500_Close']
    spx_entry = spx_entry_s.iloc[0] if not spx_entry_s.empty else subset['SP500_Close'].iloc[0]
    spx_exit = spx_exit_s.iloc[0] if not spx_exit_s.empty else subset['SP500_Close'].iloc[-1]

    # Entry label
    if "Sniper" in trade_type:
        entry_label = "Sniper Entry\n(RSI < 30)"
        entry_color = '#2ca02c'
    else:
        entry_label = "Trend Entry\n(MA10 > SMA200 * 1.02)"
        entry_color = '#1f77b4'
    entry_marker = '^'

    # Check if trade is open
    is_open = trade.get('Status', 'CLOSED') == 'OPEN'

    # Exit label
    if is_open:
        exit_label = "STILL OPEN"
        exit_color = '#ff8c00'
        exit_marker = 'D'
    else:
        if "Sniper" in trade_type and exit_date in df.index:
            rsi_val = df.loc[exit_date, 'RSI']
            if rsi_val > 49.0:
                exit_label = "RSI Exit\n(RSI > 50)"
            else:
                exit_label = "SMA Exit\n(MA10 < SMA200 * 0.98)"
        else:
            exit_label = "SMA Exit\n(MA10 < SMA200 * 0.98)"
        exit_color = '#d62728'
        exit_marker = 'v'

    # Plot markers and annotations
    ax1.scatter(entry_date, spx_entry, color=entry_color, marker=entry_marker, s=80, zorder=5)
    ax1.annotate(entry_label, xy=(entry_date, spx_entry), xytext=(-35, 25),
                 textcoords='offset points',
                 arrowprops=dict(arrowstyle='->', color=entry_color, lw=1.0),
                 fontsize=8, fontweight='bold',
                 bbox=dict(boxstyle="round,pad=0.3", fc="#eef", alpha=0.8, ec=entry_color))

    ax1.scatter(exit_date, spx_exit, color=exit_color, marker=exit_marker, s=80, zorder=5)
    ax1.annotate(exit_label, xy=(exit_date, spx_exit), xytext=(15, 25),
                 textcoords='offset points',
                 arrowprops=dict(arrowstyle='->', color=exit_color, lw=1.0),
                 fontsize=8, fontweight='bold',
                 bbox=dict(boxstyle="round,pad=0.3", fc="#ffe", alpha=0.8, ec=exit_color))

    # Title
    if is_open:
        title_text = (f"TQQQ Hybrid Sniper Trade #{idx} | {trade_type} (Still Open)\n"
                      f"{entry_date.date()} to {exit_date.date()} ({trade['Duration_Days']} days)")
    else:
        title_text = (f"TQQQ Hybrid Sniper Trade #{idx} | {trade_type}\n"
                      f"{entry_date.date()} to {exit_date.date()} ({trade['Duration_Days']} days)")

    ax1.set_title(title_text, fontsize=11, fontweight='bold', pad=10)
    ax1.set_ylabel('S&P 500 Price', fontsize=9)
    ax1.grid(True, alpha=0.25)
    ax1.legend(loc='upper left', fontsize='x-small')

    # --- Middle Panel: RSI ---
    ax2.plot(subset.index, subset['RSI'], label='S&P 500 RSI(14)',
             color='#9467bd', linewidth=1.0)
    ax2.axhline(30, color='#2ca02c', linestyle='--', alpha=0.6,
                label='Oversold threshold (30)')
    ax2.axhline(50, color='#7f7f7f', linestyle='--', alpha=0.5,
                label='Neutral profit-take (50)')
    ax2.fill_between(subset.index, subset['RSI'], 30,
                     where=(subset['RSI'] < 30), color='#2ca02c', alpha=0.15)

    # RSI markers
    rsi_entry_s = subset.loc[subset.index >= entry_date, 'RSI']
    rsi_exit_s = subset.loc[subset.index >= exit_date, 'RSI']

    if not rsi_entry_s.empty:
        rsi_ent = rsi_entry_s.iloc[0]
        ax2.scatter(entry_date, rsi_ent, color=entry_color, s=40, zorder=5)
        ax2.annotate(f"RSI: {rsi_ent:.1f}", xy=(entry_date, rsi_ent),
                     xytext=(-25, -15), textcoords='offset points',
                     fontsize=7, color=entry_color, fontweight='bold')
    if not rsi_exit_s.empty:
        rsi_ex = rsi_exit_s.iloc[0]
        ax2.scatter(exit_date, rsi_ex, color=exit_color, s=40, zorder=5)
        ax2.annotate(f"RSI: {rsi_ex:.1f}", xy=(exit_date, rsi_ex),
                     xytext=(10, -15), textcoords='offset points',
                     fontsize=7, color=exit_color, fontweight='bold')

    ax2.set_ylabel('RSI (14)', fontsize=9)
    ax2.set_ylim(10, 90)
    ax2.grid(True, alpha=0.25)
    ax2.legend(loc='upper right', fontsize='xx-small')

    # --- Bottom Panel: TQQQ ---
    ax3.plot(subset.index, subset['TQQQ_Close'], label='TQQQ Close Price',
             color='#17becf', linewidth=1.2)
    ax3.axvspan(entry_date, exit_date, alpha=0.1, color='#2ca02c',
                label='Trade Duration')

    # TQQQ markers
    tqqq_entry_s = subset.loc[subset.index >= entry_date, 'TQQQ_Close']
    tqqq_exit_s = subset.loc[subset.index >= exit_date, 'TQQQ_Close']
    tqqq_ent = tqqq_entry_s.iloc[0] if not tqqq_entry_s.empty else subset['TQQQ_Close'].iloc[0]
    tqqq_ex = tqqq_exit_s.iloc[0] if not tqqq_exit_s.empty else subset['TQQQ_Close'].iloc[-1]

    ax3.scatter(entry_date, tqqq_ent, color=entry_color, marker=entry_marker, s=60, zorder=5)
    ax3.annotate(f"${tqqq_ent:.2f}", xy=(entry_date, tqqq_ent), xytext=(-30, -12),
                 textcoords='offset points', fontsize=8, color='#333', fontweight='bold')

    ax3.scatter(exit_date, tqqq_ex, color=exit_color, marker=exit_marker, s=60, zorder=5)
    ax3.annotate(f"${tqqq_ex:.2f}", xy=(exit_date, tqqq_ex), xytext=(10, -12),
                 textcoords='offset points', fontsize=8, color='#333', fontweight='bold')

    # Return metrics box
    strat_ret = trade['Return_Strategy'] * 100
    tqqq_ret = trade['Return_TQQQ'] * 100
    status_label = " (Open)" if is_open else ""

    metric_text = (
        f"Strategy Return: {strat_ret:+.2f}%{status_label}\n"
        f"TQQQ Asset Return: {tqqq_ret:+.2f}%\n"
        f"Outperformance: {strat_ret - tqqq_ret:+.2f}%"
    )

    ax3.text(0.03, 0.05, metric_text, transform=ax3.transAxes, fontsize=8,
             fontweight='bold',
             bbox=dict(boxstyle="round,pad=0.4", facecolor='white',
                       alpha=0.9, edgecolor='#ccc'))

    ax3.set_ylabel('TQQQ Price ($)', fontsize=9)
    ax3.set_xlabel('Date', fontsize=9)
    ax3.grid(True, alpha=0.25)
    ax3.legend(loc='upper left', fontsize='x-small')


def main():
    """Load backtest data and plot the latest 5 trades with details."""
    print("Loading TQQQ backtest data and transactions...")

    df, trades = load_backtest_data()

    # Get the latest 5 trades
    latest_trades = trades.tail(5).copy().reset_index(drop=True)

    pdf_path = os.path.join(PLOTS_DIR, 'tqqq_latest_5_trades.pdf')
    print(f"Plotting the latest 5 trades to {pdf_path}...")

    with PdfPages(pdf_path) as pdf:
        for idx, trade in latest_trades.iterrows():
            entry_date = pd.to_datetime(trade['Entry_Date'])
            exit_date = pd.to_datetime(trade['Exit_Date'])

            # Pad window with 60 days on either side
            start_window = entry_date - pd.Timedelta(days=60)
            end_window = exit_date + pd.Timedelta(days=60)

            mask = (df.index >= start_window) & (df.index <= end_window)
            subset = df.loc[mask].copy()

            if subset.empty:
                continue

            fig, (ax1, ax2, ax3) = plt.subplots(
                3, 1, figsize=(8.5, 11), sharex=True,
                gridspec_kw={'height_ratios': [2, 1, 2]}
            )

            plot_trade(ax1, ax2, ax3, subset, df, trade, idx + 1,
                       entry_date, exit_date)

            plt.subplots_adjust(hspace=0.08)
            pdf.savefig(fig)
            plt.close(fig)

    print(f"Successfully plotted the latest 5 trades to {pdf_path}")

    # Save a PNG of the latest trade
    print("Saving PNG of the latest trade...")
    latest_trade = latest_trades.iloc[-1]
    entry_date = pd.to_datetime(latest_trade['Entry_Date'])
    exit_date = pd.to_datetime(latest_trade['Exit_Date'])
    start_window = entry_date - pd.Timedelta(days=60)
    end_window = exit_date + pd.Timedelta(days=60)
    subset = df.loc[(df.index >= start_window) & (df.index <= end_window)].copy()

    if not subset.empty:
        fig, (ax1, ax2, ax3) = plt.subplots(
            3, 1, figsize=(10, 12), sharex=True,
            gridspec_kw={'height_ratios': [2, 1, 2]}
        )

        plot_trade(ax1, ax2, ax3, subset, df, latest_trade, 5,
                   entry_date, exit_date)

        plt.subplots_adjust(hspace=0.08)
        png_path = os.path.join(PLOTS_DIR, 'tqqq_latest_trade.png')
        plt.savefig(png_path, dpi=120)
        plt.close()
        print(f"Saved PNG to {png_path}")


if __name__ == "__main__":
    main()
