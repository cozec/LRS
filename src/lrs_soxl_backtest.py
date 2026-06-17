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

# Configuration
INITIAL_CAPITAL = 10000
RISK_FREE_RATE = 0.03  # 3% annual cash return
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
    
    # Join SOXL Close
    df = sp500[['Close', 'SMA_200', 'MA_10', 'RSI', 'Upper_Band', 'Lower_Band']].copy()
    df.columns = ['SP500_Close', 'SMA_200', 'MA_10', 'RSI', 'Upper_Band', 'Lower_Band']
    
    df = df.join(soxl[['Close']].rename(columns={'Close': 'SOXL_Close'}), how='inner')
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


def calculate_returns(df):
    """
    Calculate daily returns for Buy & Hold, Baseline, and Hybrid Sniper strategies.

    Parameters:
    df (pd.DataFrame): Input DataFrame.

    Returns:
    pd.DataFrame: DataFrame with strategy return columns.
    """
    df = df.copy()
    
    # SOXL daily returns
    df['SOXL_Return'] = df['SOXL_Close'].pct_change().fillna(0)
    
    # SP500 daily returns (for Alpha/Beta calculations)
    df['SP500_Return'] = df['SP500_Close'].pct_change().fillna(0)
    
    # Cash daily return
    df['Cash_Return'] = RISK_FREE_RATE / 252
    
    # Buy & Hold SOXL daily return
    df['BH_Return'] = df['SOXL_Return']
    
    # Baseline return
    df['Baseline_Return'] = np.where(
        df['Baseline_Signal'] == 1,
        df['SOXL_Return'],
        df['Cash_Return']
    )
    
    # Hybrid Sniper return
    df['Sniper_Return'] = df['Sniper_Signal'] * df['SOXL_Return'] + \
                          (1 - df['Sniper_Signal']) * df['Cash_Return']
                          
    return df


def calculate_cumulative_returns(df):
    """
    Calculate cumulative values for all strategies.

    Parameters:
    df (pd.DataFrame): Input DataFrame.

    Returns:
    pd.DataFrame: DataFrame with cumulative value columns.
    """
    df = df.copy()
    
    # For Buy & Hold, use the exact formula $10,000 * (last_close / first_close)
    first_soxl = df['SOXL_Close'].iloc[0]
    df['BH_Value'] = INITIAL_CAPITAL * (df['SOXL_Close'] / first_soxl)
    
    # For S&P 500 buy & hold (reference)
    first_sp500 = df['SP500_Close'].iloc[0]
    df['SP500_Value'] = INITIAL_CAPITAL * (df['SP500_Close'] / first_sp500)
    
    # For active strategies: Compound daily returns
    df['Baseline_Value'] = INITIAL_CAPITAL * (1 + df['Baseline_Return']).cumprod()
    df['Sniper_Value'] = INITIAL_CAPITAL * (1 + df['Sniper_Return']).cumprod()
    
    return df


