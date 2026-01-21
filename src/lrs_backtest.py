#!/usr/bin/env python3
"""
Leverage Rotation Strategy (LRS) Backtest

Implements the strategy from "Leverage for the Long Run" by Michael A. Gayed.
- Hold leveraged S&P 500 when price > 200-day SMA (Risk-On)
- Hold T-Bills (cash) when price < 200-day SMA (Risk-Off)
"""

import os
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime
import warnings
from matplotlib.backends.backend_pdf import PdfPages

warnings.filterwarnings('ignore')


# Configuration
START_DATE = '1990-01-01'
END_DATE = datetime.now().strftime('%Y-%m-%d')
INITIAL_CAPITAL = 10000
DAILY_FEE = 0.01 / 252
RISK_FREE_RATE = 0.03

SMA_PERIOD = 200
BUFFER = 0.02 # 2% buffer

# Directories
DATA_DIR = 'data'
PLOTS_DIR = 'plots'
RESULTS_DIR = 'results'

def calculate_signals(df):
    """Calculate 200-day SMA and generate buy/sell signals."""
    df = df.copy()
    df['SMA_200'] = df['Close'].rolling(window=SMA_PERIOD).mean()
    df['MA_10'] = df['Close'].rolling(window=10).mean() # Changed to MA 10
    
    # Apply Hysteresis (Buffer) Logic:
    # - Switch to Risk-On (1) only if MA_10 > SMA * (1 + BUFFER)
    # - Switch to Risk-Off (0) only if MA_10 < SMA * (1 - BUFFER)
    
    regime = []
    current_state = 0 # Assume start in Risk-Off
    
    for i in range(len(df)):
        close = df['Close'].iloc[i]
        ma_price = df['MA_10'].iloc[i] # Use MA 10
        sma = df['SMA_200'].iloc[i]
        
        if pd.isna(sma) or pd.isna(ma_price):
            regime.append(0)
            continue
            
        upper_band = sma * (1 + BUFFER)
        lower_band = sma * (1 - BUFFER)
        
        if ma_price > upper_band:
            current_state = 1
        elif ma_price < lower_band:
            current_state = 0
        # else: keep current_state
        
        regime.append(current_state)

        
    df['Regime'] = regime

    # Use previous day's regime for today's allocation (avoid look-ahead bias)
    df['Signal'] = df['Regime'].shift(1)
    
    return df


def calculate_returns(df, leverage=2):
    """Calculate daily returns for different strategies."""
    df = df.copy()
    
    # Daily index return
    df['Index_Return'] = df['Close'].pct_change()
    
    # Leveraged return (with daily fee)
    # Calculate SPX 3x Returns (Real if available, else Simulated)
    if 'UPRO_Returns' in df.columns:
        df['SPX_3x_Return'] = df['UPRO_Returns']
    else:
        df['SPX_3x_Return'] = (df['Index_Return'] * 3) - DAILY_FEE
    
    # Calculate TQQQ Returns (Real/Synthetic)
    if 'TQQQ_Returns' in df.columns:
        df['TQQQ_Return'] = df['TQQQ_Returns']
    else:
        df['TQQQ_Return'] = df['SPX_3x_Return'] # Fallback
    
    # Cash return (simplified: use average T-Bill rate)
    df['Cash_Return'] = RISK_FREE_RATE / 252
    
    # Strategy Returns (LRS)
    # If Regime=1 (Risk-On), use Leveraged Return; else Cash
    # We calculate TWO strategy streams now: LRS_SPX3x and LRS_TQQQ
    
    df['LRS_SPX3x_Return'] = np.where(df['Regime'].shift(1) == 1, df['SPX_3x_Return'], df['Cash_Return'])
    df['LRS_TQQQ_Return'] = np.where(df['Regime'].shift(1) == 1, df['TQQQ_Return'], df['Cash_Return'])
    
    # Benchmark Returns (Buy-Hold)
    df['BH_SPX3x_Return'] = (df['SPX_3x_Return'])
    df['BH_TQQQ_Return'] = (df['TQQQ_Return'])
    df['BH_Index_Return'] = (df['Index_Return'])
    
    return df


