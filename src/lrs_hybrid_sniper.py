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
from backtest_common import DATA_DIR, PLOTS_DIR, RESULTS_DIR  # noqa: E402
import backtest_common as bc  # noqa: E402

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
            
            # 3 Panels: Top = Price/SMA, Middle = RSI, Bottom = TQQQ
            # Letter Page is 8.5 x 11. We use (8.5, 11) for full page portrait.
            fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8.5, 11), sharex=True, gridspec_kw={'height_ratios': [2, 1, 2]})
            
            # --- Top Panel: SPX Signals ---
            ax1.plot(subset.index, subset['Close'], label='S&P 500', color='black', linewidth=1, alpha=0.6)
            if 'MA_10' in subset.columns:
                ax1.plot(subset.index, subset['MA_10'], label='MA 10', color='blue', linewidth=1)
            ax1.plot(subset.index, subset['SMA_200'], label='MA 200', color='orange', linestyle='--', linewidth=1)
            
            # Shaded Buffer Zone (±2%)
            upper_buffer = subset['SMA_200'] * 1.02
            lower_buffer = subset['SMA_200'] * 0.98
            ax1.fill_between(subset.index, lower_buffer, upper_buffer, color='orange', alpha=0.15, label='±2% Buffer')
            
            # Determine Reasons
            trade_type = trade.get('Type', 'Unknown')
            entry_reason = "SMA Trend" if "SMA" in trade_type else "RSI Panic"
            
            # Check if this trade is still open
            is_open = trade.get('Status', 'CLOSED') == 'OPEN'
            
            # Exit Reason (from the trade log's actual allocation change)
            exit_reason = trade.get('Exit_Reason', 'Exit')

            # Mark Entry
            spx_entry = subset.loc[subset.index >= entry_date, 'Close'].iloc[0] if not subset.loc[subset.index >= entry_date].empty else None
            if spx_entry: 
                ax1.scatter(entry_date, spx_entry, color='green', marker='^', s=60, zorder=5)
                ax1.annotate('', xy=(entry_date, spx_entry), xytext=(0, 20), 
                             textcoords='offset points', arrowprops=dict(arrowstyle='->', color='green', lw=1.0))

            # Mark Exit
            spx_exit = subset.loc[subset.index >= exit_date, 'Close'].iloc[0] if not subset.loc[subset.index >= exit_date].empty else None
            if spx_exit:
                exit_color = '#ff8c00' if is_open else 'red'
                exit_marker = 'D' if is_open else 'v'
                ax1.scatter(exit_date, spx_exit, color=exit_color, marker=exit_marker, s=60, zorder=5)
                ax1.annotate('', xy=(exit_date, spx_exit), xytext=(0, 20), 
                             textcoords='offset points', arrowprops=dict(arrowstyle='->', color=exit_color, lw=1.0))
            
            trade_type = trade.get('Type', 'Unknown')
            if is_open:
                title_text = f"Trade #{idx} ({trade_type} - Still Open) | {entry_date.date()} to {exit_date.date()} ({trade['Duration_Days']} days)"
            else:
                title_text = f"Trade #{idx} ({trade_type}) | {entry_date.date()} to {exit_date.date()} ({trade['Duration_Days']} days) | Exit: {exit_reason}"
            ax1.set_title(title_text, fontsize=10, fontweight='bold')
            ax1.set_ylabel('S&P 500', fontsize=8)
            ax1.legend(loc='upper left', fontsize='x-small')
            ax1.grid(True, alpha=0.3)
            
            # --- Middle Panel: RSI ---
            if 'RSI' in subset.columns:
                ax2.plot(subset.index, subset['RSI'], label='RSI(14)', color='purple', linewidth=0.8)
                ax2.axhline(30, color='green', linestyle='--', alpha=0.5, label='Oversold (30)')
                ax2.axhline(50, color='gray', linestyle='--', alpha=0.5, label='Neutral (50)')
                ax2.fill_between(subset.index, subset['RSI'], 30, where=(subset['RSI'] < 30), color='green', alpha=0.2)
                
                # Mark RSI Entry/Exit Points
                rsi_entry_val = subset.loc[subset.index >= entry_date, 'RSI'].iloc[0] if not subset.loc[subset.index >= entry_date].empty else None
                rsi_exit_val = subset.loc[subset.index >= exit_date, 'RSI'].iloc[0] if not subset.loc[subset.index >= exit_date].empty else None
                
                if rsi_entry_val:
                    ax2.scatter(entry_date, rsi_entry_val, color='green', s=30, zorder=5)
                if rsi_exit_val:
                    ax2.scatter(exit_date, rsi_exit_val, color='red', s=30, zorder=5)

                ax2.set_ylabel('RSI', fontsize=8)
                ax2.set_ylim(0, 100)
                ax2.legend(loc='upper right', fontsize='x-small')
                ax2.grid(True, alpha=0.3)
            
            # --- Bottom Panel: TQQQ ---
            ax3.plot(subset.index, subset['TQQQ_Close'], label='TQQQ Price', color='teal', linewidth=1.2)
            ax3.axvspan(entry_date, exit_date, alpha=0.1, color='green', label='Active Trade')
            ret_tqqq = trade['Return_TQQQ'] * 100
            ax3.set_title(f"Result: {ret_tqqq:.2f}%", fontsize=9, fontweight='bold')
            ax3.set_ylabel('TQQQ ($)', fontsize=8)
            ax3.grid(True, alpha=0.3)
            
            plt.subplots_adjust(hspace=0.1)
            pdf.savefig(fig)
            plt.close(fig)
            
    print(f"Saved comparison trade plots to {pdf_path}")


