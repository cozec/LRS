#!/usr/bin/env python3
"""
LRS Backtest from 1999 using Synthetic TQQQ Data

Backtests 3 strategies from Section 2 of summary.md:
1. Buy & Hold TQQQ
2. LRS Baseline (MA10/200 with 2% buffer)
3. Hybrid Sniper (RSI re-entry)

Uses:
- S&P 500 data for signal calculation (MA, RSI)
- Synthetic TQQQ data from 1999
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import warnings

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
DATA_DIR = 'data'
PLOTS_DIR = 'plots'
RESULTS_DIR = 'results'


def load_data():
    """Load S&P 500, synthetic TQQQ, and QQQ data."""
    sp500_path = os.path.join(DATA_DIR, 'sp500.csv')
    tqqq_path = os.path.join(DATA_DIR, 'synthetic_tqqq.csv')
    qqq_path = os.path.join(DATA_DIR, 'qqq_12112025.csv')
    
    # Load S&P 500
    sp500 = pd.read_csv(sp500_path, parse_dates=['Date'], index_col='Date')
    
    # Load Synthetic TQQQ
    tqqq = pd.read_csv(tqqq_path, parse_dates=['Date'], index_col='Date')
    
    # Load QQQ
    qqq = pd.read_csv(qqq_path, parse_dates=['Date'], index_col='Date')
    
    # Merge on common dates
    df = sp500[['Close']].copy()
    df.columns = ['SPX_Close']
    df = df.join(tqqq[['TQQQ_Close']], how='inner')
    df = df.join(qqq[['Close']].rename(columns={'Close': 'QQQ_Close'}), how='inner')
    
    # Drop rows where TQQQ is NaN (first day has no TQQQ price)
    df = df.dropna(subset=['TQQQ_Close', 'QQQ_Close'])
    
    print(f"Data range: {df.index[0].date()} to {df.index[-1].date()}")
    print(f"Total trading days: {len(df)}")
    
    return df


def calculate_rsi(series, period=14):
    """Calculate RSI using Wilder's Smoothing."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_indicators(df):
    """Calculate all technical indicators based on S&P 500."""
    df = df.copy()
    
    # Moving averages on S&P 500
    df['SMA_200'] = df['SPX_Close'].rolling(window=SMA_PERIOD).mean()
    df['MA_10'] = df['SPX_Close'].rolling(window=MA_SHORT).mean()
    
    # RSI on S&P 500
    df['RSI'] = calculate_rsi(df['SPX_Close'], RSI_PERIOD)
    
    # Buffer bands
    df['Upper_Band'] = df['SMA_200'] * (1 + BUFFER)
    df['Lower_Band'] = df['SMA_200'] * (1 - BUFFER)
    
    return df


def calculate_baseline_signal(df):
    """Calculate LRS Baseline signal (MA10/200 with 2% buffer)."""
    df = df.copy()
    
    regime = []
    current_state = 0
    
    for i in range(len(df)):
        ma10 = df['MA_10'].iloc[i]
        upper = df['Upper_Band'].iloc[i]
        lower = df['Lower_Band'].iloc[i]
        
        if pd.isna(ma10) or pd.isna(upper):
            regime.append(0)
            continue
        
        if ma10 > upper:
            current_state = 1
        elif ma10 < lower:
            current_state = 0
        # else: keep current state (hysteresis)
        
        regime.append(current_state)
    
    df['Baseline_Regime'] = regime
    df['Baseline_Signal'] = df['Baseline_Regime'].shift(1)  # Trade next day
    
    return df


