#!/usr/bin/env python3
"""
Leverage Rotation Strategy (LRS) SOXL Backtest.

Implements the backtest for SOXL (3x Bull Semiconductor ETF) from its inception in 2010.
Strategies implemented:
1. Buy & Hold SOXL
2. LRS Baseline (MA10/200 with 2% buffer)
3. Hybrid Sniper (RSI re-entry)

All strategy signals are calculated using the S&P 500 (^GSPC) as the broad-market filter.
"""

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

warnings.filterwarnings('ignore')

import backtest_common as bc  # noqa: E402

# Configuration
INITIAL_CAPITAL = bc.INITIAL_CAPITAL
RISK_FREE_RATE = bc.RISK_FREE_RATE  # 3% annual cash return
SMA_PERIOD = 200
MA_SHORT = 10
BUFFER = 0.02  # 2% buffer
RSI_PERIOD = 14
RSI_ENTRY = 30
RSI_EXIT = 50
SNIPER_ALLOC = 0.5  # 50% allocation for sniper trades

# Directories
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
PLOTS_DIR = os.path.join(PROJECT_ROOT, 'plots')
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results')

for d in [PLOTS_DIR, RESULTS_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)


def load_clean_csv(path):
    """
    Load a CSV file, parse dates, set index, and handle potential yfinance MultiIndex artifacts.

    Parameters:
    path (str): The path to the CSV file.

    Returns:
    pd.DataFrame: The cleaned DataFrame.
    """
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    if not df.empty and (df.index[0] == 'Ticker' or str(df.index[0]) == 'nan'):
        df.index = pd.to_datetime(df.index, errors='coerce')
        df = df.dropna(how='all')
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.sort_index()
    return df