def calculate_cumulative_returns(df):
    """Calculate cumulative returns for all strategies."""
    df['LRS_SPX3x_Value'] = INITIAL_CAPITAL * (1 + df['LRS_SPX3x_Return']).cumprod()
    df['LRS_TQQQ_Value'] = INITIAL_CAPITAL * (1 + df['LRS_TQQQ_Return']).cumprod()
    
    df['BH_SPX3x_Value'] = INITIAL_CAPITAL * (1 + df['BH_SPX3x_Return']).cumprod()
    df['BH_TQQQ_Value'] = INITIAL_CAPITAL * (1 + df['BH_TQQQ_Return']).cumprod()
    df['BH_Index_Value'] = INITIAL_CAPITAL * (1 + df['BH_Index_Return']).cumprod()
    
    return df


def calculate_metrics(df, column):
    """Calculate performance metrics for a strategy."""
    values = df[column].dropna()
    
    # Map value columns to return columns
    return_col_map = {
        'LRS_Value': 'LRS_Return',
        'BH_Lev_Value': 'BH_Leveraged_Return',
        'BH_Index_Value': 'BH_Index_Return',
        'LRS_SPX3x_Value': 'LRS_SPX3x_Return',
        'LRS_TQQQ_Value': 'LRS_TQQQ_Return',
        'BH_SPX3x_Value': 'BH_SPX3x_Return',
        'BH_TQQQ_Value': 'BH_TQQQ_Return',
        'BH_Index_Value': 'BH_Index_Return'
    }
    return_col = return_col_map.get(column, column.replace('_Value', '_Return'))
    returns = df[return_col].dropna()
    
    # Time period
    years = (df.index[-1] - df.index[0]).days / 365.25
    
    # CAGR
    final_value = values.iloc[-1]
    initial_value = values.iloc[0] if values.iloc[0] != 0 else INITIAL_CAPITAL
    cagr = (final_value / initial_value) ** (1 / years) - 1
    
    # Max Drawdown
    running_max = values.cummax()
    drawdown = (values - running_max) / running_max
    max_drawdown = drawdown.min()
    
    # Sharpe Ratio (annualized)
    excess_returns = returns - (RISK_FREE_RATE / 252)
    sharpe = (excess_returns.mean() * 252) / (returns.std() * np.sqrt(252))
    
    # Annualized volatility
    volatility = returns.std() * np.sqrt(252)
    
    return {
        'CAGR': cagr,
        'Max_Drawdown': max_drawdown,
        'Sharpe_Ratio': sharpe,
        'Volatility': volatility,
        'Final_Value': final_value
    }