def plot_custom_range(df, start_date, end_date, output_filename='custom_plot_covid.pdf'):
    """Generate a single detailed plot for a custom date range."""
    # Define window
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
    mask = (df.index >= start_dt) & (df.index <= end_dt)
    subset = df.loc[mask].copy()
    
    if subset.empty:
        print(f"No data for range {start_date} to {end_date}")
        return

    # Letter Page Portrait (8.5 x 11)
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8.5, 11), sharex=True, gridspec_kw={'height_ratios': [2, 1, 2]})
    
    # --- Top Panel: SPX Signals ---
    ax1.plot(subset.index, subset['Close'], label='S&P 500', color='black', linewidth=1, alpha=0.6)
    if 'MA_10' in subset.columns:
        ax1.plot(subset.index, subset['MA_10'], label='MA 10', color='blue', linewidth=1)
    ax1.plot(subset.index, subset['SMA_200'], label='MA 200', color='orange', linestyle='--', linewidth=1)
    
    # Shaded Buffer Zone (±2%)
    upper_buffer = subset['SMA_200'] * 1.02
    lower_buffer = subset['SMA_200'] * 0.98
    ax1.fill_between(subset.index, lower_buffer, upper_buffer, color='orange', alpha=0.15, label='±2% Buffer')
    
    # Identify Entries and Exits within this window
    # We reconstruct entry/exit events from Signal changes
    subset['Signal_Diff'] = subset['Signal'].diff()
    
    # Entries (Signal Increase)
    entries = subset[subset['Signal_Diff'] > 0]
    for date, row in entries.iterrows():
        price = row['Close']
        sma = row['SMA_200']
        rsi = row['RSI'] if 'RSI' in row else 50
        
        reason = "SMA Trend" if price > sma else "RSI Panic"
        
        ax1.scatter(date, price, color='green', marker='^', s=60, zorder=5)
        # Arrow pointing DOWN to the Entry point (from above)
        ax1.annotate('', xy=(date, price), xytext=(0, 20), 
                     textcoords='offset points', arrowprops=dict(arrowstyle='->', color='green', lw=1.0))
                     
        # RSI Entry Marker
        if 'RSI' in subset.columns:
            ax2.scatter(date, rsi, color='green', s=30, zorder=5)

    # Exits (Signal Decrease)
    exits = subset[subset['Signal_Diff'] < 0]
    for date, row in exits.iterrows():
        price = row['Close']
        # Look at PREVIOUS day's signal to know what we exited FROM
        prev_idx = subset.index.get_loc(date) - 1
        if prev_idx >= 0:
            last_alloc = subset['Signal'].iloc[prev_idx]
            reason = "SMA Break" if last_alloc == 1.0 else "RSI Target"
        else:
            reason = "Exit"
            
        rsi = row['RSI'] if 'RSI' in row else 50

        ax1.scatter(date, price, color='red', marker='v', s=60, zorder=5)
        # Arrow pointing DOWN to the Exit point (from above)
        ax1.annotate('', xy=(date, price), xytext=(0, 20), 
                     textcoords='offset points', arrowprops=dict(arrowstyle='->', color='red', lw=1.0))
                     
        # RSI Exit Marker
        if 'RSI' in subset.columns:
            ax2.scatter(date, rsi, color='red', s=30, zorder=5)

    ax1.set_title(f"Detailed View: {start_date} to {end_date} (COVID Crisis)", fontsize=12, fontweight='bold')
    ax1.set_ylabel('S&P 500', fontsize=8)
    ax1.legend(loc='upper left', fontsize='x-small')
    ax1.grid(True, alpha=0.3)
    
    # --- Middle Panel: RSI ---
    if 'RSI' in subset.columns:
        ax2.plot(subset.index, subset['RSI'], label='RSI(14)', color='purple', linewidth=0.8)
        ax2.axhline(30, color='green', linestyle='--', alpha=0.5, label='Oversold (30)')
        ax2.axhline(50, color='gray', linestyle='--', alpha=0.5, label='Neutral (50)')
        ax2.fill_between(subset.index, subset['RSI'], 30, where=(subset['RSI'] < 30), color='green', alpha=0.2)
        ax2.set_ylabel('RSI', fontsize=8)
        ax2.set_ylim(0, 100)
        ax2.legend(loc='upper right', fontsize='x-small')
        ax2.grid(True, alpha=0.3)
    
    # --- Bottom Panel: TQQQ ---
    ax3.plot(subset.index, subset['TQQQ_Close'], label='TQQQ Price', color='teal', linewidth=1.2)
    
    # Shade active periods based on signal > 0
    # Group consecutive days where Signal > 0
    is_active = subset['Signal'] > 0
    # Find change points
    changes = is_active.ne(is_active.shift()).cumsum()
    for k, group in subset.groupby(changes):
        if group['Signal'].iloc[0] > 0:
            ax3.axvspan(group.index[0], group.index[-1], alpha=0.1, color='green')

    ax3.set_title(f"TQQQ Performance", fontsize=10, fontweight='bold')
    ax3.set_ylabel('TQQQ ($)')
    ax3.grid(True, alpha=0.3)
    
    plt.subplots_adjust(hspace=0.1)
    output_path = os.path.join(PLOTS_DIR, output_filename)
    plt.savefig(output_path)
    plt.close(fig)
    print(f"Saved custom range plot to {output_path}")