def calculate_sniper_signal(df):
    """Calculate Hybrid Sniper signal with RSI re-entry."""
    df = df.copy()
    
    regime = []
    current_state = 0.0  # 0.0 = Cash, 0.5 = Sniper, 1.0 = Bull
    
    for i in range(len(df)):
        ma10 = df['MA_10'].iloc[i]
        sma = df['SMA_200'].iloc[i]
        upper = df['Upper_Band'].iloc[i]
        lower = df['Lower_Band'].iloc[i]
        rsi = df['RSI'].iloc[i]
        
        if pd.isna(ma10) or pd.isna(sma) or pd.isna(rsi):
            regime.append(0.0)
            continue
        
        # State Machine
        # 1. Check Bull Trend Entry
        if ma10 > upper:
            current_state = 1.0
        
        # 2. Check Bear/Risk-Off Logic
        elif ma10 < lower:
            if current_state == 1.0:
                # Was Bull, now Bear -> Exit to Cash
                current_state = 0.0
            
            # If Cash: Look for Sniper Entry
            if current_state == 0.0:
                if rsi < RSI_ENTRY:
                    current_state = SNIPER_ALLOC
            
            # If Sniper: Check Sniper Exit
            elif current_state == SNIPER_ALLOC:
                if rsi > RSI_EXIT:
                    current_state = 0.0  # Profit Take -> Cash
        
        # Else: In hysteresis zone -> keep state
        
        regime.append(current_state)
    
    df['Sniper_Regime'] = regime
    df['Sniper_Signal'] = df['Sniper_Regime'].shift(1)  # Trade next day
    
    return df


def calculate_returns(df):
    """Calculate returns for all strategies."""
    df = df.copy()
    
    # TQQQ daily returns
    df['TQQQ_Return'] = df['TQQQ_Close'].pct_change()
    
    # QQQ daily returns
    df['QQQ_Return'] = df['QQQ_Close'].pct_change()
    
    # Cash daily return
    df['Cash_Return'] = RISK_FREE_RATE / 252
    
    # Buy & Hold TQQQ
    df['BH_Return'] = df['TQQQ_Return']
    
    # Buy & Hold QQQ
    df['BH_QQQ_Return'] = df['QQQ_Return']
    
    # LRS Baseline: If signal=1 -> TQQQ, else Cash
    df['Baseline_Return'] = np.where(
        df['Baseline_Signal'] == 1,
        df['TQQQ_Return'],
        df['Cash_Return']
    )
    
    # Hybrid Sniper: Signal * TQQQ + (1 - Signal) * Cash
    # Signal: 0.0, 0.5, or 1.0
    df['Sniper_Return'] = df['Sniper_Signal'] * df['TQQQ_Return'] + \
                          (1 - df['Sniper_Signal']) * df['Cash_Return']
    
    # Handle NaN in first rows
    df['BH_Return'] = df['BH_Return'].fillna(0)
    df['BH_QQQ_Return'] = df['BH_QQQ_Return'].fillna(0)
    df['Baseline_Return'] = df['Baseline_Return'].fillna(0)
    df['Sniper_Return'] = df['Sniper_Return'].fillna(0)
    
    return df


def calculate_cumulative_returns(df):
    """Calculate cumulative portfolio values."""
    df = df.copy()
    
    # For Buy & Hold: Use simple price ratio method (last_price / first_price)
    first_tqqq = df['TQQQ_Close'].iloc[0]
    first_qqq = df['QQQ_Close'].iloc[0]
    
    df['BH_Value'] = INITIAL_CAPITAL * (df['TQQQ_Close'] / first_tqqq)
    df['BH_QQQ_Value'] = INITIAL_CAPITAL * (df['QQQ_Close'] / first_qqq)
    
    # For active strategies: Compound daily returns
    df['Baseline_Value'] = INITIAL_CAPITAL * (1 + df['Baseline_Return']).cumprod()
    df['Sniper_Value'] = INITIAL_CAPITAL * (1 + df['Sniper_Return']).cumprod()
    
    return df


