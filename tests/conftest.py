"""
Shared pytest fixtures for LRS unit tests.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


@pytest.fixture
def sample_price_data():
    """Generate sample price data for testing."""
    dates = pd.date_range('2020-01-01', periods=300, freq='D')
    np.random.seed(42)
    
    # Generate realistic price movement (random walk with drift)
    returns = np.random.normal(0.0005, 0.015, len(dates))
    prices = 100 * np.exp(np.cumsum(returns))
    
    df = pd.DataFrame({
        'Close': prices,
        'Open': prices * 0.999,
        'High': prices * 1.01,
        'Low': prices * 0.99,
        'Volume': np.random.randint(1000000, 5000000, len(dates))
    }, index=dates)
    
    return df


@pytest.fixture
def bull_trend_data():
    """Generate data with consistent uptrend (Close > SMA_200)."""
    dates = pd.date_range('2020-01-01', periods=250, freq='D')
    # Monotonically increasing prices
    prices = np.linspace(100, 200, len(dates))
    
    df = pd.DataFrame({'Close': prices}, index=dates)
    return df


@pytest.fixture
def bear_trend_data():
    """Generate data with consistent downtrend (Close < SMA_200)."""
    dates = pd.date_range('2020-01-01', periods=250, freq='D')
    # Monotonically decreasing prices
    prices = np.linspace(200, 100, len(dates))
    
    df = pd.DataFrame({'Close': prices}, index=dates)
    return df


@pytest.fixture
def oversold_data():
    """Generate data with RSI < 30 (oversold condition)."""
    dates = pd.date_range('2020-01-01', periods=50, freq='D')
    # Sharp decline to trigger oversold RSI
    prices = np.concatenate([
        np.linspace(100, 100, 20),  # Flat
        np.linspace(100, 60, 30)    # Sharp decline
    ])
    
    df = pd.DataFrame({'Close': prices}, index=dates)
    return df


@pytest.fixture
def flat_price_data():
    """Generate perfectly flat price data."""
    dates = pd.date_range('2020-01-01', periods=50, freq='D')
    prices = np.full(len(dates), 100.0)
    
    df = pd.DataFrame({'Close': prices}, index=dates)
    return df


@pytest.fixture
def sample_strategy_returns():
    """Generate sample returns data for metrics calculation."""
    dates = pd.date_range('2020-01-01', periods=252, freq='D')  # ~1 year
    np.random.seed(42)
    
    # Generate returns
    returns = np.random.normal(0.0008, 0.02, len(dates))
    
    # Calculate cumulative values
    initial_capital = 10000
    values = initial_capital * np.cumprod(1 + returns)
    
    df = pd.DataFrame({
        'LRS_Return': returns,
        'LRS_Value': values
    }, index=dates)
    
    return df