def calculate_metrics(values, daily_returns, benchmark_returns, sp500_returns):
    """
    Calculate professional performance metrics.

    Parameters:
    values (pd.Series): Portfolio equity values.
    daily_returns (pd.Series): Daily returns of the strategy.
    benchmark_returns (pd.Series): Daily returns of the Buy & Hold asset.
    sp500_returns (pd.Series): Daily returns of S&P 500.

    Returns:
    dict: Performance metrics.
    """
    days = len(values)
    years = days / 252
    
    final_value = values.iloc[-1]
    total_return = (final_value / INITIAL_CAPITAL) - 1
    cagr = (final_value / INITIAL_CAPITAL) ** (1 / years) - 1
    
    # Max DD
    running_max = values.cummax()
    drawdown = (values - running_max) / running_max
    max_dd = drawdown.min()
    
    # Volatility
    volatility = daily_returns.std() * np.sqrt(252)
    
    # Sharpe
    excess_returns = daily_returns - (RISK_FREE_RATE / 252)
    sharpe = (excess_returns.mean() * 252) / volatility if volatility > 0 else 0
    
    # Sortino
    downside_returns = daily_returns[daily_returns < 0]
    downside_std = downside_returns.std() * np.sqrt(252)
    sortino = (daily_returns.mean() * 252 - RISK_FREE_RATE) / downside_std if downside_std > 0 else 0
    
    # Calmar
    calmar = cagr / abs(max_dd) if max_dd != 0 else 0
    
    # Beta relative to Buy & Hold of the asset itself
    df_cov_bh = pd.DataFrame({'strat': daily_returns, 'bench': benchmark_returns}).dropna()
    cov_matrix_bh = np.cov(df_cov_bh['strat'], df_cov_bh['bench'])
    beta_bh = cov_matrix_bh[0, 1] / cov_matrix_bh[1, 1] if cov_matrix_bh[1, 1] != 0 else 0.0
    
    # Alpha relative to Buy & Hold of the asset
    strat_ann = (1 + df_cov_bh['strat']).prod() ** (252 / len(df_cov_bh)) - 1
    bench_ann = (1 + df_cov_bh['bench']).prod() ** (252 / len(df_cov_bh)) - 1
    alpha_bh = (strat_ann - RISK_FREE_RATE) - beta_bh * (bench_ann - RISK_FREE_RATE)
    
    # Beta relative to S&P 500 (broad market index)
    df_cov_spx = pd.DataFrame({'strat': daily_returns, 'spx': sp500_returns}).dropna()
    cov_matrix_spx = np.cov(df_cov_spx['strat'], df_cov_spx['spx'])
    beta_spx = cov_matrix_spx[0, 1] / cov_matrix_spx[1, 1] if cov_matrix_spx[1, 1] != 0 else 0.0
    
    # Alpha relative to S&P 500 (broad market index)
    spx_ann = (1 + df_cov_spx['spx']).prod() ** (252 / len(df_cov_spx)) - 1
    alpha_spx = (strat_ann - RISK_FREE_RATE) - beta_spx * (spx_ann - RISK_FREE_RATE)
    
    return {
        'Final_Value': final_value,
        'Total_Return': total_return,
        'CAGR': cagr,
        'Max_Drawdown': max_dd,
        'Volatility': volatility,
        'Sharpe': sharpe,
        'Sortino': sortino,
        'Calmar': calmar,
        'Beta_BH': beta_bh,
        'Alpha_BH': alpha_bh,
        'Beta_SPX': beta_spx,
        'Alpha_SPX': alpha_spx
    }


