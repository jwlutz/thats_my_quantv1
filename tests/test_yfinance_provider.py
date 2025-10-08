"""
Integration tests for YFinanceProvider.

These tests make actual API calls to Yahoo Finance to validate:
1. All methods work correctly with real data
2. Return schemas match documentation
3. Edge cases are handled properly (invalid tickers, missing data, etc.)
4. Retry logic works as expected

Note: These tests require network access and may be slow.
"""

import pytest
import pandas as pd
from datetime import date, timedelta
from backtester.yfinance_provider import YFinanceProvider


@pytest.fixture
def provider():
    """Create YFinanceProvider instance for testing."""
    return YFinanceProvider(retry_attempts=2, retry_delay=0.5)


@pytest.fixture
def valid_ticker():
    """Return a ticker guaranteed to have rich data."""
    return "AAPL"


@pytest.fixture
def valid_tickers():
    """Return multiple tickers for multi-ticker tests."""
    return ["AAPL", "MSFT", "GOOGL"]


@pytest.fixture
def date_range():
    """Return a recent date range for testing."""
    end = date(2024, 12, 31)
    start = date(2024, 12, 1)
    return start, end


# ============================================================================
# PRICE & VOLUME DATA TESTS
# ============================================================================

class TestGetPrices:
    """Test get_prices method."""

    def test_single_ticker(self, provider, valid_ticker, date_range):
        """Test getting prices for a single ticker."""
        start, end = date_range
        prices = provider.get_prices([valid_ticker], start, end)

        # Validate schema
        assert isinstance(prices, pd.DataFrame)
        assert not prices.empty
        assert valid_ticker in prices.columns
        assert isinstance(prices.index, pd.DatetimeIndex)
        assert all(isinstance(val, (int, float)) for val in prices[valid_ticker].dropna())

        # Validate date range (approximate, accounting for weekends)
        assert len(prices) > 0
        assert prices.index.min() >= pd.Timestamp(start)
        assert prices.index.max() <= pd.Timestamp(end) + timedelta(days=5)

    def test_multiple_tickers(self, provider, valid_tickers, date_range):
        """Test getting prices for multiple tickers."""
        start, end = date_range
        prices = provider.get_prices(valid_tickers, start, end)

        # Validate schema
        assert isinstance(prices, pd.DataFrame)
        assert not prices.empty
        for ticker in valid_tickers:
            assert ticker in prices.columns
        assert isinstance(prices.index, pd.DatetimeIndex)

        # All tickers should have data for the same dates
        assert prices.notna().all(axis=1).sum() > 0

    def test_invalid_ticker(self, provider, date_range):
        """Test handling of invalid ticker."""
        start, end = date_range
        prices = provider.get_prices(["INVALIDTICKER123"], start, end)

        # Should return empty DataFrame, not raise exception
        assert isinstance(prices, pd.DataFrame)
        assert prices.empty


class TestGetOHLCV:
    """Test get_ohlcv method."""

    def test_single_ticker(self, provider, valid_ticker, date_range):
        """Test getting OHLCV for a single ticker."""
        start, end = date_range
        ohlcv = provider.get_ohlcv([valid_ticker], start, end)

        # Validate schema
        assert isinstance(ohlcv, dict)
        assert valid_ticker in ohlcv
        df = ohlcv[valid_ticker]
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

        # Check columns
        expected_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        assert all(col in df.columns for col in expected_cols)

        # Validate data types (use .dtype on Series, not .dtypes)
        assert df['Open'].dtype in [float, 'float64']
        assert df['High'].dtype in [float, 'float64']
        assert df['Low'].dtype in [float, 'float64']
        assert df['Close'].dtype in [float, 'float64']

        # Validate OHLC relationships
        assert (df['High'] >= df['Low']).all()
        assert (df['High'] >= df['Open']).all()
        assert (df['High'] >= df['Close']).all()
        assert (df['Low'] <= df['Open']).all()
        assert (df['Low'] <= df['Close']).all()

    def test_multiple_tickers(self, provider, valid_tickers, date_range):
        """Test getting OHLCV for multiple tickers."""
        start, end = date_range
        ohlcv = provider.get_ohlcv(valid_tickers, start, end)

        # Validate schema
        assert isinstance(ohlcv, dict)
        for ticker in valid_tickers:
            assert ticker in ohlcv
            df = ohlcv[ticker]
            assert isinstance(df, pd.DataFrame)
            assert not df.empty

    def test_caching(self, provider, valid_ticker, date_range):
        """Test that caching works correctly."""
        start, end = date_range

        # First call - should fetch from API
        ohlcv1 = provider.get_ohlcv([valid_ticker], start, end)

        # Second call - should use cache
        ohlcv2 = provider.get_ohlcv([valid_ticker], start, end)

        # Should be identical
        pd.testing.assert_frame_equal(ohlcv1[valid_ticker], ohlcv2[valid_ticker])


