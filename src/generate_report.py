import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import lrs_backtest
import os

def create_summary_page(pdf, metrics):
    """Create a text-based summary page."""
    fig = plt.figure(figsize=(11, 8.5))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis('off')
    
    # Title
    ax.text(0.1, 0.9, "Leverage Rotation Strategy (LRS)", fontsize=24, fontweight='bold', color='navy')
    ax.text(0.1, 0.85, "Backtest Report: Post-2010 Comparison", fontsize=16, color='gray')
    
    # Date
    ax.text(0.1, 0.82, f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d')}", fontsize=10)
    
    # Executive Summary Text
    summary_text = (
        "This report compares the Leverage Rotation Strategy (LRS) applied to\n"
        "UPRO (Simulated SPX 3x) and TQQQ (Nasdaq-100 3x) against their Buy & Hold benchmarks.\n\n"
        "Key Findings:\n"
        "- LRS uses a 200-day SMA filter to avoid major drawdowns.\n"
        "- Post-2010 was a strong bull market, challenging defensive strategies.\n"
        "- However, LRS TQQQ significantly reduced Max Drawdown compared to Buy & Hold."
    )
    ax.text(0.1, 0.70, summary_text, fontsize=12, wrap=True, linespacing=1.5)
    
    # Metrics Table
    # Prepare data for table
    col_labels = ['Strategy', 'CAGR', 'Max Drawdown', 'Sharpe Ratio', 'Final Value']
    table_data = []
    
    # Sort order
    order = ['LRS TQQQ', 'Buy-Hold TQQQ', 'LRS SPX 3x', 'Buy-Hold SPX']
    
    for strategy in order:
        if strategy in metrics:
            m = metrics[strategy]
            table_data.append([
                strategy,
                f"{m['CAGR']:.2%}",
                f"{m['Max_Drawdown']:.2%}",
                f"{m['Sharpe_Ratio']:.2f}",
                f"${m['Final_Value']:,.0f}"
            ])
            
    # Draw Table
    table = plt.table(cellText=table_data, colLabels=col_labels, loc='center', cellLoc='center',
                      bbox=[0.1, 0.3, 0.8, 0.3])
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1, 2)
    
    # Column Styling
    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(weight='bold', color='white')
            cell.set_facecolor('navy')
        elif row % 2 == 0:
            cell.set_facecolor('#f2f2f2')
    
    pdf.savefig(fig)
    plt.close()

def create_plots_page(pdf, df):
    """Create Equity Curve and Drawdown plots."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8.5), sharex=True)
    
    # Equity Curve
    ax1.semilogy(df.index, df['LRS_TQQQ_Value'], label='LRS TQQQ', color='purple', linewidth=2)
    ax1.semilogy(df.index, df['BH_TQQQ_Value'], label='Buy & Hold TQQQ', color='gray', linestyle='--', alpha=0.6)
    ax1.semilogy(df.index, df['LRS_SPX3x_Value'], label='LRS SPX 3x', color='blue', linewidth=1.5)
    ax1.semilogy(df.index, df['BH_Index_Value'], label='S&P 500', color='black', alpha=0.4)
    
    ax1.set_title("Equity Curves (Log Scale)", fontsize=14, fontweight='bold')
    ax1.set_ylabel("Portfolio Value ($)")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)
    
    # Drawdowns
    # Calculate Drawdowns dynamically
    for col, label, color in [('LRS_TQQQ_Value', 'LRS TQQQ', 'purple'), 
                              ('BH_TQQQ_Value', 'BH TQQQ', 'gray')]:
        running_max = df[col].cummax()
        dd = (df[col] - running_max) / running_max
        ax2.fill_between(df.index, dd, 0, color=color, alpha=0.3, label=label)
        ax2.plot(df.index, dd, color=color, linewidth=1)
        
    ax2.set_title("Drawdowns", fontsize=14, fontweight='bold')
    ax2.set_ylabel("Drawdown %")
    ax2.legend(loc="lower left")
    ax2.grid(True, alpha=0.3)
    
    pdf.savefig(fig)
    plt.close()

def main():
    print("Generating LRS Report...")
    
    # Run Comparison to get fresh data
    df, metrics = lrs_backtest.run_comparison(start_date='2010-01-01')
    
    output_pdf = "LRS_Report_2010_2025.pdf"
    
    with PdfPages(output_pdf) as pdf:
        # Page 1: Summary
        create_summary_page(pdf, metrics)
        
        # Page 2: Plots
        create_plots_page(pdf, df)
        
    print(f"\nReport generated successfully: {output_pdf}")

if __name__ == "__main__":
    main()