def generate_transaction_log(df):
    """
    Generate a transaction log for the Hybrid Sniper strategy on SOXL.

    Parameters:
    df (pd.DataFrame): Input DataFrame.

    Returns:
    pd.DataFrame: Trade log DataFrame.
    """
    df = df.dropna(subset=['Sniper_Signal']).copy()
    trades = []
    in_trade = False
    entry_date = None
    entry_type = "Unknown"
    entry_idx = 0
    
    for i in range(len(df)):
        signal = df['Sniper_Signal'].iloc[i]
        
        # Entry
        if signal > 0 and not in_trade:
            in_trade = True
            entry_idx = i
            entry_date = df.index[i]
            entry_type = "Sniper (RSI)" if signal == 0.5 else "Trend (SMA)"
            
        # Exit
        elif in_trade and signal == 0:
            in_trade = False
            exit_date = df.index[i]
            
            trade_returns = df['Sniper_Return'].iloc[entry_idx:i+1]
            trade_ret = (1 + trade_returns).prod() - 1
            
            soxl_returns = df['SOXL_Return'].iloc[entry_idx:i+1]
            soxl_ret = (1 + soxl_returns).prod() - 1
            
            trades.append({
                'Entry_Date': entry_date,
                'Exit_Date': exit_date,
                'Duration_Days': (exit_date - entry_date).days,
                'Type': entry_type,
                'Status': 'CLOSED',
                'Return_Strategy': trade_ret,
                'Return_SOXL': soxl_ret
            })
            
    # Open trade at end (still active, NOT a real exit)
    if in_trade:
        exit_date = df.index[-1]
        trade_returns = df['Sniper_Return'].iloc[entry_idx:]
        trade_ret = (1 + trade_returns).prod() - 1
        soxl_returns = df['SOXL_Return'].iloc[entry_idx:]
        soxl_ret = (1 + soxl_returns).prod() - 1
        
        trades.append({
            'Entry_Date': entry_date,
            'Exit_Date': exit_date,
            'Duration_Days': (exit_date - entry_date).days,
            'Type': entry_type,
            'Status': 'OPEN',
            'Return_Strategy': trade_ret,
            'Return_SOXL': soxl_ret
        })
        
    return pd.DataFrame(trades)


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
            title_text = f"Trade #{idx+1} ({trade_type}) | {entry_date.date()} to {exit_date.date()} | {trade['Duration_Days']} days | Return: {ret_str}"
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
    """Main execution function for the backtest."""
    print("=" * 80)
    print("LRS SOXL BACKTEST (Inception - Present)")
    print("=" * 80)
    
    # Load and align data
    df = load_data()
    
    # Calculate strategy signals
    df = calculate_baseline_signal(df)
    df = calculate_sniper_signal(df)
    
    # Calculate strategy returns
    df = calculate_returns(df)
    
    # Calculate cumulative returns
    df = calculate_cumulative_returns(df)
    
    # Slice to final period where metrics are valid
    df = df.dropna(subset=['SMA_200'])
    
    # Calculate metrics
    metrics = {
        'Buy & Hold SOXL': calculate_metrics(df['BH_Value'], df['BH_Return'], df['BH_Return'], df['SP500_Return']),
        'LRS Baseline': calculate_metrics(df['Baseline_Value'], df['Baseline_Return'], df['BH_Return'], df['SP500_Return']),
        'Hybrid Sniper': calculate_metrics(df['Sniper_Value'], df['Sniper_Return'], df['BH_Return'], df['SP500_Return'])
    }
    
    # Print metrics
    print("\n" + "=" * 80)
    print("PERFORMANCE SUMMARY (SOXL)")
    print("=" * 80)
    print(f"{'Strategy':<20} {'CAGR':>10} {'Max DD':>10} {'Sharpe':>8} {'Beta (SPX)':>10} {'Alpha (SPX)':>12} {'Final Value':>15}")
    print("-" * 80)
    
    # Sort strategies by final equity descending
    sorted_strategies = sorted(metrics.items(), key=lambda x: x[1]['Final_Value'], reverse=True)
    
    for name, m in sorted_strategies:
        print(f"{name:<20} {m['CAGR']*100:>9.2f}% {m['Max_Drawdown']*100:>9.2f}% "
              f"{m['Sharpe']:>8.2f} {m['Beta_SPX']:>10.2f} {m['Alpha_SPX']*100:>11.2f}% ${m['Final_Value']:>14,.0f}")
    print("=" * 80)
    
    # Save performance metrics to CSV
    metrics_df = pd.DataFrame(metrics).T
    metrics_df.to_csv(os.path.join(RESULTS_DIR, 'soxl_performance_summary.csv'))
    
    # Generate transaction log
    trades = generate_transaction_log(df)
    trades.to_csv(os.path.join(RESULTS_DIR, 'transactions_soxl.csv'), index=False)
    print(f"Total trades for Hybrid Sniper SOXL: {len(trades)}")
    
    # Save full historical backtest data for visual verification if needed
    df.to_csv(os.path.join(RESULTS_DIR, 'soxl_backtest_daily.csv'))
    
    # Plots
    plot_results(df)
    plot_trades(df, trades)
    
    return df, metrics, trades


if __name__ == "__main__":
    main()