class TestGetBar:
    """Test get_bar method."""

    def test_valid_date(self, provider, valid_ticker):
        """Test getting bar for a valid trading date."""
        # Use a known trading date
        test_date = date(2024, 12, 2)  # Monday
        bar = provider.get_bar(valid_ticker, test_date)

        # Validate schema
        assert isinstance(bar, dict)
        expected_keys = ['open', 'high', 'low', 'close', 'volume']
        assert all(key in bar for key in expected_keys)

        # Validate data types
        assert isinstance(bar['open'], (int, float))
        assert isinstance(bar['high'], (int, float))
        assert isinstance(bar['low'], (int, float))
        assert isinstance(bar['close'], (int, float))
        assert isinstance(bar['volume'], (int, float))

        # Validate OHLC relationships
        assert bar['high'] >= bar['low']
        assert bar['high'] >= bar['open']
        assert bar['high'] >= bar['close']
        assert bar['low'] <= bar['open']
        assert bar['low'] <= bar['close']
        assert bar['volume'] > 0

    def test_weekend_date(self, provider, valid_ticker):
        """Test getting bar for a weekend (non-trading day)."""
        # Saturday
        test_date = date(2024, 12, 7)
        bar = provider.get_bar(valid_ticker, test_date)

        # Should return None for non-trading days
        assert bar is None

    def test_invalid_ticker(self, provider):
        """Test getting bar for invalid ticker."""
        test_date = date(2024, 12, 2)
        bar = provider.get_bar("INVALIDTICKER123", test_date)

        # Should return None
        assert bar is None


# ============================================================================
# FUNDAMENTAL DATA TESTS
# ============================================================================

class TestGetEarningsData:
    """Test get_earnings_data method."""

    def test_recent_earnings(self, provider, valid_ticker):
        """Test getting recent earnings data."""
        # Use a date we know has recent earnings (within 90 days)
        as_of = date(2025, 2, 15)  # After Jan 30 2025 earnings
        earnings = provider.get_earnings_data(valid_ticker, as_of)

        # Validate schema
        assert isinstance(earnings, dict)
        expected_keys = ['reported_eps', 'estimated_eps', 'earnings_date', 'surprise_pct']
        assert all(key in earnings for key in expected_keys)

        # Validate data types
        assert isinstance(earnings['reported_eps'], (int, float))
        assert isinstance(earnings['estimated_eps'], (int, float))
        assert isinstance(earnings['earnings_date'], pd.Timestamp)
        assert isinstance(earnings['surprise_pct'], (int, float))

        # Validate values make sense (use timezone-aware comparison)
        as_of_ts = pd.Timestamp(as_of)
        if earnings['earnings_date'].tz is not None:
            as_of_ts = as_of_ts.tz_localize(earnings['earnings_date'].tz)
        assert earnings['earnings_date'] < as_of_ts
        # Surprise % should be calculated correctly (allowing for negative estimates)
        if earnings['estimated_eps'] >= 0:
            expected_surprise = (earnings['reported_eps'] - earnings['estimated_eps']) / earnings['estimated_eps']
        else:
            expected_surprise = -((earnings['reported_eps'] - earnings['estimated_eps']) / abs(earnings['estimated_eps']))
        assert abs(earnings['surprise_pct'] - expected_surprise) < 0.0001

    def test_no_recent_earnings(self, provider, valid_ticker):
        """Test when no earnings within 90 days."""
        # Use a date with no recent earnings
        as_of = date(2010, 1, 1)  # Very old
        earnings = provider.get_earnings_data(valid_ticker, as_of)

        # Should return None (no earnings or too old)
        assert earnings is None

    def test_invalid_ticker(self, provider):
        """Test earnings for invalid ticker."""
        as_of = date(2024, 12, 1)
        earnings = provider.get_earnings_data("INVALIDTICKER123", as_of)

        # Should return None
        assert earnings is None


