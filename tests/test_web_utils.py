"""
Unit tests for lrs_web_utils.py

Tests cover:
- Market hours detection
- Live price fetching (mocked)
- Signal status extraction
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, time
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from lrs_web_utils import (
    should_fetch_live_data,
    fetch_live_prices,
    get_latest_signals
)


class TestShouldFetchLiveData:
    """Tests for market data fetching logic (should fetch if weekday >= 9:30 AM)."""
    
    @patch('lrs_web_utils.datetime')
    def test_market_closed_on_saturday(self, mock_datetime):
        """Should return False on Saturday."""
        import pytz
        et = pytz.timezone('America/New_York')
        # Saturday at noon
        mock_now = datetime(2024, 1, 6, 12, 0, 0, tzinfo=et)  # Saturday
        mock_datetime.now.return_value = mock_now
        
        assert should_fetch_live_data() == False
    
    @patch('lrs_web_utils.datetime')
    def test_market_closed_on_sunday(self, mock_datetime):
        """Should return False on Sunday."""
        import pytz
        et = pytz.timezone('America/New_York')
        mock_now = datetime(2024, 1, 7, 12, 0, 0, tzinfo=et)  # Sunday
        mock_datetime.now.return_value = mock_now
        
        assert should_fetch_live_data() == False
    
    @patch('lrs_web_utils.datetime')
    def test_market_open_during_trading_hours(self, mock_datetime):
        """Should return True at 10:00 AM ET on a weekday."""
        import pytz
        et = pytz.timezone('America/New_York')
        # Monday at 10:00 AM
        mock_now = datetime(2024, 1, 8, 10, 0, 0, tzinfo=et)  # Monday
        mock_datetime.now.return_value = mock_now
        
        assert should_fetch_live_data() == True
    
    @patch('lrs_web_utils.datetime')
    def test_market_closed_before_open(self, mock_datetime):
        """Should return False before 9:30 AM ET."""
        import pytz
        et = pytz.timezone('America/New_York')
        # Monday at 8:00 AM
        mock_now = datetime(2024, 1, 8, 8, 0, 0, tzinfo=et)
        mock_datetime.now.return_value = mock_now
        
        assert should_fetch_live_data() == False
    
    @patch('lrs_web_utils.datetime')
    def test_market_closed_after_close(self, mock_datetime):
        """Should return True after 4:00 PM ET (to fetch close data)."""
        import pytz
        et = pytz.timezone('America/New_York')
        # Monday at 5:00 PM
        mock_now = datetime(2024, 1, 8, 17, 0, 0, tzinfo=et)
        mock_datetime.now.return_value = mock_now
        
        # CHANGED: Allows fetching after close
        assert should_fetch_live_data() == True
    
    @patch('lrs_web_utils.datetime')
    def test_market_open_at_boundary_930(self, mock_datetime):
        """Should return True at exactly 9:30 AM ET."""
        import pytz
        et = pytz.timezone('America/New_York')
        mock_now = datetime(2024, 1, 8, 9, 30, 0, tzinfo=et)
        mock_datetime.now.return_value = mock_now
        
        assert should_fetch_live_data() == True


class TestFetchLivePrices:
    """Tests for live price fetching (mocked)."""
    
    @patch('lrs_web_utils.yf')
    def test_fetch_returns_dict_on_success(self, mock_yf):
        """Successful fetch should return dict with spx and tqqq keys."""
        # Mock the yfinance Ticker objects
        mock_spx = MagicMock()
        mock_spx.fast_info = {'lastPrice': 5000.0}
        
        mock_tqqq = MagicMock()
        mock_tqqq.fast_info = {'lastPrice': 50.0}
        
        mock_yf.Ticker.side_effect = [mock_spx, mock_tqqq]
        
        result = fetch_live_prices()
        
        assert result is not None
        assert 'spx' in result
        assert 'tqqq' in result
        assert 'timestamp' in result
    
    @patch('lrs_web_utils.yf')
    def test_fetch_returns_none_on_error(self, mock_yf):
        """Fetch should return None on network/API error."""
        mock_yf.Ticker.side_effect = Exception("Network error")
        
        result = fetch_live_prices()
        assert result is None
    
    @patch('lrs_web_utils.yf')
    def test_fetch_returns_none_on_missing_price(self, mock_yf):
        """Fetch should return None if price data is missing."""
        mock_spx = MagicMock()
        mock_spx.fast_info = {'lastPrice': None}  # Missing price
        
        mock_tqqq = MagicMock()
        mock_tqqq.fast_info = {'lastPrice': 50.0}
        
        mock_yf.Ticker.side_effect = [mock_spx, mock_tqqq]
        
        result = fetch_live_prices()
        assert result is None


class TestGetLatestSignals:
    """Tests for signal status extraction."""
    
    @pytest.fixture
    def sample_df_with_signals(self):
        """Create sample DataFrame with all required columns."""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'Close': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            'SMA_200': [95, 96, 97, 98, 99, 100, 101, 102, 103, 104],
            'RSI': [45, 50, 55, 60, 65, 70, 75, 25, 30, 35],
            'Signal': [0.0, 0.0, 0.5, 0.5, 1.0, 1.0, 1.0, 0.5, 0.0, 0.0],
            'Regime': [0, 0, 0.5, 0.5, 1.0, 1.0, 1.0, 0.5, 0, 0],
            'TQQQ_Close': [50, 51, 52, 53, 54, 55, 56, 57, 58, 59]
        }, index=dates)
        return df
    
    def test_returns_dict(self, sample_df_with_signals):
        """get_latest_signals should return a dictionary."""
        result = get_latest_signals(sample_df_with_signals)
        assert isinstance(result, dict)
    
    def test_contains_required_keys(self, sample_df_with_signals):
        """Result should contain all required status keys."""
        result = get_latest_signals(sample_df_with_signals)
        
        required_keys = ['date', 'price', 'tqqq_price', 'sma_200', 'rsi', 'signal_alloc', 
                        'regime', 'trend_signal', 'sniper_signal', 'mode', 'mode_class']
        for key in required_keys:
            assert key in result, f"Missing key: {key}"
    
    def test_trend_mode_when_signal_1(self):
        """Mode should be TREND MODE when Signal = 1.0."""
        dates = pd.date_range('2024-01-01', periods=2, freq='D')
        df = pd.DataFrame({
            'Close': [110, 115],
            'SMA_200': [100, 100],
            'RSI': [60, 65],
            'Signal': [1.0, 1.0],
            'Regime': [1, 1],
            'TQQQ_Close': [50, 51]
        }, index=dates)
        
        result = get_latest_signals(df)
        assert 'TREND MODE' in result['mode']
        assert result['mode_class'] == 'mode-bull'
    
    def test_sniper_mode_when_signal_05(self):
        """Mode should be SNIPER MODE when Signal = 0.5."""
        dates = pd.date_range('2024-01-01', periods=2, freq='D')
        df = pd.DataFrame({
            'Close': [90, 85],
            'SMA_200': [100, 100],
            'RSI': [25, 28],
            'Signal': [0.5, 0.5],
            'Regime': [0.5, 0.5],
            'TQQQ_Close': [40, 41]
        }, index=dates)
        
        result = get_latest_signals(df)
        assert 'SNIPER MODE' in result['mode']
        assert result['mode_class'] == 'mode-sniper'
    
    def test_cash_mode_when_signal_0(self):
        """Mode should be CASH when Signal = 0.0."""
        dates = pd.date_range('2024-01-01', periods=2, freq='D')
        df = pd.DataFrame({
            'Close': [80, 75],
            'SMA_200': [100, 100],
            'RSI': [55, 60],
            'Signal': [0.0, 0.0],
            'Regime': [0, 0],
            'TQQQ_Close': [30, 31]
        }, index=dates)
        
        result = get_latest_signals(df)
        assert 'CASH' in result['mode']
        assert result['mode_class'] == 'mode-cash'
    
    def test_trend_signal_bull_when_above_sma(self):
        """Trend signal should be BULL when Close > SMA_200."""
        dates = pd.date_range('2024-01-01', periods=2, freq='D')
        df = pd.DataFrame({
            'Close': [110, 115],  # Above SMA
            'SMA_200': [100, 100],
            'RSI': [60, 65],
            'Signal': [1.0, 1.0],
            'Regime': [1, 1],
            'TQQQ_Close': [50, 51]
        }, index=dates)
        
        result = get_latest_signals(df)
        assert result['trend_signal'] == 'BULL'
    
    def test_trend_signal_bear_when_below_sma(self):
        """Trend signal should be BEAR when Close < SMA_200."""
        dates = pd.date_range('2024-01-01', periods=2, freq='D')
        df = pd.DataFrame({
            'Close': [90, 85],  # Below SMA
            'SMA_200': [100, 100],
            'RSI': [40, 45],
            'Signal': [0.0, 0.0],
            'Regime': [0, 0],
            'TQQQ_Close': [40, 41]
        }, index=dates)
        
        result = get_latest_signals(df)
        assert result['trend_signal'] == 'BEAR'
    
    def test_sniper_signal_oversold_when_rsi_below_30(self):
        """Sniper signal should be OVERSOLD when RSI < 30."""
        dates = pd.date_range('2024-01-01', periods=2, freq='D')
        df = pd.DataFrame({
            'Close': [90, 85],
            'SMA_200': [100, 100],
            'RSI': [25, 28],  # Below 30
            'Signal': [0.5, 0.5],
            'Regime': [0.5, 0.5],
            'TQQQ_Close': [40, 41]
        }, index=dates)
        
        result = get_latest_signals(df)
        assert result['sniper_signal'] == 'OVERSOLD'
    
    def test_sniper_signal_neutral_when_rsi_above_30(self):
        """Sniper signal should be NEUTRAL when RSI >= 30."""
        dates = pd.date_range('2024-01-01', periods=2, freq='D')
        df = pd.DataFrame({
            'Close': [110, 115],
            'SMA_200': [100, 100],
            'RSI': [55, 60],  # Above 30
            'Signal': [1.0, 1.0],
            'Regime': [1, 1],
            'TQQQ_Close': [50, 51]
        }, index=dates)
        
        result = get_latest_signals(df)
        assert result['sniper_signal'] == 'NEUTRAL'
    
    def test_price_matches_last_close(self, sample_df_with_signals):
        """Reported price should match the last Close value."""
        result = get_latest_signals(sample_df_with_signals)
        expected_price = sample_df_with_signals['Close'].iloc[-1]
        assert result['price'] == expected_price
    
    def test_date_format(self, sample_df_with_signals):
        """Date should be in YYYY-MM-DD format."""
        result = get_latest_signals(sample_df_with_signals)
        
        # Should be parseable as date
        from datetime import datetime
        parsed = datetime.strptime(result['date'], '%Y-%m-%d')
        assert parsed is not None