def calculate_metrics(values, returns):
    """Calculate performance metrics."""
    # Time period
    days = len(values)
    years = days / 252
    
    # CAGR
    final_value = values.iloc[-1]
    cagr = (final_value / INITIAL_CAPITAL) ** (1 / years) - 1
    
    # Total Return
    total_return = (final_value / INITIAL_CAPITAL) - 1
    
    # Max Drawdown
    running_max = values.cummax()
    drawdown = (values - running_max) / running_max
    max_drawdown = drawdown.min()
    
    # Volatility (annualized)
    volatility = returns.std() * np.sqrt(252)
    
    # Sharpe Ratio
    excess_returns = returns - (RISK_FREE_RATE / 252)
    sharpe = (excess_returns.mean() * 252) / (returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
    
    # Sortino Ratio
    downside_returns = returns[returns < 0]
    downside_std = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
    sortino = (returns.mean() * 252 - RISK_FREE_RATE) / downside_std if downside_std > 0 else 0
    
    # Calmar Ratio
    calmar = cagr / abs(max_drawdown) if max_drawdown != 0 else 0
    
    return {
        'Final_Value': final_value,
        'Total_Return': total_return,
        'CAGR': cagr,
        'Max_Drawdown': max_drawdown,
        'Volatility': volatility,
        'Sharpe': sharpe,
        'Sortino': sortino,
        'Calmar': calmar
    }


def generate_transaction_log(df):
    """Generate detailed trade log for Hybrid Sniper strategy."""
    df = df.dropna(subset=['Sniper_Signal']).copy()
    
    trades = []
    in_trade = False
    entry_date = None
    entry_type = "Unknown"
    entry_idx = 0
    
    for i in range(len(df)):
        signal = df['Sniper_Signal'].iloc[i]
        
        # Entry: Signal goes from 0 to >0
        if signal > 0 and not in_trade:
            in_trade = True
            entry_idx = i
            entry_date = df.index[i]
            
            # Determine type based on Signal value
            # Signal = 0.5 -> Sniper entry (RSI-based)
            # Signal = 1.0 -> Trend entry (SMA-based)
            if signal == 0.5:
                entry_type = "Sniper (RSI)"
            else:
                entry_type = "Trend (SMA)"
        
        # Exit: Signal goes back to 0
        elif in_trade and signal == 0:
            in_trade = False
            exit_date = df.index[i]
            
            # Calculate returns during trade
            trade_returns = df['Sniper_Return'].iloc[entry_idx:i+1]
            trade_ret = (1 + trade_returns).prod() - 1
            
            tqqq_returns = df['TQQQ_Return'].iloc[entry_idx:i+1]
            tqqq_ret = (1 + tqqq_returns).prod() - 1
            
            trades.append({
                'Entry_Date': entry_date,
                'Exit_Date': exit_date,
                'Duration_Days': (exit_date - entry_date).days,
                'Type': entry_type,
                'Return_Strategy': trade_ret,
                'Return_TQQQ': tqqq_ret
            })
    
    # Handle open trade at end
    if in_trade:
        exit_date = df.index[-1]
        trade_returns = df['Sniper_Return'].iloc[entry_idx:]
        trade_ret = (1 + trade_returns).prod() - 1
        tqqq_returns = df['TQQQ_Return'].iloc[entry_idx:]
        tqqq_ret = (1 + tqqq_returns).prod() - 1
        
        trades.append({
            'Entry_Date': entry_date,
            'Exit_Date': exit_date,
            'Duration_Days': (exit_date - entry_date).days,
            'Type': entry_type,
            'Return_Strategy': trade_ret,
            'Return_TQQQ': tqqq_ret
        })
    
    return pd.DataFrame(trades)


def plot_trades(df, transactions):
    """Generate a multi-page PDF with plots for all trades."""
    from matplotlib.backends.backend_pdf import PdfPages
    
    if transactions.empty:
        print("No trades found.")
        return

    pdf_path = os.path.join(PLOTS_DIR, 'trades_1999.pdf')
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
            fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8.5, 11), sharex=True, 
                                                  gridspec_kw={'height_ratios': [2, 1, 2]})
            
            # --- Top Panel: SPX Signals ---
            ax1.plot(subset.index, subset['SPX_Close'], label='S&P 500', color='black', linewidth=1, alpha=0.6)
            ax1.plot(subset.index, subset['MA_10'], label='MA 10', color='blue', linewidth=1)
            ax1.plot(subset.index, subset['SMA_200'], label='MA 200', color='orange', linestyle='--', linewidth=1)
            
            # Shaded Buffer Zone (±2%)
            upper_buffer = subset['SMA_200'] * 1.02
            lower_buffer = subset['SMA_200'] * 0.98
            ax1.fill_between(subset.index, lower_buffer, upper_buffer, color='orange', alpha=0.15, label='±2% Buffer')
            
            # Mark Entry
            entry_mask = subset.index >= entry_date
            if entry_mask.any():
                spx_entry = subset.loc[entry_mask, 'SPX_Close'].iloc[0]
                ax1.scatter(entry_date, spx_entry, color='green', marker='^', s=80, zorder=5)
                ax1.annotate('', xy=(entry_date, spx_entry), xytext=(0, 20), 
                             textcoords='offset points', arrowprops=dict(arrowstyle='->', color='green', lw=1.5))

            # Mark Exit
            exit_mask = subset.index >= exit_date
            if exit_mask.any():
                spx_exit = subset.loc[exit_mask, 'SPX_Close'].iloc[0]
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
            
            # --- Middle Panel: RSI ---
            ax2.plot(subset.index, subset['RSI'], label='RSI(14)', color='purple', linewidth=0.8)
            ax2.axhline(30, color='green', linestyle='--', alpha=0.5, label='Oversold (30)')
            ax2.axhline(50, color='gray', linestyle='--', alpha=0.5, label='Neutral (50)')
            ax2.fill_between(subset.index, subset['RSI'], 30, where=(subset['RSI'] < 30), color='green', alpha=0.2)
            
            # Mark RSI Entry/Exit Points
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
            
            # --- Bottom Panel: TQQQ ---
            ax3.plot(subset.index, subset['TQQQ_Close'], label='TQQQ Price', color='teal', linewidth=1.2)
            ax3.axvspan(entry_date, exit_date, alpha=0.15, color='green', label='Active Trade')
            
            # Mark Entry/Exit on TQQQ
            if entry_mask.any():
                tqqq_entry = subset.loc[entry_mask, 'TQQQ_Close'].iloc[0]
                ax3.scatter(entry_date, tqqq_entry, color='green', marker='^', s=80, zorder=5)
                ax3.annotate('', xy=(entry_date, tqqq_entry), xytext=(0, 20), 
                             textcoords='offset points', arrowprops=dict(arrowstyle='->', color='green', lw=1.5))
            if exit_mask.any():
                tqqq_exit = subset.loc[exit_mask, 'TQQQ_Close'].iloc[0]
                ax3.scatter(exit_date, tqqq_exit, color='red', marker='v', s=80, zorder=5)
                ax3.annotate('', xy=(exit_date, tqqq_exit), xytext=(0, 20), 
                             textcoords='offset points', arrowprops=dict(arrowstyle='->', color='red', lw=1.5))
            
            tqqq_ret = trade['Return_TQQQ'] * 100
            ax3.set_title(f"TQQQ Return: {tqqq_ret:+.1f}%", fontsize=9, fontweight='bold')
            ax3.set_ylabel('TQQQ ($)', fontsize=9)
            ax3.set_xlabel('Date', fontsize=9)
            ax3.legend(loc='upper left', fontsize='x-small')
            ax3.grid(True, alpha=0.3)
            
            plt.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)
            
    print(f"Saved trade plots to {pdf_path}")