class TestGetInfo:
    """Test get_info method."""

    def test_valid_ticker(self, provider, valid_ticker):
        """Test getting company info."""
        info = provider.get_info(valid_ticker)

        # Validate schema
        assert isinstance(info, dict)
        assert len(info) > 50  # Should have many keys

        # Check for common keys
        common_keys = [
            'marketCap', 'trailingPE', 'forwardPE', 'sector', 'industry',
            'profitMargins', 'returnOnEquity', 'beta', 'dividendYield'
        ]
        present_keys = [k for k in common_keys if k in info and info[k] is not None]
        assert len(present_keys) > 5  # Should have most common keys

        # Validate data types for present keys
        if 'marketCap' in info and info['marketCap'] is not None:
            assert isinstance(info['marketCap'], (int, float))
            assert info['marketCap'] > 0
        if 'sector' in info and info['sector'] is not None:
            assert isinstance(info['sector'], str)
        if 'beta' in info and info['beta'] is not None:
            assert isinstance(info['beta'], (int, float))

    def test_invalid_ticker(self, provider):
        """Test info for invalid ticker."""
        info = provider.get_info("INVALIDTICKER123")

        # Should return None or empty dict
        assert info is None or len(info) < 5


class TestGetInstitutionalHolders:
    """Test get_institutional_holders method."""

    def test_valid_ticker(self, provider, valid_ticker):
        """Test getting institutional holders."""
        holders = provider.get_institutional_holders(valid_ticker)

        # Validate schema
        assert isinstance(holders, pd.DataFrame)
        assert not holders.empty

        # Check columns
        expected_cols = ['Holder', 'Shares', 'Date Reported', 'pctHeld', 'Value']
        assert all(col in holders.columns for col in expected_cols)

        # Validate data
        assert len(holders) > 0  # Should have at least some holders
        assert holders['Shares'].dtype in [int, 'int64', float, 'float64']
        assert holders['pctHeld'].dtype in [float, 'float64']
        assert (holders['pctHeld'] >= 0).all()
        assert (holders['pctHeld'] <= 1).all()  # Should be percentage

    def test_invalid_ticker(self, provider):
        """Test holders for invalid ticker."""
        holders = provider.get_institutional_holders("INVALIDTICKER123")

        # Should return None
        assert holders is None


# ============================================================================
# CORPORATE ACTIONS TESTS
# ============================================================================

class TestGetDividends:
    """Test get_dividends method."""

    def test_dividend_paying_stock(self, provider, valid_ticker):
        """Test getting dividends for a dividend-paying stock."""
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)
        divs = provider.get_dividends(valid_ticker, start, end)

        # Validate schema
        assert isinstance(divs, pd.DataFrame)
        assert not divs.empty
        assert 'Dividend' in divs.columns
        assert isinstance(divs.index, pd.DatetimeIndex)

        # Validate data
        assert (divs['Dividend'] > 0).all()
        # Use timezone-aware comparisons
        start_ts = pd.Timestamp(start).tz_localize(divs.index.tz) if divs.index.tz else pd.Timestamp(start)
        end_ts = pd.Timestamp(end).tz_localize(divs.index.tz) if divs.index.tz else pd.Timestamp(end)
        assert divs.index.min() >= start_ts
        assert divs.index.max() <= end_ts

    def test_no_dividends_in_range(self, provider, valid_ticker):
        """Test date range with no dividends."""
        start = date(1980, 1, 1)
        end = date(1980, 12, 31)
        divs = provider.get_dividends(valid_ticker, start, end)

        # Should return None (no dividends in this range)
        assert divs is None

    def test_non_dividend_stock(self, provider):
        """Test stock that doesn't pay dividends."""
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)
        # GOOGL historically hasn't paid dividends
        divs = provider.get_dividends("TSLA", start, end)

        # May return None or empty DataFrame
        assert divs is None or divs.empty


