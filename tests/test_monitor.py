"""
Tests for the Hybrid Sniper monitor's scheduling and alert/state logic.
"""
import os
import sys
import json
from datetime import datetime, date

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import monitor_hybrid_sniper as monitor  # noqa: E402
from update_data import ET  # noqa: E402


def et(*args):
    """Build a US/Eastern aware datetime."""
    return ET.localize(datetime(*args))


def test_imports_src_strategy_module():
    """The monitor must use src/lrs_hybrid_sniper.py, not the root copy."""
    import lrs_hybrid_sniper
    assert os.path.dirname(lrs_hybrid_sniper.__file__) == monitor.SRC_DIR


def test_paths_are_absolute():
    assert os.path.isabs(monitor.STATE_FILE)
    assert os.path.isabs(monitor.LOG_FILE)


class TestSchedule:
    """The monitor acts once per completed close."""

    def test_expected_bar_before_close_is_previous_day(self):
        assert monitor.expected_bar_date(et(2026, 11, 19, 15, 0)) == date(2026, 11, 18)

    def test_expected_bar_after_close_is_today(self):
        assert monitor.expected_bar_date(et(2026, 11, 19, 16, 20)) == date(2026, 11, 19)

    def test_monday_morning_expects_friday(self):
        assert monitor.expected_bar_date(et(2026, 11, 23, 9, 0)) == date(2026, 11, 20)

    def test_weekend_expects_friday(self):
        assert monitor.expected_bar_date(et(2026, 11, 22, 18, 0)) == date(2026, 11, 20)

    def test_should_check(self):
        now = et(2026, 11, 19, 16, 30)
        assert monitor.should_check({}, now)
        assert monitor.should_check({'last_bar_date': '2026-11-18'}, now)
        assert not monitor.should_check({'last_bar_date': '2026-11-19'}, now)


@pytest.fixture
def run_check(monkeypatch, tmp_path):
    """
    Run check_signals against a fake latest close and a temp state file.

    Returns a function(regime, ma_below, state, send_ok) -> (state, emails).
    """
    def _run(regime, ma_below, state=None, send_ok=True):
        state_file = tmp_path / 'state.json'
        if state is not None:
            state_file.write_text(json.dumps(state))
        emails = []
        latest = {'date': '2026-11-19', 'price': 7000.0, 'rsi': 45.0,
                  'regime': regime, 'ma_10': 6900.0 if ma_below else 7100.0,
                  'sma_200': 7000.0}
        monkeypatch.setattr(monitor, 'STATE_FILE', str(state_file))
        monkeypatch.setattr(monitor, 'LOG_FILE', str(tmp_path / 'monitor.log'))
        monkeypatch.setattr(monitor, 'get_hybrid_sniper_data', lambda force_refresh: None)
        monkeypatch.setattr(monitor, 'drop_incomplete_bar', lambda df: df)
        monkeypatch.setattr(monitor, 'get_latest_signals', lambda df: latest)

        def fake_send(subject, body, dry_run=False):
            emails.append(subject)
            return send_ok

        monkeypatch.setattr(monitor, 'send_email', fake_send)
        monitor.check_signals()
        return json.loads(state_file.read_text()), emails

    return _run


class TestAlerts:
    """Alert on changes in the close's decision; never lose a failed alert."""

    def test_first_run_records_without_alerting(self, run_check):
        state, emails = run_check(1.0, ma_below=True)
        assert emails == []
        assert state['last_regime'] == 1.0
        assert state['last_ma_cross'] is True
        assert state['last_bar_date'] == '2026-11-19'

    def test_regime_change_alerts_with_next_open(self, run_check):
        prior = {'last_regime': 1.0, 'last_ma_cross': True, 'last_bar_date': '2026-11-18'}
        state, emails = run_check(0.0, ma_below=True, state=prior)
        assert emails == ['📉 Hybrid Sniper Alert: Signal Change to 0.0']
        assert state['last_regime'] == 0.0

    def test_failed_send_keeps_state_for_retry(self, run_check):
        prior = {'last_regime': 1.0, 'last_ma_cross': False, 'last_bar_date': '2026-11-18'}
        state, emails = run_check(0.0, ma_below=True, state=prior, send_ok=False)
        assert len(emails) == 2
        assert state['last_regime'] == 1.0
        assert state['last_ma_cross'] is False
        assert state['last_bar_date'] == '2026-11-18'

    def test_no_change_no_alert(self, run_check):
        prior = {'last_regime': 1.0, 'last_ma_cross': False, 'last_bar_date': '2026-11-18'}
        state, emails = run_check(1.0, ma_below=False, state=prior)
        assert emails == []
        assert state['last_bar_date'] == '2026-11-19'

    def test_alert_body_says_next_open(self):
        latest = {'date': '2026-11-19', 'price': 7000.0, 'rsi': 45.0,
                  'regime': 0.5, 'ma_10': 6800.0, 'sma_200': 7000.0}
        subject, body = monitor.regime_alert(latest, 0.0)
        assert 'next market open' in body
        assert 'close of: 2026-11-19' in body
