#!/usr/bin/env python3
"""
Plot the latest 5 trades for the Hybrid Sniper strategy on SOXL.
Generates a detailed PDF report visualizing the trade contexts, S&P 500 signals,
RSI values, and SOXL returns.
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


def main():
    """Load backtest data and plot the latest 5 trades with details."""
    print("Loading SOXL backtest daily data and transactions...")
    
    daily_path = os.path.join(RESULTS_DIR, 'soxl_backtest_daily.csv')
    trans_path = os.path.join(RESULTS_DIR, 'transactions_soxl.csv')
    
    if not os.path.exists(daily_path) or not os.path.exists(trans_path):
        print("Error: Backtest data files not found. Run lrs_soxl_backtest.py first.")
        return
        
    df = pd.read_csv(daily_path, index_col=0, parse_dates=True)
    trades = pd.read_csv(trans_path)
    
    # Get the latest 5 trades
    latest_trades = trades.tail(5).copy().reset_index(drop=True)
    
    pdf_path = os.path.join(PLOTS_DIR, 'soxl_latest_5_trades.pdf')
    print(f"Plotting the latest 5 trades to {pdf_path}...")
    
    with PdfPages(pdf_path) as pdf:
        for idx, trade in latest_trades.iterrows():
            entry_date = pd.to_datetime(trade['Entry_Date'])
            exit_date = pd.to_datetime(trade['Exit_Date'])
            
            # Pad window with 60 days on either side for historical context
            start_window = entry_date - pd.Timedelta(days=60)
            end_window = exit_date + pd.Timedelta(days=60)
            
            mask = (df.index >= start_window) & (df.index <= end_window)
            subset = df.loc[mask].copy()
            
            if subset.empty:
                continue
                
            # Letter Page size portrait (8.5 x 11 inches)
            fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8.5, 11), sharex=True,
                                                  gridspec_kw={'height_ratios': [2, 1, 2]})
            
            # 1. Top Panel: S&P 500 signals
            ax1.plot(subset.index, subset['SP500_Close'], label='S&P 500 Close', color='#1a1a1a', linewidth=1.2, alpha=0.8)
            ax1.plot(subset.index, subset['MA_10'], label='MA 10', color='#007bff', linewidth=1.0)
            ax1.plot(subset.index, subset['SMA_200'], label='SMA 200', color='#ff7f0e', linestyle='--', linewidth=1.0)
            
            # Buffer bands (±2%)
            upper_band = subset['SMA_200'] * 1.02
            lower_band = subset['SMA_200'] * 0.98
            ax1.fill_between(subset.index, lower_band, upper_band, color='#ff7f0e', alpha=0.12, label='Buffer Zone (±2%)')
            
            # Identify exact S&P 500 entry/exit values
            spx_entry_series = subset.loc[subset.index >= entry_date, 'SP500_Close']
            spx_exit_series = subset.loc[subset.index >= exit_date, 'SP500_Close']
            
            spx_entry = spx_entry_series.iloc[0] if not spx_entry_series.empty else subset['SP500_Close'].iloc[0]
            spx_exit = spx_exit_series.iloc[0] if not spx_exit_series.empty else subset['SP500_Close'].iloc[-1]
            
            # Entry Signal type & details
            trade_type = trade['Type']
            if "Sniper" in trade_type:
                entry_label = "Sniper Entry\n(RSI < 30)"
                entry_color = '#2ca02c'
                entry_marker = '^'
            else:
                entry_label = "Trend Entry\n(MA10 > SMA200 * 1.02)"
                entry_color = '#1f77b4'
                entry_marker = '^'
                
            # Check if this trade is still open
            is_open = trade.get('Status', 'CLOSED') == 'OPEN'
            
            # Exit Signal type & details
            if is_open:
                exit_label = "STILL OPEN"
                exit_color = '#ff8c00'  # Orange for open trades
                exit_marker = 'D'  # Diamond marker
            else:
                # If exit date corresponds to a Sniper RSI target or SMA breakdown
                exit_regime_series = subset.loc[subset.index == exit_date, 'Sniper_Signal']
                if not exit_regime_series.empty:
                    if "Sniper" in trade_type and exit_date in df.index:
                        rsi_val = df.loc[exit_date, 'RSI']
                        if rsi_val > 49.0:
                            exit_label = "RSI Exit\n(RSI > 50)"
                        else:
                            exit_label = "SMA Exit\n(MA10 < SMA200 * 0.98)"
                    else:
                        exit_label = "SMA Exit\n(MA10 < SMA200 * 0.98)"
                else:
                    exit_label = "Exit"
                exit_color = '#d62728'
                exit_marker = 'v'
            
            # Plot Entry/Exit Markers
            ax1.scatter(entry_date, spx_entry, color=entry_color, marker=entry_marker, s=80, zorder=5)
            ax1.annotate(entry_label, xy=(entry_date, spx_entry), xytext=(-35, 25), 
                         textcoords='offset points', arrowprops=dict(arrowstyle='->', color=entry_color, lw=1.0),
                         fontsize=8, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="#eef", alpha=0.8, ec=entry_color))
            
            ax1.scatter(exit_date, spx_exit, color=exit_color, marker=exit_marker, s=80, zorder=5)
            ax1.annotate(exit_label, xy=(exit_date, spx_exit), xytext=(15, 25), 
                         textcoords='offset points', arrowprops=dict(arrowstyle='->', color=exit_color, lw=1.0),
                         fontsize=8, fontweight='bold', bbox=dict(boxstyle="round,pad=0.3", fc="#ffe", alpha=0.8, ec=exit_color))
            
            # Build title
            if is_open:
                title_text = f"SOXL Hybrid Sniper Trade #{idx+1} | {trade_type} (Still Open)\n{entry_date.date()} to {exit_date.date()} ({trade['Duration_Days']} days)"
            else:
                title_text = f"SOXL Hybrid Sniper Trade #{idx+1} | {trade_type}\n{entry_date.date()} to {exit_date.date()} ({trade['Duration_Days']} days)"
            ax1.set_title(title_text, fontsize=11, fontweight='bold', pad=10)
            ax1.set_ylabel('S&P 500 Price', fontsize=9)
            ax1.grid(True, alpha=0.25)
            ax1.legend(loc='upper left', fontsize='x-small')
            
            # 2. Middle Panel: RSI
            ax2.plot(subset.index, subset['RSI'], label='S&P 500 RSI(14)', color='#9467bd', linewidth=1.0)
            ax2.axhline(30, color='#2ca02c', linestyle='--', alpha=0.6, label='Oversold threshold (30)')
            ax2.axhline(50, color='#7f7f7f', linestyle='--', alpha=0.5, label='Neutral profit-take (50)')
            ax2.fill_between(subset.index, subset['RSI'], 30, where=(subset['RSI'] < 30), color='#2ca02c', alpha=0.15)
            
            # Show RSI markers at entry/exit
            rsi_entry_series = subset.loc[subset.index >= entry_date, 'RSI']
            rsi_exit_series = subset.loc[subset.index >= exit_date, 'RSI']
            
            if not rsi_entry_series.empty:
                rsi_ent = rsi_entry_series.iloc[0]
                ax2.scatter(entry_date, rsi_ent, color=entry_color, s=40, zorder=5)
                ax2.annotate(f"RSI: {rsi_ent:.1f}", xy=(entry_date, rsi_ent), xytext=(-25, -15),
                             textcoords='offset points', fontsize=7, color=entry_color, fontweight='bold')
            if not rsi_exit_series.empty:
                rsi_ex = rsi_exit_series.iloc[0]
                ax2.scatter(exit_date, rsi_ex, color=exit_color, s=40, zorder=5)
                ax2.annotate(f"RSI: {rsi_ex:.1f}", xy=(exit_date, rsi_ex), xytext=(10, -15),
                             textcoords='offset points', fontsize=7, color=exit_color, fontweight='bold')
                             
            ax2.set_ylabel('RSI (14)', fontsize=9)
            ax2.set_ylim(10, 90)
            ax2.grid(True, alpha=0.25)
            ax2.legend(loc='upper right', fontsize='xx-small')
            
            # 3. Bottom Panel: SOXL
            ax3.plot(subset.index, subset['SOXL_Close'], label='SOXL Close Price', color='#17becf', linewidth=1.2)
            ax3.axvspan(entry_date, exit_date, alpha=0.1, color='#2ca02c', label='Trade Duration')
            
            # Mark Entry/Exit on SOXL
            soxl_entry_series = subset.loc[subset.index >= entry_date, 'SOXL_Close']
            soxl_exit_series = subset.loc[subset.index >= exit_date, 'SOXL_Close']
            
            soxl_ent = soxl_entry_series.iloc[0] if not soxl_entry_series.empty else subset['SOXL_Close'].iloc[0]
            soxl_ex = soxl_exit_series.iloc[0] if not soxl_exit_series.empty else subset['SOXL_Close'].iloc[-1]
            
            ax3.scatter(entry_date, soxl_ent, color=entry_color, marker=entry_marker, s=60, zorder=5)
            ax3.annotate(f"${soxl_ent:.2f}", xy=(entry_date, soxl_ent), xytext=(-30, -12),
                         textcoords='offset points', fontsize=8, color='#333', fontweight='bold')
                         
            ax3.scatter(exit_date, soxl_ex, color=exit_color, marker=exit_marker, s=60, zorder=5)
            ax3.annotate(f"${soxl_ex:.2f}", xy=(exit_date, soxl_ex), xytext=(10, -12),
                         textcoords='offset points', fontsize=8, color='#333', fontweight='bold')
            
            # Calculate return labels
            strat_ret = trade['Return_Strategy'] * 100
            soxl_ret = trade['Return_SOXL'] * 100
            
            metric_text = (
                f"Strategy Return: {strat_ret:+.2f}%\n"
                f"SOXL Asset Return: {soxl_ret:+.2f}%\n"
                f"Outperformance: {strat_ret - soxl_ret:+.2f}%"
            )
            
            # Place metrics box on SOXL chart
            ax3.text(0.03, 0.05, metric_text, transform=ax3.transAxes, fontsize=8,
                     fontweight='bold', bbox=dict(boxstyle="round,pad=0.4", facecolor='white', alpha=0.9, edgecolor='#ccc'))
            
            ax3.set_ylabel('SOXL Price ($)', fontsize=9)
            ax3.set_xlabel('Date', fontsize=9)
            ax3.grid(True, alpha=0.25)
            ax3.legend(loc='upper left', fontsize='x-small')
            
            plt.subplots_adjust(hspace=0.08)
            pdf.savefig(fig)
            plt.close(fig)
            
    print(f"Successfully plotted the latest 5 trades to {pdf_path}")
    
    # Save a PNG of the latest trade for quick visual check
    print("Saving PNG of the latest trade...")
    latest_trade = latest_trades.iloc[-1]
    entry_date = pd.to_datetime(latest_trade['Entry_Date'])
    exit_date = pd.to_datetime(latest_trade['Exit_Date'])
    start_window = entry_date - pd.Timedelta(days=60)
    end_window = exit_date + pd.Timedelta(days=60)
    subset = df.loc[(df.index >= start_window) & (df.index <= end_window)].copy()
    
    if not subset.empty:
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 12), sharex=True,
                                              gridspec_kw={'height_ratios': [2, 1, 2]})
        ax1.plot(subset.index, subset['SP500_Close'], color='black', label='S&P 500')
        ax1.plot(subset.index, subset['MA_10'], color='#007bff', label='MA 10')
        ax1.plot(subset.index, subset['SMA_200'], color='#ff7f0e', linestyle='--', label='SMA 200')
        ax1.fill_between(subset.index, subset['SMA_200']*0.98, subset['SMA_200']*1.02, color='#ff7f0e', alpha=0.1)
        
        spx_ent = subset.loc[subset.index >= entry_date, 'SP500_Close'].iloc[0]
        spx_ex = subset.loc[subset.index >= exit_date, 'SP500_Close'].iloc[0]
        
        ax1.scatter(entry_date, spx_ent, color='#1f77b4', marker='^', s=100)
        ax1.scatter(exit_date, spx_ex, color='#d62728', marker='v', s=100)
        ax1.set_title(f"Latest SOXL Trade Context: {entry_date.date()} to {exit_date.date()}", fontsize=12, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        ax2.plot(subset.index, subset['RSI'], color='#9467bd')
        ax2.axhline(30, color='green', linestyle='--')
        ax2.axhline(50, color='gray', linestyle='--')
        ax2.grid(True, alpha=0.3)
        ax2.set_ylabel('RSI (14)')
        
        ax3.plot(subset.index, subset['SOXL_Close'], color='#17becf', label='SOXL')
        ax3.axvspan(entry_date, exit_date, color='green', alpha=0.1)
        ax3.set_ylabel('SOXL Close')
        ax3.grid(True, alpha=0.3)
        
        png_path = os.path.join(PLOTS_DIR, 'soxl_latest_trade.png')
        plt.savefig(png_path, dpi=120)
        plt.close()
        print(f"Saved PNG to {png_path}")

if __name__ == "__main__":
    main()