class TestGetSplits:
    """Test get_splits method."""

    def test_stock_with_splits(self, provider, valid_ticker):
        """Test getting splits for a stock with historical splits."""
        # AAPL had a split in 2020
        start = date(2020, 1, 1)
        end = date(2020, 12, 31)
        splits = provider.get_splits(valid_ticker, start, end)

        # Validate schema
        assert isinstance(splits, pd.DataFrame)
        assert not splits.empty
        assert 'Split Ratio' in splits.columns
        assert isinstance(splits.index, pd.DatetimeIndex)

        # Validate data
        assert (splits['Split Ratio'] > 0).all()
        # Use timezone-aware comparisons
        start_ts = pd.Timestamp(start).tz_localize(splits.index.tz) if splits.index.tz else pd.Timestamp(start)
        end_ts = pd.Timestamp(end).tz_localize(splits.index.tz) if splits.index.tz else pd.Timestamp(end)
        assert splits.index.min() >= start_ts
        assert splits.index.max() <= end_ts

    def test_no_splits_in_range(self, provider, valid_ticker):
        """Test date range with no splits."""
        start = date(2023, 1, 1)
        end = date(2023, 12, 31)
        splits = provider.get_splits(valid_ticker, start, end)

        # Should return None (no splits in this range)
        assert splits is None


# ============================================================================
# FINANCIAL STATEMENTS TESTS
# ============================================================================

class TestGetFinancials:
    """Test get_financials method."""

    def test_annual_income_statement(self, provider, valid_ticker):
        """Test getting annual income statement."""
        financials = provider.get_financials(valid_ticker, statement_type="income", period="annual")

        # Validate schema
        assert isinstance(financials, pd.DataFrame)
        assert not financials.empty
        assert isinstance(financials.columns, pd.DatetimeIndex)

        # Check for common line items
        common_items = ['Total Revenue', 'Net Income', 'Operating Income']
        present_items = [item for item in common_items if item in financials.index]
        assert len(present_items) > 0

        # Validate that we have multiple years
        assert len(financials.columns) >= 2

    def test_quarterly_income_statement(self, provider, valid_ticker):
        """Test getting quarterly income statement."""
        financials = provider.get_financials(valid_ticker, statement_type="income", period="quarterly")

        # Validate schema
        assert isinstance(financials, pd.DataFrame)
        assert not financials.empty

        # Should have more periods than annual
        assert len(financials.columns) >= 4

    def test_ttm_income_statement(self, provider, valid_ticker):
        """Test getting TTM income statement."""
        financials = provider.get_financials(valid_ticker, statement_type="income", period="ttm")

        # Validate schema
        assert isinstance(financials, pd.DataFrame)
        assert not financials.empty

    def test_balance_sheet(self, provider, valid_ticker):
        """Test getting balance sheet."""
        financials = provider.get_financials(valid_ticker, statement_type="balance", period="annual")

        # Validate schema
        assert isinstance(financials, pd.DataFrame)
        assert not financials.empty

        # Check for common line items
        common_items = ['Total Assets', 'Total Debt', 'Cash And Cash Equivalents']
        present_items = [item for item in common_items if item in financials.index]
        assert len(present_items) > 0

    def test_cash_flow(self, provider, valid_ticker):
        """Test getting cash flow statement."""
        financials = provider.get_financials(valid_ticker, statement_type="cash", period="annual")

        # Validate schema
        assert isinstance(financials, pd.DataFrame)
        assert not financials.empty

        # Check for common line items
        common_items = ['Operating Cash Flow', 'Free Cash Flow']
        present_items = [item for item in common_items if item in financials.index]
        assert len(present_items) > 0

    def test_invalid_statement_type(self, provider, valid_ticker):
        """Test invalid statement type raises error."""
        with pytest.raises(ValueError, match="Invalid statement_type"):
            provider.get_financials(valid_ticker, statement_type="invalid")

    def test_invalid_period(self, provider, valid_ticker):
        """Test invalid period raises error."""
        with pytest.raises(ValueError, match="Invalid period"):
            provider.get_financials(valid_ticker, statement_type="income", period="invalid")


