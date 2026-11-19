"""
Print the markdown tables used in summary.md from the results/ CSVs.

Run after lrs_golden_cross.py, lrs_hybrid_sniper.py and lrs_soxl_backtest.py:
    python src/summary_tables.py > results/summary_tables.md
"""
import os

import pandas as pd

from backtest_common import RESULTS_DIR


def pct(x, signed=False):
    """Format a fraction as a percentage."""
    return f"{x * 100:+.2f}%" if signed else f"{x * 100:.2f}%"


def money(x):
    """Format a dollar amount with escaped $ for markdown."""
    return f"\\${x:,.0f}"


def performance_table(metrics, names, asset):
    """Markdown performance table for ``names`` ordered by final equity."""
    lines = [f"| Strategy | Final Equity | Return | CAGR | Max DD | Volatility | Sharpe | Sortino | Calmar "
             f"| Alpha ({asset}) | Beta ({asset}) | Alpha (SPX) | Beta (SPX) |",
             "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, m in metrics.loc[names].sort_values('Final_Value', ascending=False).iterrows():
        lines.append(f"| {name} | {money(m.Final_Value)} | {pct(m.Total_Return)} | {pct(m.CAGR)} "
                     f"| {pct(m.Max_Drawdown)} | {pct(m.Volatility)} | {m.Sharpe:.2f} | {m.Sortino:.2f} "
                     f"| {m.Calmar:.2f} | {pct(m.Alpha_BH, True)} | {m.Beta_BH:.2f} "
                     f"| {pct(m.Alpha_SPX, True)} | {m.Beta_SPX:.2f} |")
    return '\n'.join(lines)


def sensitivity_table(metrics, names):
    """Markdown table comparing fill conventions and cash assumptions."""
    lines = ["| Run | Fill | Final Equity | CAGR | Max DD | Sharpe |",
             "| :--- | :--- | ---: | ---: | ---: | ---: |"]
    for name, m in metrics.loc[names].sort_values('Final_Value', ascending=False).iterrows():
        lines.append(f"| {name} | {m.Fill} | {money(m.Final_Value)} | {pct(m.CAGR)} "
                     f"| {pct(m.Max_Drawdown)} | {m.Sharpe:.2f} |")
    return '\n'.join(lines)


def trade_table(trades, asset_col, asset):
    """Markdown trade log (fill dates are opens)."""
    lines = [f"| # | Entry (open) | Exit (open) | Days | Type | Exit Reason | Return (Strat) | Return ({asset}) |",
             "| ---: | :--- | :--- | ---: | :--- | :--- | ---: | ---: |"]
    for i, t in enumerate(trades.itertuples(), 1):
        exit_date = t.Exit_Date if t.Status == 'CLOSED' else f"{t.Exit_Date} (still open)"
        typ = f"**{t.Type}**" if 'Sniper' in t.Type else t.Type
        lines.append(f"| {i} | {t.Entry_Date} | {exit_date} | {t.Duration_Days} | {typ} | {t.Exit_Reason} "
                     f"| {pct(t.Return_Strategy, True)} | {pct(getattr(t, asset_col), True)} |")
    return '\n'.join(lines)


def trade_stats(trades, daily_signal, start, end):
    """Markdown trade statistics table."""
    closed = trades[trades.Status == 'CLOSED']
    trend = trades[trades.Type.str.contains('Trend')]
    sniper = trades[trades.Type.str.contains('Sniper')]
    entries = pd.to_datetime(trades.Entry_Date)
    exits = pd.to_datetime(trades.Exit_Date)
    # Wait = calendar days in cash between one trade's exit and the next entry
    waits = [(entries.iloc[i + 1] - exits.iloc[i]).days for i in range(len(trades) - 1)
             if entries.iloc[i + 1] > exits.iloc[i]]
    longest = trades.loc[trades.Duration_Days.idxmax()]
    wins = (closed.Return_Strategy > 0).sum()
    in_market = (daily_signal > 0).mean()
    years = (pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25
    rows = [
        ("**Count**", "Total Trades", f"{len(trades)} ({len(closed)} closed, {len(trades) - len(closed)} open)"),
        ("", "Trend Trades", len(trend)),
        ("", "Sniper Trades", len(sniper)),
        ("**Holding Period**", "Mean (All)", f"{trades.Duration_Days.mean():.0f} days"),
        ("", "Mean (Trend)", f"{trend.Duration_Days.mean():.0f} days"),
        ("", "Mean (Sniper)", f"{sniper.Duration_Days.mean():.0f} days"),
        ("", "Longest Trade", f"{longest.Duration_Days:,} days ({longest.Entry_Date} to {longest.Exit_Date})"),
        ("", "Shortest Trade", f"{trades.Duration_Days.min()} days"),
        ("**Wait Time**", "Mean Wait in Cash Between Trades", f"{sum(waits) / len(waits):.0f} days" if waits else "n/a"),
        ("", "Max Wait", f"{max(waits)} days" if waits else "n/a"),
        ("**Returns**", "Mean Return (All)", pct(trades.Return_Strategy.mean(), True)),
        ("", "Mean Return (Trend)", pct(trend.Return_Strategy.mean(), True)),
        ("", "Mean Return (Sniper)", pct(sniper.Return_Strategy.mean(), True)),
        ("", "Win Rate (closed trades)", f"{wins}/{len(closed)} ({wins / len(closed):.0%})"),
        ("", "Best Trade", pct(trades.Return_Strategy.max(), True)),
        ("", "Worst Trade", pct(trades.Return_Strategy.min(), True)),
        ("**Exposure**", "Total Period", f"{years:.1f} years"),
        ("", "Time in Market", f"{in_market:.1%}"),
        ("", "Time in Cash", f"{1 - in_market:.1%}"),
    ]
    lines = ["| Category | Metric | Value |", "| :--- | :--- | :--- |"]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    return '\n'.join(lines)


def golden_cross_table(gc):
    """Markdown table for the golden cross scan, ordered by final equity."""
    lines = ["| Strategy | Final Equity | Return | CAGR | Max DD | Sharpe | Alpha (TQQQ) | Beta (TQQQ) "
             "| Trades | Final Equity (MOC) |",
             "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for m in gc.sort_values('Final_Value', ascending=False).itertuples():
        trades = '' if pd.isna(m.Trades) else int(m.Trades)
        lines.append(f"| {m.Strategy} | {money(m.Final_Value)} | {pct(m.Total_Return)} | {pct(m.CAGR)} "
                     f"| {pct(m.Max_Drawdown)} | {m.Sharpe:.2f} | {pct(m.Alpha_BH, True)} | {m.Beta_BH:.2f} "
                     f"| {trades} | {money(m.MOC_Final_Value)} |")
    return '\n'.join(lines)


def main():
    """Print every summary table."""
    gc = pd.read_csv(os.path.join(RESULTS_DIR, 'golden_cross_summary.csv'))
    hs = pd.read_csv(os.path.join(RESULTS_DIR, 'hybrid_sniper_metrics.csv'), index_col=0)
    hs_trades = pd.read_csv(os.path.join(RESULTS_DIR, 'transactions_hybrid_sniper.csv'), index_col=0)
    sx = pd.read_csv(os.path.join(RESULTS_DIR, 'soxl_performance_summary.csv'), index_col=0)
    sx_trades = pd.read_csv(os.path.join(RESULTS_DIR, 'transactions_soxl.csv'))
    sx_daily = pd.read_csv(os.path.join(RESULTS_DIR, 'soxl_backtest_daily.csv'), index_col=0, parse_dates=True)

    # TQQQ daily held weight for exposure stats (recomputed from regime, next-open)
    import lrs_hybrid_sniper as hsm
    import backtest_common as bc
    sig = hsm.calculate_signals_sniper(bc.load_ohlcv('sp500'))
    tq = bc.load_ohlcv('tqqq')
    sig = sig.join(tq[['Close']].rename(columns={'Close': 'TQQQ'}), how='inner')
    sig = sig[sig.index >= pd.Timestamp(hs['Start'].iloc[0])]
    tq_signal = bc.held_weights(sig['Regime'])[1]

    print(f"## Golden Cross ({gc['Start'].iloc[0]} to {gc['End'].iloc[0]})\n")
    print(golden_cross_table(gc))
    print(f"\n## Hybrid Sniper TQQQ ({hs['Start'].iloc[0]} to {hs['End'].iloc[0]})\n")
    print(performance_table(hs, ['Buy & Hold TQQQ', 'Hybrid Sniper', 'LRS Baseline'], 'TQQQ'))
    print()
    print(sensitivity_table(hs, ['Hybrid Sniper', 'Hybrid Sniper (MOC)', 'Hybrid Sniper (0% cash)',
                                 'LRS Baseline', 'LRS Baseline (MOC)']))
    print()
    print(trade_table(hs_trades, 'Return_TQQQ', 'TQQQ'))
    print()
    print(trade_stats(hs_trades, tq_signal, hs['Start'].iloc[0], hs['End'].iloc[0]))
    print(f"\n## SOXL ({sx['Start'].iloc[0]} to {sx['End'].iloc[0]})\n")
    print(performance_table(sx, ['Buy & Hold SOXL', 'Hybrid Sniper', 'LRS Baseline'], 'SOXL'))
    print()
    print(sensitivity_table(sx, ['Hybrid Sniper', 'Hybrid Sniper (MOC)', 'Hybrid Sniper (0% cash)',
                                 'LRS Baseline', 'LRS Baseline (MOC)']))
    print()
    print(trade_table(sx_trades, 'Return_SOXL', 'SOXL'))
    print()
    print(trade_stats(sx_trades, sx_daily['Sniper_Signal'], sx['Start'].iloc[0], sx['End'].iloc[0]))


if __name__ == "__main__":
    main()