def generate_transaction_log(df):
    """Generate a detailed list of all trades (Sniper & Trend).

    Each trade includes a 'Status' field:
    - 'CLOSED': Trade exited by a real signal (SMA breakdown or RSI profit-take).
    - 'OPEN': Trade is still active at the end of available data.
    """
    df = df.dropna(subset=['Signal'])
    
    trades = []
    in_trade = False
    entry_date = None
    trade_start_idx = None
    entry_type = "Unknown"
    
    for i in range(len(df)):
        signal = df['Signal'].iloc[i]
        
        # Start of Trade (Signal > 0)
        # Signal is already Regime.shift(1), so day i is the execution day
        if signal > 0 and not in_trade:
            in_trade = True
            entry_date = df.index[i]
            trade_start_idx = i
            
            # Determine Type: look at the signal generation day's conditions (i-1)
            sig_idx = i - 1 if i > 0 else 0
            rsi_entry = df['RSI'].iloc[sig_idx]
            sma_entry = df['SMA_200'].iloc[sig_idx]
            close_entry = df['Close'].iloc[sig_idx]
            
            if close_entry < sma_entry and rsi_entry < 35:  # Close enough to 30
                entry_type = "Sniper (RSI)"
            else:
                entry_type = "Trend (SMA)"
            
        # End of Trade: Real exit (Signal == 0)
        elif in_trade and signal == 0:
            in_trade = False
            exit_date = df.index[i]
            
            # Calculate returns (include the exit day)
            strat_period = df['LRS_Sniper_Return'].iloc[trade_start_idx:i + 1]
            strat_ret = (1 + strat_period).prod() - 1
            
            tqqq_period = df['TQQQ_Returns'].iloc[trade_start_idx:i + 1]
            tqqq_ret = (1 + tqqq_period).prod() - 1
            
            trades.append({
                'Entry_Date': entry_date,
                'Exit_Date': exit_date,
                'Duration_Days': (exit_date - entry_date).days,
                'Type': entry_type,
                'Status': 'CLOSED',
                'Return_Strategy': strat_ret,
                'Return_TQQQ': tqqq_ret,
            })
    
    # Open trade at end (still active, NOT a real exit)
    if in_trade:
        exit_date = df.index[-1]
        
        strat_period = df['LRS_Sniper_Return'].iloc[trade_start_idx:]
        strat_ret = (1 + strat_period).prod() - 1
        
        tqqq_period = df['TQQQ_Returns'].iloc[trade_start_idx:]
        tqqq_ret = (1 + tqqq_period).prod() - 1
        
        trades.append({
            'Entry_Date': entry_date,
            'Exit_Date': exit_date,
            'Duration_Days': (exit_date - entry_date).days,
            'Type': entry_type,
            'Status': 'OPEN',
            'Return_Strategy': strat_ret,
            'Return_TQQQ': tqqq_ret,
        })
    
    trades_df = pd.DataFrame(trades)
    return trades_df