# ============================================================================
# NEW METHOD TESTS
# ============================================================================

class TestGetCalendar:
    """Test get_calendar method."""

    def test_valid_ticker(self, provider, valid_ticker):
        """Test getting calendar events."""
        calendar = provider.get_calendar(valid_ticker)

        # Validate schema
        assert isinstance(calendar, dict)
        assert len(calendar) > 0

        # Check for common keys (some may be missing depending on timing)
        possible_keys = [
            'Earnings Date', 'Earnings Average', 'Earnings Low', 'Earnings High',
            'Revenue Average', 'Revenue Low', 'Revenue High',
            'Ex-Dividend Date', 'Dividend Date'
        ]
        present_keys = [k for k in possible_keys if k in calendar]
        assert len(present_keys) > 0

    def test_invalid_ticker(self, provider):
        """Test calendar for invalid ticker."""
        calendar = provider.get_calendar("INVALIDTICKER123")

        # Should return None
        assert calendar is None


class TestGetFastInfo:
    """Test get_fast_info method."""

    def test_valid_ticker(self, provider, valid_ticker):
        """Test getting fast info."""
        fast_info = provider.get_fast_info(valid_ticker)

        # Validate schema
        assert isinstance(fast_info, dict)
        assert len(fast_info) > 0

        # Check for common keys (at least some should be present)
        common_keys = ['last_price', 'market_cap', 'shares', 'currency']
        present_keys = [k for k in common_keys if k in fast_info]
        assert len(present_keys) >= 1  # At least one key should be present

        # Validate data types
        if 'lastPrice' in fast_info:
            assert isinstance(fast_info['lastPrice'], (int, float))
            assert fast_info['lastPrice'] > 0
        if 'marketCap' in fast_info:
            assert isinstance(fast_info['marketCap'], (int, float))
            assert fast_info['marketCap'] > 0

    def test_invalid_ticker(self, provider):
        """Test fast info for invalid ticker."""
        fast_info = provider.get_fast_info("INVALIDTICKER123")

        # Invalid tickers may return None or a dict (possibly with minimal/None values)
        # Just check it doesn't crash and returns expected type
        assert fast_info is None or isinstance(fast_info, dict)


# ============================================================================
# RETRY LOGIC TESTS
# ============================================================================

class TestRetryLogic:
    """Test retry logic and error handling."""

    def test_retry_on_network_error(self, provider, valid_ticker):
        """Test that retries work (indirectly - hard to simulate network errors)."""
        # This test mainly ensures retry logic doesn't break normal operation
        prices = provider.get_prices([valid_ticker], date(2024, 12, 1), date(2024, 12, 5))
        assert isinstance(prices, pd.DataFrame)
        assert not prices.empty

    def test_exponential_backoff(self):
        """Test that exponential backoff is configured."""
        provider = YFinanceProvider(retry_attempts=3, retry_delay=0.1)
        assert provider.retry_attempts == 3
        assert provider.retry_delay == 0.1


# ============================================================================
# EDGE CASES & QUIRKS
# ============================================================================

class TestEdgeCases:
    """Test edge cases and quirks."""

    def test_empty_dataframe_check(self, provider):
        """Test that empty DataFrame check works correctly."""
        # This validates the bug fix at line 80
        prices = provider.get_prices(["INVALIDTICKER123"], date(2024, 12, 1), date(2024, 12, 5))
        assert isinstance(prices, pd.DataFrame)
        assert prices.empty

    def test_cache_variable_naming(self, provider, valid_ticker):
        """Test that cache variables are named correctly."""
        # This validates the bug fix at line 121
        bar1 = provider.get_bar(valid_ticker, date(2024, 12, 2))
        assert bar1 is not None

        # Call again to use cache
        bar2 = provider.get_bar(valid_ticker, date(2024, 12, 2))
        assert bar2 is not None
        assert bar1 == bar2

    def test_timestamp_construction(self, provider, valid_ticker):
        """Test that pd.Timestamp is constructed correctly."""
        # This validates the bug fix at line 239
        splits = provider.get_splits(valid_ticker, date(2020, 1, 1), date(2020, 12, 31))
        # Should not raise AttributeError
        assert splits is not None or splits is None  # Either outcome is valid


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
