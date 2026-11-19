"""
Tests for the shared downloader (src/update_data.py) and the dashboard's
refresh path (src/lrs_web_utils.get_hybrid_sniper_data).
"""
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import update_data  # noqa: E402
import lrs_web_utils  # noqa: E402
from update_data import ET  # noqa: E402


def bars(end, periods=5):
    """Return simple daily OHLCV bars ending on ``end``."""
    idx = pd.bdate_range(end=end, periods=periods)
    close = np.arange(100.0, 100.0 + periods)
    return pd.DataFrame({'Open': close, 'High': close + 1, 'Low': close - 1,
                         'Close': close, 'Volume': 1_000_000}, index=idx)


def et(*args):
    """Build a US/Eastern aware datetime."""
    return ET.localize(datetime(*args))


class TestLastBarIsFinal:
    """A bar dated today is only final after 16:15 ET."""

    def test_today_during_session_is_not_final(self):
        df = bars('2026-11-19')
        assert not update_data.last_bar_is_final(df, et(2026, 11, 19, 13, 0))

    def test_today_after_close_is_final(self):
        df = bars('2026-11-19')
        assert update_data.last_bar_is_final(df, et(2026, 11, 19, 16, 15))

    def test_yesterday_is_final(self):
        df = bars('2026-11-18')
        assert update_data.last_bar_is_final(df, et(2026, 11, 19, 10, 0))

    def test_utc_clock_is_converted_to_eastern(self):
        # 20:00 UTC = 15:00 ET (EST): session still open
        df = bars('2026-11-19')
        now = pytz_utc(datetime(2026, 11, 19, 20, 0))
        assert not update_data.last_bar_is_final(df, now)

    def test_drop_incomplete_bar_removes_only_today(self):
        df = bars('2026-11-19')
        out = update_data.drop_incomplete_bar(df, et(2026, 11, 19, 11, 0))
        assert out.index[-1] == pd.Timestamp('2026-11-18')
        assert len(out) == len(df) - 1


def pytz_utc(naive):
    """Localize a naive datetime to UTC."""
    import pytz
    return pytz.utc.localize(naive)


class TestSaveCsv:
    """save_csv never writes intraday or empty data and replaces atomically."""

    def test_intraday_bar_not_saved(self, tmp_path):
        path = tmp_path / 'x.csv'
        update_data.save_csv(bars('2026-11-19'), str(path), et(2026, 11, 19, 12, 0))
        saved = pd.read_csv(path, index_col=0, parse_dates=True)
        assert saved.index[-1] == pd.Timestamp('2026-11-18')

    def test_empty_frame_refused_and_old_file_kept(self, tmp_path):
        path = tmp_path / 'x.csv'
        path.write_text('old')
        with pytest.raises(ValueError):
            update_data.save_csv(bars('2026-11-19').iloc[:0], str(path))
        assert path.read_text() == 'old'

    def test_saved_format(self, tmp_path):
        path = tmp_path / 'x.csv'
        update_data.save_csv(bars('2026-11-18'), str(path), et(2026, 11, 19, 12, 0))
        assert path.read_text().splitlines()[0] == 'Date,Open,High,Low,Close,Volume'
        assert not list(tmp_path.glob('*.tmp*'))


class TestDownloadOhlcv:
    """download_ohlcv normalizes yfinance output and rejects empty results."""

    def test_empty_download_raises(self, monkeypatch):
        monkeypatch.setattr(update_data.yf, 'download', lambda *a, **k: pd.DataFrame())
        with pytest.raises(ValueError):
            update_data.download_ohlcv('ZZZZ', '2020-01-01')

    def test_columns_and_adjustment(self, monkeypatch):
        calls = {}
        raw = bars('2026-11-18')
        raw['Adj Close'] = raw['Close']

        def fake_download(symbol, **kwargs):
            calls.update(kwargs)
            return raw[['Close', 'High', 'Low', 'Open', 'Volume', 'Adj Close']]

        monkeypatch.setattr(update_data.yf, 'download', fake_download)
        df = update_data.download_ohlcv('TQQQ', '2010-02-09')
        assert list(df.columns) == update_data.OHLCV_COLUMNS
        assert df.index.name == 'Date'
        assert calls['auto_adjust'] is True


class TestRefreshFallback:
    """A failed download falls back to cached CSVs and leaves them untouched."""

    def test_download_failure_uses_cache(self, monkeypatch, tmp_path):
        idx = pd.bdate_range(end='2026-11-18', periods=400)
        close = pd.Series(np.linspace(100, 200, len(idx)), index=idx)
        frame = pd.DataFrame({'Open': close, 'High': close, 'Low': close,
                              'Close': close, 'Volume': 1}, index=idx)
        frame.index.name = 'Date'
        for name in ('sp500', 'tqqq', 'vix'):
            frame.to_csv(tmp_path / f'{name}.csv')
        before = (tmp_path / 'sp500.csv').read_text()

        def boom():
            raise ValueError("yfinance returned no data")

        monkeypatch.setattr(lrs_web_utils, 'DATA_DIR', str(tmp_path))
        monkeypatch.setattr(lrs_web_utils, 'download_fresh_data', boom)

        df = lrs_web_utils.get_hybrid_sniper_data(force_refresh=True)
        assert df.index[-1] == pd.Timestamp('2026-11-18')
        assert (tmp_path / 'sp500.csv').read_text() == before

    def test_download_failure_without_cache_raises(self, monkeypatch, tmp_path):
        def boom():
            raise ValueError("offline")

        monkeypatch.setattr(lrs_web_utils, 'DATA_DIR', str(tmp_path))
        monkeypatch.setattr(lrs_web_utils, 'download_fresh_data', boom)
        with pytest.raises(FileNotFoundError):
            lrs_web_utils.get_hybrid_sniper_data(force_refresh=True)
