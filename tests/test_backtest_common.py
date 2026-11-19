"""
Tests for src/backtest_common.py: fill conventions, buy & hold, trade log.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import backtest_common as bc  # noqa: E402

CASH = bc.RISK_FREE_RATE / bc.TRADING_DAYS


@pytest.fixture
def prices():
    """Random-walk open/close prices with real overnight gaps."""
    rng = np.random.default_rng(0)
    idx = pd.bdate_range('2020-01-01', periods=60)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, len(idx)))), index=idx)
    open_ = close.shift(1).fillna(close.iloc[0]) * np.exp(rng.normal(0, 0.01, len(idx)))
    return open_, close


def test_buy_hold_formula(prices):
    _, close = prices
    bh = bc.buy_hold_equity(close)
    assert bh.iloc[0] == bc.INITIAL_CAPITAL
    assert bh.iloc[-1] == pytest.approx(10000 * close.iloc[-1] / close.iloc[0])


def test_always_invested_next_open_matches_close_to_close_after_entry(prices):
    open_, close = prices
    w = pd.Series(1.0, index=close.index)
    r = bc.strategy_returns(w, open_, close, 'next_open')
    assert r.iloc[0] == 0.0
    # Day 1: cash overnight, bought at open, so earns open->close only
    assert r.iloc[1] == pytest.approx((1 + CASH) * close.iloc[1] / open_.iloc[1] - 1)
    # From day 2 on: fully invested both legs = close-to-close
    np.testing.assert_allclose(r.iloc[2:], close.pct_change().iloc[2:])


def test_always_cash_earns_cash(prices):
    open_, close = prices
    w = pd.Series(0.0, index=close.index)
    for fill in ('next_open', 'moc'):
        r = bc.strategy_returns(w, open_, close, fill)
        np.testing.assert_allclose(r.iloc[1:], CASH)


def test_moc_uses_previous_decision(prices):
    open_, close = prices
    w = pd.Series(0.0, index=close.index)
    w.iloc[10] = 1.0  # decided at close of day 10
    r = bc.strategy_returns(w, open_, close, 'moc')
    assert r.iloc[11] == pytest.approx(close.iloc[11] / close.iloc[10] - 1)
    assert r.iloc[10] == pytest.approx(CASH)


def test_next_open_fills_at_following_open(prices):
    open_, close = prices
    w = pd.Series(0.0, index=close.index)
    w.iloc[10:20] = 1.0  # buy decided at close 10, sell decided at close 19
    r = bc.strategy_returns(w, open_, close, 'next_open')
    assert r.iloc[10] == pytest.approx(CASH)                      # still cash on decision day
    assert r.iloc[11] == pytest.approx((1 + CASH) * close.iloc[11] / open_.iloc[11] - 1)
    # Last 1.0 decision at close 19 -> still invested on day 20
    assert r.iloc[20] == pytest.approx(close.iloc[20] / close.iloc[19] - 1)
    # Exit decided at close 20: hold overnight, sell at open 21, cash intraday
    assert r.iloc[21] == pytest.approx(open_.iloc[21] / close.iloc[20] - 1)


@pytest.mark.parametrize('fill', ['next_open', 'moc'])
def test_no_lookahead(prices, fill):
    """Changing prices after day t must not change returns up to day t."""
    open_, close = prices
    w = (close > close.rolling(5).mean()).astype(float)
    base = bc.strategy_returns(w, open_, close, fill)
    t = 30
    close2, open2 = close.copy(), open_.copy()
    close2.iloc[t + 1:] *= 1.5
    open2.iloc[t + 1:] *= 0.7
    w2 = (close2 > close2.rolling(5).mean()).astype(float)
    moved = bc.strategy_returns(w2, open2, close2, fill)
    np.testing.assert_allclose(base.iloc[:t + 1], moved.iloc[:t + 1])


def test_trade_log_splits_on_level_change(prices):
    open_, close = prices
    w = pd.Series(0.0, index=close.index)
    w.iloc[5:15] = 1.0    # trend
    w.iloc[15:25] = 0.5   # direct switch to sniper
    w.iloc[25:30] = 0.0
    w.iloc[30:] = 0.5     # still open
    r = bc.strategy_returns(w, open_, close, 'next_open')
    log = bc.trade_log(w, r, open_, close)
    assert list(log['Type']) == ['Trend (SMA)', 'Sniper (RSI)', 'Sniper (RSI)']
    assert list(log['Exit_Reason']) == ['SMA break -> Sniper', 'RSI target', 'Still open']
    assert list(log['Status']) == ['CLOSED', 'CLOSED', 'OPEN']
    # Fill dates are the opens after the deciding closes
    assert log['Entry_Date'].iloc[0] == close.index[6].date()
    assert log['Exit_Date'].iloc[0] == close.index[16].date()
    assert log['Return_Asset'].iloc[0] == pytest.approx(open_.iloc[16] / open_.iloc[6] - 1)


def test_trade_returns_chain_to_equity(prices):
    """Fully invested trade return equals equity growth between the fills."""
    open_, close = prices
    w = pd.Series(0.0, index=close.index)
    w.iloc[5:15] = 1.0
    r = bc.strategy_returns(w, open_, close, 'next_open')
    log = bc.trade_log(w, r, open_, close)
    assert log['Return_Strategy'].iloc[0] == pytest.approx(log['Return_Asset'].iloc[0])


def test_metrics_basic(prices):
    _, close = prices
    bench = close.pct_change().fillna(0.0)
    values = bc.buy_hold_equity(close)
    m = bc.performance_metrics(values, bench, bench, bench)
    assert m['Final_Value'] == pytest.approx(values.iloc[-1])
    assert m['Beta_BH'] == pytest.approx(1.0)
    assert m['Alpha_BH'] == pytest.approx(0.0, abs=1e-12)
    assert m['Max_Drawdown'] <= 0
