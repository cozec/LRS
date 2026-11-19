"""
Build results/LRS_Hybrid_Sniper_Report.pdf from the backtest outputs.

Every number comes from files written by src/lrs_hybrid_sniper.py
(results/hybrid_sniper_metrics.csv, results/transactions_hybrid_sniper.csv);
run that script first.
"""
import os

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results')
PLOTS_DIR = os.path.join(PROJECT_ROOT, 'plots')
OUTPUT_FILE = os.path.join(RESULTS_DIR, 'LRS_Hybrid_Sniper_Report.pdf')

TABLE_STYLE = TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 8),
    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
])


def pct(x):
    """Format a fraction as a signed percentage."""
    return f"{x * 100:+.2f}%"


def money(x):
    """Format a dollar amount."""
    return f"${x:,.0f}"


def performance_rows(metrics, names):
    """Table rows for ``names`` ordered by final equity."""
    rows = [['Strategy', 'Final Equity', 'Return', 'CAGR', 'Max DD', 'Sharpe', 'Alpha (TQQQ)', 'Beta (TQQQ)']]
    sub = metrics.loc[names].sort_values('Final_Value', ascending=False)
    for name, m in sub.iterrows():
        rows.append([name, money(m.Final_Value), pct(m.Total_Return), pct(m.CAGR), pct(m.Max_Drawdown),
                     f"{m.Sharpe:.2f}", pct(m.Alpha_BH), f"{m.Beta_BH:.2f}"])
    return rows


def create_report():
    """Write the PDF report from the latest backtest results."""
    metrics = pd.read_csv(os.path.join(RESULTS_DIR, 'hybrid_sniper_metrics.csv'), index_col=0)
    trades = pd.read_csv(os.path.join(RESULTS_DIR, 'transactions_hybrid_sniper.csv'), index_col=0)
    start, end = metrics['Start'].iloc[0], metrics['End'].iloc[0]
    sniper, bh = metrics.loc['Hybrid Sniper'], metrics.loc['Buy & Hold TQQQ']

    print(f"Generating PDF Report: {OUTPUT_FILE}")
    doc = SimpleDocTemplate(OUTPUT_FILE, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [Paragraph("LRS: Hybrid Sniper Strategy Report", styles['Title']), Spacer(1, 12)]

    verdict = "beat" if sniper.Final_Value > bh.Final_Value else "trailed"
    summary_text = f"""
    <b>Backtest window:</b> {start} to {end}, $10,000 start, TQQQ traded on S&amp;P 500 signals.<br/>
    <b>Fills:</b> decide at the close, trade at the next open. Cash earns 3%/yr; no commissions or slippage.<br/><br/>
    <b>Hybrid Sniper logic (signals on the S&amp;P 500):</b><br/>
    1. <b>Trend (100% TQQQ):</b> enter when MA10 &gt; SMA200 x 1.02; exit to cash when MA10 &lt; SMA200 x 0.98.<br/>
    2. <b>Sniper (50% TQQQ):</b> while MA10 &lt; SMA200 x 0.98 and in cash, buy when RSI(14) &lt; 30.<br/>
    3. <b>Sniper exit:</b> back to cash when RSI(14) &gt; 50, or promoted to Trend on MA10 &gt; SMA200 x 1.02.<br/><br/>
    <b>Result:</b> the Hybrid Sniper {verdict} Buy &amp; Hold TQQQ ({money(sniper.Final_Value)} vs
    {money(bh.Final_Value)}) with a max drawdown of {pct(sniper.Max_Drawdown)} vs {pct(bh.Max_Drawdown)}.
    """
    story += [Paragraph(summary_text, styles['BodyText']), Spacer(1, 12)]

    table = Table(performance_rows(metrics, ['Buy & Hold TQQQ', 'Hybrid Sniper', 'LRS Baseline']))
    table.setStyle(TABLE_STYLE)
    story += [table, Spacer(1, 12)]

    story.append(Paragraph("<b>Sensitivity</b> (fill convention and cash rate):", styles['BodyText']))
    sens = Table(performance_rows(metrics, ['Hybrid Sniper', 'Hybrid Sniper (MOC)', 'Hybrid Sniper (0% cash)',
                                            'LRS Baseline', 'LRS Baseline (MOC)']))
    sens.setStyle(TABLE_STYLE)
    story += [sens, Spacer(1, 18)]

    equity_plot = os.path.join(PLOTS_DIR, 'comparison_equity_sniper.png')
    if os.path.exists(equity_plot):
        story.append(Image(equity_plot, width=500, height=250))
        story.append(Paragraph("<b>Figure 1:</b> Equity curves (log scale), next-open fills.", styles['BodyText']))

    story += [PageBreak(), Paragraph("Trade Log", styles['Title'])]
    rows = [['Entry (open)', 'Exit (open)', 'Days', 'Type', 'Exit Reason', 'Strategy', 'TQQQ']]
    for _, t in trades.iterrows():
        rows.append([t.Entry_Date, t.Exit_Date if t.Status == 'CLOSED' else f"{t.Exit_Date} (open)",
                     t.Duration_Days, t.Type, t.Exit_Reason, pct(t.Return_Strategy), pct(t.Return_TQQQ)])
    log_table = Table(rows)
    log_table.setStyle(TABLE_STYLE)
    story += [log_table, Spacer(1, 12),
              Paragraph("See plots/trades_comparison.pdf for a chart of every trade.", styles['BodyText'])]

    doc.build(story)
    print("PDF Generation Complete.")


if __name__ == "__main__":
    create_report()