def calculate_rsi(series, period=14):
    """
    Calculate RSI using Wilder's Smoothing (Exponential Weighted Moving Average).

    Parameters:
    series (pd.Series): The price series.
    period (int): The RSI lookback period.

    Returns:
    pd.Series: The calculated RSI series.
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def load_data():
    """
    Load S&P 500 and SOXL data, calculate signals on S&P 500, and align them.

    Returns:
    pd.DataFrame: S&P 500 and SOXL aligned data.
    """
    sp500_path = os.path.join(DATA_DIR, 'sp500.csv')
    soxl_path = os.path.join(DATA_DIR, 'soxl.csv')
    
    if not os.path.exists(sp500_path) or not os.path.exists(soxl_path):
        raise FileNotFoundError(f"Ensure sp500.csv and soxl.csv exist in {DATA_DIR}.")
        
    sp500 = load_clean_csv(sp500_path)
    soxl = load_clean_csv(soxl_path)
    
    # Calculate indicators on S&P 500 FULL history first to avoid warm-up period
    sp500['SMA_200'] = sp500['Close'].rolling(window=SMA_PERIOD).mean()
    sp500['MA_10'] = sp500['Close'].rolling(window=MA_SHORT).mean()
    sp500['RSI'] = calculate_rsi(sp500['Close'], RSI_PERIOD)
    
    sp500['Upper_Band'] = sp500['SMA_200'] * (1 + BUFFER)
    sp500['Lower_Band'] = sp500['SMA_200'] * (1 - BUFFER)
    
    # Run both state machines on the FULL S&P 500 history, so the regime at
    # SOXL's first day does not depend on where the window starts
    sp500 = calculate_baseline_signal(sp500)
    sp500 = calculate_sniper_signal(sp500)

    # Join SOXL Open/Close
    df = sp500[['Close', 'SMA_200', 'MA_10', 'RSI', 'Upper_Band', 'Lower_Band',
                'Baseline_Regime', 'Sniper_Regime']].copy()
    df = df.rename(columns={'Close': 'SP500_Close'})

    df = df.join(soxl[['Open', 'Close']].rename(columns={'Open': 'SOXL_Open', 'Close': 'SOXL_Close'}),
                 how='inner')
    df = df.dropna(subset=['SOXL_Close'])
    
    print(f"SOXL Alignment Date Range: {df.index[0].date()} to {df.index[-1].date()}")
    print(f"Total Trading Days: {len(df)}")
    
    return df


def calculate_baseline_signal(df):
    """
    Calculate LRS Baseline signal (MA10/200 with 2% buffer).

    Parameters:
    df (pd.DataFrame): Input DataFrame.

    Returns:
    pd.DataFrame: DataFrame with Baseline_Signal column.
    """
    df = df.copy()
    regime = []
    current_state = 0
    
    ma10_vals = df['MA_10'].values
    up_vals = df['Upper_Band'].values
    low_vals = df['Lower_Band'].values
    
    for i in range(len(df)):
        ma10 = ma10_vals[i]
        upper = up_vals[i]
        lower = low_vals[i]
        
        if pd.isna(ma10) or pd.isna(upper):
            regime.append(0)
            continue
            
        if ma10 > upper:
            current_state = 1
        elif ma10 < lower:
            current_state = 0
            
        regime.append(current_state)
        
    df['Baseline_Regime'] = regime
    df['Baseline_Signal'] = df['Baseline_Regime'].shift(1)  # Trade next day
    return df


def calculate_sniper_signal(df):
    """
    Calculate Hybrid Sniper signal with RSI re-entry.

    Parameters:
    df (pd.DataFrame): Input DataFrame.

    Returns:
    pd.DataFrame: DataFrame with Sniper_Signal column.
    """
    df = df.copy()
    regime = []
    current_state = 0.0  # 0.0 = Cash, 0.5 = Sniper, 1.0 = Bull
    
    ma10_vals = df['MA_10'].values
    lower_vals = df['Lower_Band'].values
    upper_vals = df['Upper_Band'].values
    rsi_vals = df['RSI'].values
    
    for i in range(len(df)):
        ma10 = ma10_vals[i]
        upper = upper_vals[i]
        lower = lower_vals[i]
        rsi = rsi_vals[i]
        
        if pd.isna(ma10) or pd.isna(upper) or pd.isna(rsi):
            regime.append(0.0)
            continue
            
        # State Machine
        # 1. Bull Trend Entry
        if ma10 > upper:
            current_state = 1.0
        # 2. Bear territory
        elif ma10 < lower:
            if current_state == 1.0:
                current_state = 0.0  # Exit to Cash
                
            if current_state == 0.0:
                if rsi < RSI_ENTRY:
                    current_state = SNIPER_ALLOC
            elif current_state == SNIPER_ALLOC:
                if rsi > RSI_EXIT:
                    current_state = 0.0  # Profit Take -> Cash
        # 3. Inside Hysteresis zone (keep state)
        
        regime.append(current_state)
        
    df['Sniper_Regime'] = regime
    df['Sniper_Signal'] = df['Sniper_Regime'].shift(1)  # Trade next day
    return df


def calculate_returns(df, fill='next_open', cash_rate=RISK_FREE_RATE):
    """
    Calculate daily returns and equity for Buy & Hold, Baseline and Hybrid Sniper.

    Parameters:
    df (pd.DataFrame): Aligned S&P 500 / SOXL data with regime columns.
    fill (str): 'next_open' (primary) or 'moc' (market-on-close), see backtest_common.
    cash_rate (float): Annual return on cash.

    Returns:
    pd.DataFrame: DataFrame with return and value columns.
    """
    df = df.copy()
    df['SOXL_Return'] = df['SOXL_Close'].pct_change().fillna(0)
    df['SP500_Return'] = df['SP500_Close'].pct_change().fillna(0)
    df['BH_Return'] = df['SOXL_Return']

    # Weight held during each session (next-open), used by plots/logs
    df['Baseline_Signal'] = bc.held_weights(df['Baseline_Regime'])[1]
    df['Sniper_Signal'] = bc.held_weights(df['Sniper_Regime'])[1]

    df['Baseline_Return'] = bc.strategy_returns(df['Baseline_Regime'], df['SOXL_Open'],
                                                df['SOXL_Close'], fill, cash_rate)
    df['Sniper_Return'] = bc.strategy_returns(df['Sniper_Regime'], df['SOXL_Open'],
                                              df['SOXL_Close'], fill, cash_rate)

    # Buy & Hold uses the exact formula $10,000 * (close / first_close)
    df['BH_Value'] = bc.buy_hold_equity(df['SOXL_Close'])
    df['SP500_Value'] = bc.buy_hold_equity(df['SP500_Close'])
    df['Baseline_Value'] = bc.equity_curve(df['Baseline_Return'])
    df['Sniper_Value'] = bc.equity_curve(df['Sniper_Return'])
    return df


def calculate_metrics(values, daily_returns, benchmark_returns, sp500_returns):
    """
    Calculate professional performance metrics (see backtest_common.performance_metrics).

    Parameters:
    values (pd.Series): Portfolio equity values.
    daily_returns (pd.Series): Daily returns of the strategy.
    benchmark_returns (pd.Series): Daily returns of the Buy & Hold asset.
    sp500_returns (pd.Series): Daily returns of S&P 500.

    Returns:
    dict: Performance metrics.
    """
    return bc.performance_metrics(values, daily_returns, benchmark_returns, sp500_returns)


def generate_transaction_log(df):
    """
    Generate the Hybrid Sniper SOXL trade log under next-open fills.

    Parameters:
    df (pd.DataFrame): Output of ``calculate_returns`` with fill='next_open'.

    Returns:
    pd.DataFrame: Trade log DataFrame (see backtest_common.trade_log).
    """
    log = bc.trade_log(df['Sniper_Regime'], df['Sniper_Return'], df['SOXL_Open'], df['SOXL_Close'])
    return log.rename(columns={'Return_Asset': 'Return_SOXL'})


def plot_results(df):
    """
    Generate comparison plot of equity curves and drawdowns.

    Parameters:
    df (pd.DataFrame): Input DataFrame with cumulative values.
    """
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    
    # Equity Curves
    ax1 = axes[0]
    ax1.semilogy(df.index, df['Sniper_Value'], label='Hybrid Sniper', color='blue', linewidth=2)
    ax1.semilogy(df.index, df['Baseline_Value'], label='LRS Baseline', color='orange', linewidth=1.5)
    ax1.semilogy(df.index, df['BH_Value'], label='Buy & Hold SOXL', color='red', linewidth=1.5, alpha=0.7)
    ax1.semilogy(df.index, df['SP500_Value'], label='Buy & Hold S&P 500', color='green', linewidth=1.5, alpha=0.7)
    
    ax1.set_title('LRS Strategy Comparison (SOXL Era: 2010 - Present)', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Portfolio Value ($, log scale)')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=INITIAL_CAPITAL, color='gray', linestyle='--', alpha=0.5)
    
    # Drawdowns
    ax2 = axes[1]
    for col, label, color in [('Sniper_Value', 'Hybrid Sniper', 'blue'),
                               ('Baseline_Value', 'LRS Baseline', 'orange'),
                               ('BH_Value', 'Buy & Hold SOXL', 'red'),
                               ('SP500_Value', 'Buy & Hold S&P 500', 'green')]:
        running_max = df[col].cummax()
        drawdown = (df[col] - running_max) / running_max * 100
        ax2.fill_between(df.index, drawdown, 0, alpha=0.2, label=label)
        ax2.plot(df.index, drawdown, linewidth=0.8, color=color)
        
    ax2.set_title('Drawdowns (%)', fontsize=14, fontweight='bold')
    ax2.set_ylabel('Drawdown (%)')
    ax2.set_xlabel('Date')
    ax2.legend(loc='lower left')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, 'soxl_equity_comparison.png'), dpi=150)
    plt.savefig(os.path.join(PLOTS_DIR, 'soxl_equity_comparison.pdf'), dpi=150)
    plt.close()
    print(f"Saved equity plots to {PLOTS_DIR}/soxl_equity_comparison.png/pdf")


def plot_trades(df, transactions):
    """
    Generate a multi-page PDF showing context charts for each strategy trade.

    Parameters:
    df (pd.DataFrame): Input DataFrame.
    transactions (pd.DataFrame): DataFrame of trades.
    """
    if transactions.empty:
        print("No trades found to plot.")
        return
        
    pdf_path = os.path.join(PLOTS_DIR, 'soxl_trades.pdf')
    with PdfPages(pdf_path) as pdf:
        for idx, trade in transactions.iterrows():
            entry_date = pd.to_datetime(trade['Entry_Date'])
            exit_date = pd.to_datetime(trade['Exit_Date'])
            
            # 60 days padding around trade
            start_window = entry_date - pd.Timedelta(days=60)
            end_window = exit_date + pd.Timedelta(days=60)
            
            mask = (df.index >= start_window) & (df.index <= end_window)
            subset = df.loc[mask].copy()
            
            if subset.empty:
                continue
                
            fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8.5, 11), sharex=True,
                                                  gridspec_kw={'height_ratios': [2, 1, 2]})
            
            # Top Panel: S&P 500 (Signals)
            ax1.plot(subset.index, subset['SP500_Close'], label='S&P 500', color='black', linewidth=1, alpha=0.6)
            ax1.plot(subset.index, subset['MA_10'], label='MA 10', color='blue', linewidth=1)
            ax1.plot(subset.index, subset['SMA_200'], label='MA 200', color='orange', linestyle='--', linewidth=1)
            
            upper_buffer = subset['SMA_200'] * 1.02
            lower_buffer = subset['SMA_200'] * 0.98
            ax1.fill_between(subset.index, lower_buffer, upper_buffer, color='orange', alpha=0.15, label='±2% Buffer')
            
            # Mark Entry/Exit on SPX
            entry_mask = subset.index >= entry_date
            if entry_mask.any():
                spx_entry = subset.loc[entry_mask, 'SP500_Close'].iloc[0]
                ax1.scatter(entry_date, spx_entry, color='green', marker='^', s=80, zorder=5)
                ax1.annotate('', xy=(entry_date, spx_entry), xytext=(0, 20), 
                             textcoords='offset points', arrowprops=dict(arrowstyle='->', color='green', lw=1.5))
                             
            exit_mask = subset.index >= exit_date
            if exit_mask.any():
                spx_exit = subset.loc[exit_mask, 'SP500_Close'].iloc[0]
                ax1.scatter(exit_date, spx_exit, color='red', marker='v', s=80, zorder=5)
                ax1.annotate('', xy=(exit_date, spx_exit), xytext=(0, 20), 
                             textcoords='offset points', arrowprops=dict(arrowstyle='->', color='red', lw=1.5))
                             
            trade_type = trade.get('Type', 'Unknown')
            ret_str = f"{trade['Return_Strategy']*100:+.1f}%"
            title_text = f"Trade #{idx+1} ({trade_type}) | {entry_date.date()} to {exit_date.date()} | {trade['Duration_Days']} days | Return: {ret_str} | Exit: {trade.get('Exit_Reason', '')}"
            ax1.set_title(title_text, fontsize=10, fontweight='bold')
            ax1.set_ylabel('S&P 500', fontsize=9)
            ax1.legend(loc='upper left', fontsize='x-small')
            ax1.grid(True, alpha=0.3)
            
            # Middle Panel: RSI on S&P 500
            ax2.plot(subset.index, subset['RSI'], label='RSI(14)', color='purple', linewidth=0.8)
            ax2.axhline(30, color='green', linestyle='--', alpha=0.5, label='Oversold (30)')
            ax2.axhline(50, color='gray', linestyle='--', alpha=0.5, label='Neutral (50)')
            ax2.fill_between(subset.index, subset['RSI'], 30, where=(subset['RSI'] < 30), color='green', alpha=0.2)
            
            if entry_mask.any():
                rsi_entry = subset.loc[entry_mask, 'RSI'].iloc[0]
                ax2.scatter(entry_date, rsi_entry, color='green', marker='^', s=40, zorder=5)
            if exit_mask.any():
                rsi_exit = subset.loc[exit_mask, 'RSI'].iloc[0]
                ax2.scatter(exit_date, rsi_exit, color='red', marker='v', s=40, zorder=5)
                
            ax2.set_ylabel('RSI', fontsize=9)
            ax2.set_ylim(0, 100)
            ax2.legend(loc='upper right', fontsize='x-small')
            ax2.grid(True, alpha=0.3)
            
            # Bottom Panel: SOXL
            ax3.plot(subset.index, subset['SOXL_Close'], label='SOXL Price', color='teal', linewidth=1.2)
            ax3.axvspan(entry_date, exit_date, alpha=0.15, color='green', label='Active Trade')
            
            if entry_mask.any():
                soxl_entry = subset.loc[entry_mask, 'SOXL_Close'].iloc[0]
                ax3.scatter(entry_date, soxl_entry, color='green', marker='^', s=80, zorder=5)
                ax3.annotate('', xy=(entry_date, soxl_entry), xytext=(0, 20), 
                             textcoords='offset points', arrowprops=dict(arrowstyle='->', color='green', lw=1.5))
            if exit_mask.any():
                soxl_exit = subset.loc[exit_mask, 'SOXL_Close'].iloc[0]
                ax3.scatter(exit_date, soxl_exit, color='red', marker='v', s=80, zorder=5)
                ax3.annotate('', xy=(exit_date, soxl_exit), xytext=(0, 20), 
                             textcoords='offset points', arrowprops=dict(arrowstyle='->', color='red', lw=1.5))
                             
            soxl_ret = trade['Return_SOXL'] * 100
            ax3.set_title(f"SOXL Return: {soxl_ret:+.1f}%", fontsize=9, fontweight='bold')
            ax3.set_ylabel('SOXL ($)', fontsize=9)
            ax3.set_xlabel('Date', fontsize=9)
            ax3.legend(loc='upper left', fontsize='x-small')
            ax3.grid(True, alpha=0.3)
            
            plt.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)
            
    print(f"Saved trade plots to {pdf_path}")


def main():
    """Run the SOXL backtest: next-open primary, MOC and 0% cash sensitivities."""
    print("=" * 80)
    print("LRS SOXL BACKTEST (Inception - Present)")
    print("=" * 80)

    data = load_data()
    df = calculate_returns(data, 'next_open')
    moc = calculate_returns(data, 'moc')
    no_cash = calculate_returns(data, 'next_open', cash_rate=0.0)

    bh, spx = df['BH_Return'], df['SP500_Return']
    metrics = {
        'Buy & Hold SOXL': calculate_metrics(df['BH_Value'], bh, bh, spx),
        'LRS Baseline': calculate_metrics(df['Baseline_Value'], df['Baseline_Return'], bh, spx),
        'Hybrid Sniper': calculate_metrics(df['Sniper_Value'], df['Sniper_Return'], bh, spx),
        'LRS Baseline (MOC)': calculate_metrics(moc['Baseline_Value'], moc['Baseline_Return'], bh, spx),
        'Hybrid Sniper (MOC)': calculate_metrics(moc['Sniper_Value'], moc['Sniper_Return'], bh, spx),
        'Hybrid Sniper (0% cash)': calculate_metrics(no_cash['Sniper_Value'], no_cash['Sniper_Return'], bh, spx),
    }
    fills = {'Buy & Hold SOXL': 'close', 'LRS Baseline': 'next_open', 'Hybrid Sniper': 'next_open',
             'LRS Baseline (MOC)': 'moc', 'Hybrid Sniper (MOC)': 'moc', 'Hybrid Sniper (0% cash)': 'next_open'}

    print("\n" + "=" * 80)
    print("PERFORMANCE SUMMARY (SOXL; primary = next-open fills)")
    print("=" * 80)
    print(f"{'Strategy':<24} {'CAGR':>9} {'Max DD':>9} {'Sharpe':>7} {'Beta(SPX)':>9} {'Alpha(SPX)':>10} {'Final Value':>14}")
    print("-" * 80)
    for name, m in sorted(metrics.items(), key=lambda x: x[1]['Final_Value'], reverse=True):
        print(f"{name:<24} {m['CAGR']*100:>8.2f}% {m['Max_Drawdown']*100:>8.2f}% "
              f"{m['Sharpe']:>7.2f} {m['Beta_SPX']:>9.2f} {m['Alpha_SPX']*100:>9.2f}% ${m['Final_Value']:>13,.0f}")
    print("=" * 80)

    metrics_df = pd.DataFrame(metrics).T
    metrics_df.insert(0, 'Fill', pd.Series(fills))
    metrics_df.index.name = 'Strategy'
    metrics_df['Start'] = df.index[0].date()
    metrics_df['End'] = df.index[-1].date()
    metrics_df.to_csv(os.path.join(RESULTS_DIR, 'soxl_performance_summary.csv'))

    trades = generate_transaction_log(df)
    trades.to_csv(os.path.join(RESULTS_DIR, 'transactions_soxl.csv'), index=False)
    print(f"Total trades for Hybrid Sniper SOXL: {len(trades)}")

    df.to_csv(os.path.join(RESULTS_DIR, 'soxl_backtest_daily.csv'))

    plot_results(df)
    plot_trades(df, trades)

    return df, metrics, trades


if __name__ == "__main__":
    main()
