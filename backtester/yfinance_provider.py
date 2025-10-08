"""
YFinance implementation of DataProvider.

Includes retry logic, caching, and proper handling of yfinance quirks.
"""

import yfinance as yf
import pandas as pd
import time
from typing import List, Dict, Optional
from datetime import date, timedelta
from backtester.dataprovider import DataProvider


class YFinanceProvider(DataProvider):
    """
    Market data provider using Yahoo Finance (yfinance).

    Features:
    - Automatic retry with exponential backoff for flaky API
    - Caching for performance
    - Proper handling of yfinance data format quirks
    - Point-in-time earnings data (no look-ahead bias)
    """

    def __init__(self, retry_attempts: int = 3, retry_delay: float = 1.0):
        """
        Initialize YFinance provider.

        Args:
            retry_attempts: Number of retry attempts for failed requests (default: 3)
            retry_delay: Base delay between retries in seconds (default: 1.0)
                        Uses exponential backoff: delay, delay*2, delay*4, etc.
        """
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay

        # Caches
        self._price_cache: Dict[str, pd.DataFrame] = {}
        self._ohlcv_cache: Dict[str, pd.DataFrame] = {}
        self._earnings_cache: Dict[str, pd.DataFrame] = {}

    def _fetch_with_retry(self, fetch_func, *args, **kwargs):
        """
        Generic retry wrapper for any fetch operation.

        Uses exponential backoff: delay, delay*2, delay*4, etc.
        Raises the last exception if all retries fail.
        """
        last_exception = None

        for attempt in range(self.retry_attempts):
            try:
                return fetch_func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.retry_attempts - 1:
                    sleep_time = self.retry_delay * (2 ** attempt)
                    time.sleep(sleep_time)
        raise last_exception

    # ==================== PRICE & VOLUME DATA ====================

    def get_prices(self, tickers: List[str], start: date, end: date) -> pd.DataFrame:
        """Get daily close prices with retry logic."""
        return self._fetch_with_retry(self._fetch_prices, tickers, start, end)

    def _fetch_prices(self, tickers: List[str], start: date, end: date) -> pd.DataFrame:
        """Actual yfinance fetch for prices."""
        if isinstance(tickers, str):
            tickers = [tickers]
        price_data = yf.download(
            tickers=tickers,
            start=start,
            end=end + timedelta(days=1),
            progress=False,
            auto_adjust=True
        )
        if price_data.empty:
            return pd.DataFrame()

        # Handle single vs multiple tickers (different structure)
        if len(tickers) == 1:
            # Single ticker: DataFrame has columns [Open, High, Low, Close, Volume, ...]
            if 'Close' in price_data.columns:
                # Create DataFrame with ticker as column name, preserving index
                result = pd.DataFrame(index=price_data.index)
                result[tickers[0]] = price_data['Close']
                return result
            else:
                # Fallback if structure is different
                result = pd.DataFrame(index=price_data.index)
                result[tickers[0]] = price_data.iloc[:, 3]  # Close is usually 4th column
                return result
        else:
            # Multiple tickers: MultiIndex columns
            return price_data['Close']

    def get_ohlcv(self, tickers: List[str], start: date, end: date) -> Dict[str, pd.DataFrame]:
        """Get OHLCV data with caching and retry."""
        return self._fetch_with_retry(self._fetch_ohlcv, tickers, start, end)

    def _fetch_ohlcv(self, tickers: List[str], start: date, end: date) -> Dict[str, pd.DataFrame]:
        """Actual yfinance fetch for OHLCV."""
        if isinstance(tickers, str):
            tickers = [tickers]
        result = {}
        for ticker in tickers:
            if ticker in self._ohlcv_cache:
                cached = self._ohlcv_cache[ticker]
                if start in cached.index and end in cached.index:
                    result[ticker] = cached.loc[start:end]
                    continue
            data = yf.download(
                ticker,
                start=start,
                end=end + timedelta(days=1),
                progress=False,
                auto_adjust=True
            )
            if not data.empty:
                # Flatten MultiIndex columns for single ticker
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
                self._ohlcv_cache[ticker] = data
                result[ticker] = data
        return result

    def get_bar(self, ticker: str, date: date) -> Optional[Dict[str, float]]:
        """Get single bar with retry."""
        return self._fetch_with_retry(self._fetch_bar, ticker, date)

    def _fetch_bar(self, ticker: str, date: date) -> Optional[Dict[str, float]]:
        """Actual yfinance fetch for single bar."""
        if ticker in self._ohlcv_cache:
            df = self._ohlcv_cache[ticker]
            if date in df.index:
                row = df.loc[date]
                # Handle both Series and scalar cases - use iloc[0] if Series
                if hasattr(row['Open'], 'iloc'):
                    return {
                        'open': float(row['Open'].iloc[0]),
                        'high': float(row['High'].iloc[0]),
                        'low': float(row['Low'].iloc[0]),
                        'close': float(row['Close'].iloc[0]),
                        'volume': float(row['Volume'].iloc[0])
                    }
                else:
                    return {
                        'open': float(row['Open']),
                        'high': float(row['High']),
                        'low': float(row['Low']),
                        'close': float(row['Close']),
                        'volume': float(row['Volume'])
                    }
        data = yf.download(
            ticker,
            start=date,
            end=date + timedelta(days=1),
            progress=False,
            auto_adjust=True
        )
        if data.empty:
            return None
        row = data.iloc[0]
        # Handle both Series and scalar cases
        if hasattr(row['Open'], 'iloc'):
            return {
                'open': float(row['Open'].iloc[0]),
                'high': float(row['High'].iloc[0]),
                'low': float(row['Low'].iloc[0]),
                'close': float(row['Close'].iloc[0]),
                'volume': float(row['Volume'].iloc[0])
            }
        else:
            return {
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': float(row['Volume'])
            }   

    # ==================== FUNDAMENTAL DATA ====================

    def get_earnings_data(self, ticker: str, as_of_date: date) -> Optional[Dict[str, any]]:
        """Get earnings data with retry."""
        return self._fetch_with_retry(self._fetch_earnings_data, ticker, as_of_date)

    def _fetch_earnings_data(self, ticker: str, as_of_date: date) -> Optional[Dict[str, any]]:
        """Actual yfinance fetch for earnings."""
        # Check cache first - earnings data is expensive to fetch
        if ticker in self._earnings_cache:
            earnings = self._earnings_cache[ticker]
        else:
            # Fetch and cache
            stock = yf.Ticker(ticker)
            earnings = stock.earnings_dates
            if earnings is not None and not earnings.empty:
                self._earnings_cache[ticker] = earnings
            else:
                return None

        if earnings is None or earnings.empty:
            return None

        # Convert to timezone-aware timestamp if needed
        as_of_datetime = pd.Timestamp(as_of_date)
        if earnings.index.tz is not None:
            as_of_datetime = as_of_datetime.tz_localize(earnings.index.tz)

        past_earnings = earnings[earnings.index < as_of_datetime]
        if past_earnings.empty:
            return None
        
        past_earnings = past_earnings.sort_index(ascending=False)
        most_recent = past_earnings.iloc[0]
        days_ago = (as_of_datetime - most_recent.name).days
        if days_ago > 90:
            return None
        reported = most_recent.get('Reported EPS')
        estimate = most_recent.get('EPS Estimate')
        if pd.isna(reported) or pd.isna(estimate):
            return None
        if estimate >= 0:
            surprise = (reported - estimate) / estimate
        else:
            surprise = -((reported - estimate) / abs(estimate))
        return {
        "reported_eps": reported,
        "estimated_eps": estimate,
        "earnings_date": most_recent.name,
        "surprise_pct": surprise
        }

    def get_info(self, ticker: str) -> Optional[Dict[str, any]]:
        """Get company info with retry."""
        return self._fetch_with_retry(self._fetch_info, ticker)

    def _fetch_info(self, ticker: str) -> Optional[Dict[str, any]]:
        """Actual yfinance fetch for company info."""
        stock = yf.Ticker(ticker)
        info = stock.info
        if not info:
            return None
        return info

    def get_institutional_holders(self, ticker: str) -> Optional[pd.DataFrame]:
        """Get institutional holders with retry."""
        return self._fetch_with_retry(self._fetch_institutional_holders, ticker)

    def _fetch_institutional_holders(self, ticker: str) -> Optional[pd.DataFrame]:
        """Actual yfinance fetch for institutional holders."""
        stock = yf.Ticker(ticker)
        holders = stock.institutional_holders
        if holders is None or holders.empty:
            return None
        return holders

    # ==================== CORPORATE ACTIONS ====================

    def get_dividends(self, ticker: str, start: date, end: date) -> Optional[pd.DataFrame]:
        """Get dividends with retry."""
        return self._fetch_with_retry(self._fetch_dividends, ticker, start, end)

    def _fetch_dividends(self, ticker: str, start: date, end: date) -> Optional[pd.DataFrame]:
        """Actual yfinance fetch for dividends."""
        stock = yf.Ticker(ticker)
        divs = stock.dividends
        if divs is None or divs.empty:
            return None
        # Convert dates to timezone-aware timestamps matching the index
        start_ts = pd.Timestamp(start).tz_localize(divs.index.tz) if divs.index.tz else pd.Timestamp(start)
        end_ts = pd.Timestamp(end).tz_localize(divs.index.tz) if divs.index.tz else pd.Timestamp(end)
        divs = divs[(divs.index >= start_ts) & (divs.index <= end_ts)]
        if divs.empty:
            return None
        return divs.to_frame(name='Dividend')

    def get_splits(self, ticker: str, start: date, end: date) -> Optional[pd.DataFrame]:
        """Get splits with retry."""
        return self._fetch_with_retry(self._fetch_splits, ticker, start, end)

    def _fetch_splits(self, ticker: str, start: date, end: date) -> Optional[pd.DataFrame]:
        """Actual yfinance fetch for splits."""
        stock = yf.Ticker(ticker)
        splits = stock.splits
        if splits is None or splits.empty:
            return None
        # Convert dates to timezone-aware timestamps matching the index
        start_ts = pd.Timestamp(start).tz_localize(splits.index.tz) if splits.index.tz else pd.Timestamp(start)
        end_ts = pd.Timestamp(end).tz_localize(splits.index.tz) if splits.index.tz else pd.Timestamp(end)
        splits = splits[(splits.index >= start_ts) & (splits.index <= end_ts)]
        if splits.empty:
            return None
        return splits.to_frame(name='Split Ratio')

    def get_financials(self, ticker: str, statement_type: str = "income", period: str = "annual") -> Optional[pd.DataFrame]:
        """Get financials with retry."""
        return self._fetch_with_retry(self._fetch_financials, ticker, statement_type, period)

    def _fetch_financials(self, ticker: str, statement_type: str, period: str) -> Optional[pd.DataFrame]:
        """Actual yfinance fetch for financials."""
        stock = yf.Ticker(ticker)

        # Map statement type and period to yfinance attributes
        if statement_type == "income":
            if period == "annual":
                financials = stock.financials
            elif period == "quarterly":
                financials = stock.quarterly_financials
            elif period == "ttm":
                financials = stock.income_stmt  # TTM version
            else:
                raise ValueError(f"Invalid period: {period}. Must be 'annual', 'quarterly', or 'ttm'")
        elif statement_type == "balance":
            if period == "annual":
                financials = stock.balance_sheet
            elif period == "quarterly":
                financials = stock.quarterly_balance_sheet
            elif period == "ttm":
                # No TTM for balance sheet, use most recent annual
                financials = stock.balance_sheet
            else:
                raise ValueError(f"Invalid period: {period}. Must be 'annual', 'quarterly', or 'ttm'")
        elif statement_type == "cash":
            if period == "annual":
                financials = stock.cashflow
            elif period == "quarterly":
                financials = stock.quarterly_cashflow
            elif period == "ttm":
                financials = stock.cash_flow  # TTM version
            else:
                raise ValueError(f"Invalid period: {period}. Must be 'annual', 'quarterly', or 'ttm'")
        else:
            raise ValueError(f"Invalid statement_type: {statement_type}. Must be 'income', 'balance', or 'cash'")

        if financials is None or financials.empty:
            return None

        return financials

    def get_calendar(self, ticker: str) -> Optional[Dict[str, any]]:
        """Get calendar events with retry."""
        return self._fetch_with_retry(self._fetch_calendar, ticker)

    def _fetch_calendar(self, ticker: str) -> Optional[Dict[str, any]]:
        """Actual yfinance fetch for calendar events."""
        stock = yf.Ticker(ticker)
        calendar = stock.calendar
        if calendar is None:
            return None
        if isinstance(calendar, pd.DataFrame) and calendar.empty:
            return None
        if isinstance(calendar, dict) and len(calendar) == 0:
            return None
        return calendar

    def get_fast_info(self, ticker: str) -> Optional[Dict[str, any]]:
        """Get fast info with retry."""
        return self._fetch_with_retry(self._fetch_fast_info, ticker)

    def _fetch_fast_info(self, ticker: str) -> Optional[Dict[str, any]]:
        """Actual yfinance fetch for fast info."""
        stock = yf.Ticker(ticker)
        try:
            fast_info = stock.fast_info
            if fast_info is None:
                return None

            # Extract public attributes from the fast_info object
            result = {}
            for attr in dir(fast_info):
                if not attr.startswith('_'):
                    try:
                        value = getattr(fast_info, attr)
                        # Skip methods
                        if not callable(value):
                            result[attr] = value
                    except:
                        pass

            if len(result) == 0:
                return None
            return result
        except Exception:
            return None