def plot_results(df, leverage):
    """Generate and save performance plots."""
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    
    # Plot 1: Cumulative Returns (Log Scale)
    ax1 = axes[0]
    ax1.semilogy(df.index, df['LRS_Value'], label=f'LRS {leverage}x', linewidth=2, color='blue')
    ax1.semilogy(df.index, df['BH_Lev_Value'], label=f'Buy-Hold {leverage}x', linewidth=1.5, color='red', alpha=0.7)
    ax1.semilogy(df.index, df['BH_Index_Value'], label='Buy-Hold S&P 500', linewidth=1.5, color='green', alpha=0.7)
    ax1.set_title(f'Leverage Rotation Strategy ({leverage}x) vs Buy-and-Hold', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Portfolio Value ($, log scale)')
    
    # Update title for TQQQ
    title_label = f'LRS TQQQ' if leverage == 3 else f'LRS {leverage}x'
    ax1.set_title(f'{title_label} Strategy vs Buy-and-Hold', fontsize=14, fontweight='bold')
    
    # Update legend for TQQQ
    handles, labels = ax1.get_legend_handles_labels()
    new_labels = []
    for l in labels:
        if 'LRS 3x' in l: new_labels.append('LRS TQQQ (Synthetic)')
        elif 'Buy-Hold 3x' in l: new_labels.append('Buy-Hold TQQQ (Synthetic)')
        else: new_labels.append(l)
    ax1.legend(handles, new_labels, loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=INITIAL_CAPITAL, color='gray', linestyle='--', alpha=0.5)
    
    # Plot 2: Drawdowns
    ax2 = axes[1]
    for col, label, color in [('LRS_Value', f'LRS {leverage}x', 'blue'), 
                               ('BH_Lev_Value', f'Buy-Hold {leverage}x', 'red'),
                               ('BH_Index_Value', 'Buy-Hold S&P 500', 'green')]:
        running_max = df[col].cummax()
        drawdown = (df[col] - running_max) / running_max * 100
        ax2.fill_between(df.index, drawdown, 0, alpha=0.3, label=label)
        ax2.plot(df.index, drawdown, linewidth=0.5, color=color)
    
    ax2.set_title('Drawdowns', fontsize=14, fontweight='bold')
    ax2.set_ylabel('Drawdown (%)')
    ax2.legend(loc='lower left')
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: Regime (Risk-On vs Risk-Off periods)
    ax3 = axes[2]
    ax3.plot(df.index, df['Close'], label='S&P 500', linewidth=1, color='black')
    ax3.plot(df.index, df['SMA_200'], label='200-day SMA', linewidth=1, color='orange')
    
    # Shade Risk-On periods
    risk_on = df['Signal'] == 1
    ax3.fill_between(df.index, df['Close'].min() * 0.9, df['Close'].max() * 1.1,
                     where=risk_on, alpha=0.2, color='green', label='Risk-On (Invested)')
    ax3.fill_between(df.index, df['Close'].min() * 0.9, df['Close'].max() * 1.1,
                     where=~risk_on, alpha=0.2, color='red', label='Risk-Off (Cash)')
    
    ax3.set_title('S&P 500 with 200-day SMA and Regime', fontsize=14, fontweight='bold')
    ax3.set_ylabel('Price')
    ax3.set_xlabel('Date')
    ax3.legend(loc='upper left')
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim(df['Close'].min() * 0.9, df['Close'].max() * 1.1)
    
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, f'lrs_backtest_{leverage}x.pdf'), dpi=150, bbox_inches='tight')
    plt.savefig(os.path.join(PLOTS_DIR, f'lrs_backtest_{leverage}x.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved plots to {PLOTS_DIR}/lrs_backtest_{leverage}x.pdf")


def print_summary(metrics_dict):
    """Print formatted performance summary."""
    print("\n" + "=" * 80)
    print("PERFORMANCE SUMMARY")
    print("=" * 80)
    print(f"{'Strategy':<25} {'CAGR':>12} {'Max DD':>12} {'Sharpe':>12} {'Final Value':>15}")
    print("-" * 80)
    
    for strategy, metrics in metrics_dict.items():
        print(f"{strategy:<25} {metrics['CAGR']*100:>11.2f}% {metrics['Max_Drawdown']*100:>11.2f}% "
              f"{metrics['Sharpe_Ratio']:>12.2f} ${metrics['Final_Value']:>14,.0f}")
    
    print("=" * 80)


def save_results(metrics_dict, df, leverage):
    """Save results to CSV files."""
    # Performance summary
    summary_df = pd.DataFrame(metrics_dict).T
    summary_df.to_csv(os.path.join(RESULTS_DIR, f'performance_summary_{leverage}x.csv'))
    
    # Trade log (regime changes)
    regime_changes = df[df['Regime'] != df['Regime'].shift(1)].copy()
    regime_changes['Action'] = regime_changes['Regime'].map({1: 'BUY (Risk-On)', 0: 'SELL (Risk-Off)'})
    regime_changes[['Close', 'SMA_200', 'Regime', 'Action']].to_csv(
        os.path.join(RESULTS_DIR, f'trade_log_{leverage}x.csv')
    )
    
    print(f"Saved results to {RESULTS_DIR}/")


def plot_trades(df, transactions):
    """Generate a multi-page PDF with plots for all trades."""
    if transactions.empty:
        print("No trades found.")
        return

    pdf_path = os.path.join(PLOTS_DIR, f'trades_comparison.pdf')
    with PdfPages(pdf_path) as pdf:
        for idx, trade in transactions.iterrows():
            entry_date = pd.to_datetime(trade['Entry_Date'])
            exit_date = pd.to_datetime(trade['Exit_Date'])
            
            # Define window (60 days padding)
            start_window = entry_date - pd.Timedelta(days=60)
            end_window = exit_date + pd.Timedelta(days=60)
            
            # Slice data
            mask = (df.index >= start_window) & (df.index <= end_window)
            subset = df.loc[mask].copy()
            
            if subset.empty:
                continue
            
            # 2 Panels: Top = Signals, Bottom = TQQQ
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={'height_ratios': [1, 1]})
            
            # --- Top Panel: SPX Signals ---
            ax1.plot(subset.index, subset['Close'], label='S&P 500', color='black', linewidth=1, alpha=0.6)
            # Use MA_10 if available, else MA_5 (for backwards compatibility if needed, but we switched to 10)
            if 'MA_10' in subset.columns:
                ax1.plot(subset.index, subset['MA_10'], label='MA 10', color='blue', linewidth=1)
            else:
                ax1.plot(subset.index, subset['MA_5'], label='MA 5', color='blue', linewidth=1)
                
            ax1.plot(subset.index, subset['SMA_200'], label='200-day SMA', color='orange', linestyle='--', linewidth=1)
            
            # Mark Entry/Exit on SPX
            spx_entry = subset.loc[subset.index >= entry_date, 'Close'].iloc[0] if not subset.loc[subset.index >= entry_date].empty else None
            spx_exit = subset.loc[subset.index >= exit_date, 'Close'].iloc[0] if not subset.loc[subset.index >= exit_date].empty else None
            
            if spx_entry: ax1.scatter(entry_date, spx_entry, color='green', marker='^', s=100, label='Entry Signal', zorder=5)
            if spx_exit: ax1.scatter(exit_date, spx_exit, color='red', marker='v', s=100, label='Exit Signal', zorder=5)
            
            title_text = f"Trade #{idx} | {entry_date.date()} to {exit_date.date()} ({trade['Duration_Days']} days) | S&P 500 Context"
            ax1.set_title(title_text, fontsize=11, fontweight='bold')
            ax1.set_ylabel('S&P 500 Index')
            ax1.legend(loc='upper left', fontsize='small')
            ax1.grid(True, alpha=0.3)
            
            # --- Bottom Panel: TQQQ --- (Previously ax3)
            # Use Real TQQQ Close Price
            ax2.plot(subset.index, subset['TQQQ_Close'], label='TQQQ Price', color='purple', linewidth=1.5)
            ax2.axvspan(entry_date, exit_date, alpha=0.1, color='green', label='Active Trade')
            ret_tqqq = trade['Return_TQQQ'] * 100
            duration = trade['Duration_Days']
            ax2.set_title(f"TQQQ Performance: {ret_tqqq:.2f}% ({duration} days)", fontsize=10, fontweight='bold')
            ax2.set_ylabel('TQQQ Price ($)')
            ax2.grid(True, alpha=0.3)
             # Mark markers
            t_entry = subset.loc[subset.index >= entry_date, 'TQQQ_Close'].iloc[0] if not subset.loc[subset.index >= entry_date].empty else None
            t_exit = subset.loc[subset.index >= exit_date, 'TQQQ_Close'].iloc[0] if not subset.loc[subset.index >= exit_date].empty else None
            if t_entry: ax2.scatter(entry_date, t_entry, color='green', marker='^', s=80)
            if t_exit: ax2.scatter(exit_date, t_exit, color='red', marker='v', s=80)
            
            plt.subplots_adjust(hspace=0.2)
            pdf.savefig(fig)
            plt.close(fig)
            
    print(f"Saved comparison trade plots to {pdf_path}")



def generate_transaction_log(df):
    """Generate a detailed list of all Risk-On trades."""
    df = df.dropna(subset=['Signal'])
    
    trades = []
    in_trade = False
    entry_date = None
    entry_price = None # SPX Price
    trade_start_idx = None
    
    for i in range(len(df)):
        date = df.index[i]
        signal = df['Signal'].iloc[i]
        
        # Start of Risk-On trade (Signal 0 -> 1)
        if signal == 1 and not in_trade:
            in_trade = True
            entry_idx = i - 1 if i > 0 else 0
            entry_date = df.index[entry_idx]
            entry_price = df['Close'].iloc[entry_idx]
            trade_start_idx = i
            
        # End of Risk-On trade (Signal 1 -> 0 or End of Data)
        elif in_trade and (signal == 0 or i == len(df) - 1):
            in_trade = False
            exit_idx = i - 1
            exit_date = df.index[exit_idx]
            exit_price = df['Close'].iloc[exit_idx]
            
            # Calculate returns for BOTH assets
            spx3x_period = df['LRS_SPX3x_Return'].iloc[trade_start_idx : exit_idx + 1]
            spx3x_ret = (1 + spx3x_period).prod() - 1
            
            tqqq_period = df['LRS_TQQQ_Return'].iloc[trade_start_idx : exit_idx + 1]
            tqqq_ret = (1 + tqqq_period).prod() - 1
            
            trades.append({
                'Entry_Date': entry_date,
                'Exit_Date': exit_date,
                'Duration_Days': (exit_date - entry_date).days,
                'Return_SPX3x': spx3x_ret,
                'Return_TQQQ': tqqq_ret,
            })
    
    trades_df = pd.DataFrame(trades)
    return trades_df



def run_comparison(start_date='2010-01-01'):
    """Run Comparison: SPX 3x vs TQQQ."""
    print(f"\n{'='*80}")
    print(f"Running COMPARISON Backtest: SPX 3x vs TQQQ (From {start_date})")
    print(f"{'='*80}")
    
    # Download/Load and Align
    sp500_path = os.path.join(DATA_DIR, 'sp500.csv')
    ndx_path = os.path.join(DATA_DIR, 'ndx.csv')
    tqqq_path = os.path.join(DATA_DIR, 'tqqq.csv')
    upro_path = os.path.join(DATA_DIR, 'upro.csv')
    
    if os.path.exists(sp500_path) and os.path.exists(ndx_path) and os.path.exists(tqqq_path) and os.path.exists(upro_path):
        print("Loading existing data...")
        df = pd.read_csv(sp500_path, index_col=0, parse_dates=True)
        ndx = pd.read_csv(ndx_path, index_col=0, parse_dates=True)
        tqqq = pd.read_csv(tqqq_path, index_col=0, parse_dates=True)
        upro = pd.read_csv(upro_path, index_col=0, parse_dates=True)
    else:
        df, ndx, tqqq, upro = download_data()
    
    # Align
    common_idx = df.index.intersection(ndx.index)
    df = df.loc[common_idx]
    
    # Preserve Real Prices for Plotting
    # Reindex TQQQ and UPRO Close to match df index
    df['TQQQ_Close'] = tqqq['Close'].reindex(df.index)
    df['UPRO_Close'] = upro['Close'].reindex(df.index)
    
    # TQQQ Data Prep (Real Data Only)
    tqqq_returns = tqqq['Close'].pct_change()
    tqqq_returns = tqqq_returns.reindex(df.index)
    
    # Use real returns only; do not fillna with synthetic
    df['TQQQ_Returns'] = tqqq_returns

    # UPRO Data Prep
    upro_returns = upro['Close'].pct_change()
    upro_returns = upro_returns.reindex(df.index)
    df['UPRO_Returns'] = upro_returns
    
    # Calculate Signals
    df = calculate_signals(df)
    
    # Calculate Returns (comparison logic modified in function)
    df = calculate_returns(df, leverage=3) # leverage arg ignored for structure but we calc columns
    
    # Filter
    df = df[df.index >= pd.Timestamp(start_date)]
    
    # Cum Returns
    df = calculate_cumulative_returns(df)
    
    # Metrics
    metrics = {
        'LRS SPX 3x': calculate_metrics(df, 'LRS_SPX3x_Value'),
        'LRS TQQQ': calculate_metrics(df, 'LRS_TQQQ_Value'),
        'Buy-Hold TQQQ': calculate_metrics(df, 'BH_TQQQ_Value'),
        'Buy-Hold SPX': calculate_metrics(df, 'BH_Index_Value')
    }
    
    print_summary(metrics)
    
    # Plot Overall Comparison
    # We'll do a simple comparison plot here tailored for this
    plt.figure(figsize=(12, 6))
    plt.semilogy(df.index, df['LRS_SPX3x_Value'], label='LRS SPX 3x', color='blue')
    plt.semilogy(df.index, df['LRS_TQQQ_Value'], label='LRS TQQQ', color='purple')
    plt.semilogy(df.index, df['BH_TQQQ_Value'], label='Buy-Hold TQQQ', color='gray', linestyle='--', alpha=0.5)
    plt.title('Strategy Comparison: SPX 3x vs TQQQ')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(PLOTS_DIR, 'comparison_equity.png'))
    plt.savefig(os.path.join(PLOTS_DIR, 'comparison_equity.pdf'))
    plt.close()
    
    # Logs and Plots
    transactions = generate_transaction_log(df)
    transactions.to_csv(os.path.join(RESULTS_DIR, 'transactions_comparison.csv'))
    
    plot_trades(df, transactions)
    
    return df, metrics

if __name__ == "__main__":
    run_comparison(start_date='2010-01-01')