def save_summary(metrics, trades, df):
    """Save summary to summary_1999.md file."""
    
    summary = f"""# LRS Backtest Results (1999 - Present)

## Data Period
- **Start Date:** {df.index[0].strftime('%Y-%m-%d')}
- **End Date:** {df.index[-1].strftime('%Y-%m-%d')}
- **Total Trading Days:** {len(df):,}
- **Total Years:** {len(df)/252:.1f}

> **Note:** Uses synthetic TQQQ data from 1999 and S&P 500 for signal generation.

## Strategy Comparison

| Strategy | Final Equity | Return | CAGR | Max DD | Sharpe | Sortino | Calmar |
|:---------|-------------:|-------:|-----:|-------:|-------:|--------:|-------:|
"""
    
    # Sort by final value
    sorted_metrics = sorted(metrics.items(), key=lambda x: x[1]['Final_Value'], reverse=True)
    
    for name, m in sorted_metrics:
        summary += f"| **{name}** | ${m['Final_Value']:,.0f} | {m['Total_Return']*100:.0f}% | {m['CAGR']*100:.2f}% | {m['Max_Drawdown']*100:.2f}% | {m['Sharpe']:.2f} | {m['Sortino']:.2f} | {m['Calmar']:.2f} |\n"
    
    summary += """
## Key Findings

"""
    
    # Calculate relative performance
    bh_final = metrics['Buy & Hold TQQQ']['Final_Value']
    sniper_final = metrics['Hybrid Sniper']['Final_Value']
    baseline_final = metrics['LRS Baseline']['Final_Value']
    
    if sniper_final > bh_final:
        summary += f"1. **Hybrid Sniper outperforms Buy & Hold** by ${sniper_final - bh_final:,.0f} ({(sniper_final/bh_final - 1)*100:.0f}% more)\n"
    else:
        summary += f"1. **Buy & Hold outperforms Hybrid Sniper** by ${bh_final - sniper_final:,.0f} ({(bh_final/sniper_final - 1)*100:.0f}% more)\n"
    
    bh_dd = metrics['Buy & Hold TQQQ']['Max_Drawdown']
    sniper_dd = metrics['Hybrid Sniper']['Max_Drawdown']
    
    summary += f"2. **Max Drawdown Reduction:** Sniper strategy reduces max drawdown from {bh_dd*100:.1f}% to {sniper_dd*100:.1f}% ({abs(bh_dd - sniper_dd)*100:.1f}% improvement)\n"
    summary += f"3. **Risk-Adjusted Returns:** Sniper Sharpe Ratio ({metrics['Hybrid Sniper']['Sharpe']:.2f}) vs B&H ({metrics['Buy & Hold TQQQ']['Sharpe']:.2f})\n"
    
    # Trade statistics
    sniper_trades = trades[trades['Type'].str.contains('Sniper')]
    trend_trades = trades[trades['Type'].str.contains('Trend')]
    
    summary += f"""
## Trade Statistics

| Category | Metric | Value |
|----------|--------|-------|
| **Count** | Total Trades | {len(trades)} |
| | Trend Trades | {len(trend_trades)} |
| | Sniper Trades | {len(sniper_trades)} |
| **Holding Period** | Mean (All) | {trades['Duration_Days'].mean():.0f} days |
| | Mean (Trend) | {trend_trades['Duration_Days'].mean():.0f} days |
| | Mean (Sniper) | {sniper_trades['Duration_Days'].mean():.0f} days |
| | Longest Trade | {trades['Duration_Days'].max():,} days |
| | Shortest Trade | {trades['Duration_Days'].min()} days |
| **Returns** | Mean Return (All) | {trades['Return_Strategy'].mean()*100:.2f}% |
| | Mean Return (Trend) | {trend_trades['Return_Strategy'].mean()*100:.2f}% |
| | Mean Return (Sniper) | {sniper_trades['Return_Strategy'].mean()*100:.2f}% |
| | Win Rate | {(trades['Return_Strategy'] > 0).sum()}/{len(trades)} ({(trades['Return_Strategy'] > 0).mean()*100:.0f}%) |
| | Best Trade | {trades['Return_Strategy'].max()*100:.2f}% |
| | Worst Trade | {trades['Return_Strategy'].min()*100:.2f}% |

"""
    
    # Add trade log if less than 30 trades
    if len(trades) < 30:
        summary += """## Trade Log

| Entry Date | Exit Date | Duration | Type | Return (Strat) | Return (TQQQ) |
|:-----------|:----------|:---------|:-----|---------------:|---------------:|
"""
        for _, trade in trades.iterrows():
            entry = trade['Entry_Date'].strftime('%Y-%m-%d')
            exit = trade['Exit_Date'].strftime('%Y-%m-%d')
            summary += f"| {entry} | {exit} | {trade['Duration_Days']} days | {trade['Type']} | {trade['Return_Strategy']*100:.2f}% | {trade['Return_TQQQ']*100:.2f}% |\n"
    
    # Save
    with open('summary_1999.md', 'w') as f:
        f.write(summary)
    
    print("\nSaved summary to summary_1999.md")