def baseline_regime(df):
    """
    LRS Baseline regime: 1 when MA10 > SMA200 * 1.02, 0 when MA10 < SMA200 * 0.98,
    otherwise keep the previous state.

    Parameters:
    df (pd.DataFrame): Output of ``calculate_signals_sniper`` (needs MA_10, SMA_200).

    Returns:
    pd.Series: Regime (0.0 or 1.0) decided at each close.
    """
    upper = df['SMA_200'] * (1 + BUFFER)
    lower = df['SMA_200'] * (1 - BUFFER)
    regime = []
    curr = 0.0
    for ma10, up, low in zip(df['MA_10'].values, upper.values, lower.values):
        if np.isnan(ma10) or np.isnan(up):
            regime.append(0.0)
            continue
        if ma10 > up:
            curr = 1.0
        elif ma10 < low:
            curr = 0.0
        regime.append(curr)
    return pd.Series(regime, index=df.index)


def run_comparison(start_date='2010-01-01'):
    """
    Backtest Hybrid Sniper vs LRS Baseline vs Buy & Hold TQQQ.

    Signals come from the full S&P 500 history (no SMA warm-up inside the
    window); the window starts at the first TQQQ bar on/after ``start_date``
    and ends at the last bar shared by S&P 500 and TQQQ. Primary results
    use next-open fills; market-on-close and 0% cash runs are reported as
    labeled sensitivities (see backtest_common).

    Parameters:
    start_date (str): First date of the backtest window.

    Returns:
    tuple: (daily DataFrame, metrics dict for the next-open runs).
    """
    print(f"\n{'='*80}")
    print(f"Running Hybrid Sniper Backtest on TQQQ (From {start_date})")
    print(f"{'='*80}")

    sp500 = bc.load_ohlcv('sp500')
    tqqq = bc.load_ohlcv('tqqq')

    # Signals on the full S&P 500 history, then align to TQQQ
    sig = calculate_signals_sniper(sp500)
    sig['Std_Regime'] = baseline_regime(sig)
    tq = tqqq[['Open', 'Close']].rename(columns={'Open': 'TQQQ_Open', 'Close': 'TQQQ_Close'})
    df = sig.join(tq, how='inner')
    df = df[df.index >= pd.Timestamp(start_date)].copy()
    print(f"Backtest window: {df.index[0].date()} to {df.index[-1].date()} ({len(df)} days)")

    # Weight held during each session under next-open fills (used by plots)
    df['Signal'] = bc.held_weights(df['Regime'])[1]
    df['Std_Signal'] = bc.held_weights(df['Std_Regime'])[1]
    df['TQQQ_Returns'] = df['TQQQ_Close'].pct_change().fillna(0.0)
    spx_ret = df['Close'].pct_change().fillna(0.0)
    bh_ret = df['TQQQ_Returns']

    runs = {
        'Hybrid Sniper': ('Regime', 'next_open', RISK_FREE_RATE),
        'LRS Baseline': ('Std_Regime', 'next_open', RISK_FREE_RATE),
        'Hybrid Sniper (MOC)': ('Regime', 'moc', RISK_FREE_RATE),
        'LRS Baseline (MOC)': ('Std_Regime', 'moc', RISK_FREE_RATE),
        'Hybrid Sniper (0% cash)': ('Regime', 'next_open', 0.0),
    }
    returns = {name: bc.strategy_returns(df[col], df['TQQQ_Open'], df['TQQQ_Close'], fill, cash)
               for name, (col, fill, cash) in runs.items()}

    df['LRS_Sniper_Return'] = returns['Hybrid Sniper']
    df['LRS_Standard_Return'] = returns['LRS Baseline']
    df['LRS_Sniper_Value'] = bc.equity_curve(df['LRS_Sniper_Return'])
    df['LRS_Standard_Value'] = bc.equity_curve(df['LRS_Standard_Return'])
    df['BH_TQQQ_Value'] = bc.buy_hold_equity(df['TQQQ_Close'])

    all_metrics = {'Buy & Hold TQQQ': bc.performance_metrics(df['BH_TQQQ_Value'], bh_ret, bh_ret, spx_ret)}
    for name, r in returns.items():
        all_metrics[name] = bc.performance_metrics(bc.equity_curve(r), r, bh_ret, spx_ret)
    fills = {'Buy & Hold TQQQ': 'close'}
    fills.update({name: fill for name, (_, fill, _) in runs.items()})

    print("\n" + "=" * 80)
    print("PERFORMANCE SUMMARY (TQQQ; primary = next-open fills)")
    print("=" * 80)
    print(f"{'Strategy':<26} {'CAGR':>9} {'Max DD':>9} {'Sharpe':>7} {'Final Value':>14}")
    print("-" * 80)
    for name, m in sorted(all_metrics.items(), key=lambda kv: -kv[1]['Final_Value']):
        print(f"{name:<26} {m['CAGR']*100:>8.2f}% {m['Max_Drawdown']*100:>8.2f}% "
              f"{m['Sharpe']:>7.2f} ${m['Final_Value']:>13,.0f}")
    print("=" * 80)

    metrics_df = pd.DataFrame(all_metrics).T
    metrics_df.insert(0, 'Fill', pd.Series(fills))
    metrics_df.index.name = 'Strategy'
    metrics_df['Start'] = df.index[0].date()
    metrics_df['End'] = df.index[-1].date()
    metrics_df.to_csv(os.path.join(RESULTS_DIR, 'hybrid_sniper_metrics.csv'))

    # Plot Overall Comparison
    plt.figure(figsize=(12, 6))
    plt.semilogy(df.index, df['LRS_Sniper_Value'], label='Hybrid Sniper', color='blue', linewidth=2)
    plt.semilogy(df.index, df['LRS_Standard_Value'], label='LRS Baseline', color='orange', linestyle='--')
    plt.semilogy(df.index, df['BH_TQQQ_Value'], label='Buy & Hold TQQQ', color='gray', linestyle='--', alpha=0.5)
    plt.title('Hybrid Sniper vs Baseline vs Buy & Hold TQQQ (next-open fills)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(PLOTS_DIR, 'comparison_equity_sniper.png'))
    plt.savefig(os.path.join(PLOTS_DIR, 'comparison_equity_sniper.pdf'))
    plt.close()

    transactions = bc.trade_log(df['Regime'], df['LRS_Sniper_Return'],
                                df['TQQQ_Open'], df['TQQQ_Close'])
    transactions = transactions.rename(columns={'Return_Asset': 'Return_TQQQ'})
    transactions.to_csv(os.path.join(RESULTS_DIR, 'transactions_hybrid_sniper.csv'))
    print(f"Trades: {len(transactions)}")

    plot_trades(df, transactions)

    # Custom Plot: COVID Range
    plot_custom_range(df, '2020-01-01', '2022-03-31', 'custom_plot_covid.pdf')

    return df, all_metrics


def calculate_rsi(series, period=14):
    """Calculate RSI using Wilder's Smoothing (Exponential Weighted Moving Average).

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

def calculate_signals_sniper(df):
    """Calculate Signals with Hybrid Sniper Logic."""
    df = df.copy()
    df['SMA_200'] = df['Close'].rolling(window=SMA_PERIOD).mean()
    df['MA_10'] = df['Close'].rolling(window=10).mean()
    df['RSI'] = calculate_rsi(df['Close'], 14)
    
    # Parameters
    RSI_ENTRY = 30
    RSI_EXIT = 50
    SNIPER_ALLOC = 0.5 # 50%
    BUFFER = 0.02
    
    regime = []
    current_state = 0.0 # 0.0 = Cash, 0.5 = Sniper, 1.0 = Bull
    
    # Pre-calculate arrays for speed
    close_vals = df['Close'].values
    ma10_vals = df['MA_10'].values
    sma200_vals = df['SMA_200'].values
    rsi_vals = df['RSI'].values
    
    upper_band = sma200_vals * (1 + BUFFER)
    lower_band = sma200_vals * (1 - BUFFER)
    
    for i in range(len(df)):
        # Skip invalid
        if np.isnan(sma200_vals[i]) or np.isnan(ma10_vals[i]) or np.isnan(rsi_vals[i]):
            regime.append(0.0)
            continue
            
        c = close_vals[i]
        ma10 = ma10_vals[i]
        sma = sma200_vals[i]
        rsi = rsi_vals[i]
        
        # State Machine
        
        # 1. Check Bull Trend Entry (Standard LRS)
        # Priority: If Trend is confirmed, we go ALL IN (1.0).
        # Condition: MA10 > SMA200 * 1.02
        if ma10 > upper_band[i]:
            current_state = 1.0
            
        # 2. Check Bear/Risk-Off Logic
        elif ma10 < lower_band[i]:
            # We are officially in Bear Territory relative to SMA
            # But we might be in Sniper Mode or entering it
            
            if current_state == 1.0:
                # Was Bull, now Bear -> Exit to Cash
                current_state = 0.0
                
            # If Cash (0.0): Look for Sniper Entry
            if current_state == 0.0:
                if rsi < RSI_ENTRY:
                    current_state = SNIPER_ALLOC
            
            # If Sniper (0.5): Check Snipe Exit
            elif current_state == SNIPER_ALLOC:
                if rsi > RSI_EXIT:
                     # Profit Take -> Back to Cash (Wait for next snipe or bull trend)
                     current_state = 0.0
                # Else hold 0.5
        
        # Else (In Hysteresis Zone between 0.98 and 1.02) -> Keep State
        # If State was 1.0, stay 1.0
        # If State was 0.0, stay 0.0
        # If State was 0.5, stay 0.5 (Wait for RSI exit or SMA confirmation)
        
        regime.append(current_state)
        
    df['Regime'] = regime
    df['Signal'] = df['Regime'].shift(1) # Trade next day
    return df

if __name__ == "__main__":
    run_comparison(start_date='2010-01-01')