def plot_results(df):
    """Generate comparison plot."""
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    
    # Equity Curves (Log Scale)
    ax1 = axes[0]
    ax1.semilogy(df.index, df['Sniper_Value'], label='Hybrid Sniper', color='blue', linewidth=2)
    ax1.semilogy(df.index, df['Baseline_Value'], label='LRS Baseline', color='orange', linewidth=1.5)
    ax1.semilogy(df.index, df['BH_Value'], label='Buy & Hold TQQQ', color='red', linewidth=1.5, alpha=0.7)
    ax1.semilogy(df.index, df['BH_QQQ_Value'], label='Buy & Hold QQQ', color='green', linewidth=1.5, alpha=0.7)
    
    ax1.set_title('LRS Strategy Comparison (1999 - Present) - Synthetic TQQQ', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Portfolio Value ($, log scale)')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=INITIAL_CAPITAL, color='gray', linestyle='--', alpha=0.5)
    
    # Drawdowns
    ax2 = axes[1]
    for col, label, color in [('Sniper_Value', 'Hybrid Sniper', 'blue'),
                               ('Baseline_Value', 'LRS Baseline', 'orange'),
                               ('BH_Value', 'Buy & Hold TQQQ', 'red'),
                               ('BH_QQQ_Value', 'Buy & Hold QQQ', 'green')]:
        running_max = df[col].cummax()
        drawdown = (df[col] - running_max) / running_max * 100
        ax2.fill_between(df.index, drawdown, 0, alpha=0.3, label=label)
        ax2.plot(df.index, drawdown, linewidth=0.5, color=color)
    
    ax2.set_title('Drawdowns', fontsize=14, fontweight='bold')
    ax2.set_ylabel('Drawdown (%)')
    ax2.set_xlabel('Date')
    ax2.legend(loc='lower left')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, 'lrs_backtest_1999.png'), dpi=150)
    plt.savefig(os.path.join(PLOTS_DIR, 'lrs_backtest_1999.pdf'), dpi=150)
    plt.close()
    print(f"Saved plots to {PLOTS_DIR}/lrs_backtest_1999.png")


def main():
    """Run the backtest."""
    print("=" * 80)
    print("LRS BACKTEST (1999 - Present) - Using Synthetic TQQQ")
    print("=" * 80)
    
    # Load data
    df = load_data()
    
    # Calculate indicators
    df = calculate_indicators(df)
    
    # Calculate signals
    df = calculate_baseline_signal(df)
    df = calculate_sniper_signal(df)
    
    # Calculate returns
    df = calculate_returns(df)
    
    # Calculate cumulative returns
    df = calculate_cumulative_returns(df)
    
    # Filter to valid period (after SMA_200 is available)
    df = df.dropna(subset=['SMA_200'])
    
    # Calculate metrics
    metrics = {
        'Buy & Hold TQQQ': calculate_metrics(df['BH_Value'], df['BH_Return']),
        'Buy & Hold QQQ': calculate_metrics(df['BH_QQQ_Value'], df['BH_QQQ_Return']),
        'LRS Baseline': calculate_metrics(df['Baseline_Value'], df['Baseline_Return']),
        'Hybrid Sniper': calculate_metrics(df['Sniper_Value'], df['Sniper_Return'])
    }
    
    # Print summary
    print("\n" + "=" * 80)
    print("PERFORMANCE SUMMARY")
    print("=" * 80)
    print(f"{'Strategy':<25} {'CAGR':>12} {'Max DD':>12} {'Sharpe':>12} {'Final Value':>15}")
    print("-" * 80)
    
    for name, m in sorted(metrics.items(), key=lambda x: x[1]['Final_Value'], reverse=True):
        print(f"{name:<25} {m['CAGR']*100:>11.2f}% {m['Max_Drawdown']*100:>11.2f}% "
              f"{m['Sharpe']:>12.2f} ${m['Final_Value']:>14,.0f}")
    
    print("=" * 80)
    
    # Generate transaction log
    trades = generate_transaction_log(df)
    trades.to_csv(os.path.join(RESULTS_DIR, 'transactions_1999.csv'), index=False)
    print(f"\nTotal trades: {len(trades)}")
    
    # Plot trade details to PDF
    plot_trades(df, trades)
    
    # Plot results
    plot_results(df)
    
    # Save summary
    save_summary(metrics, trades, df)
    
    return df, metrics, trades


if __name__ == "__main__":
    main()
