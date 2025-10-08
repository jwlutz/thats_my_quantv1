"""
Abstract DataProvider interface for market data.

Supports pluggable data sources (yfinance, Alpaca, custom providers, etc.)
without changing backtester logic.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import date
import pandas as pd


class DataProvider(ABC):
    """
    Abstract interface for market data providers.

    Implementations must provide methods to fetch:
    - Price/volume data (OHLCV)
    - Fundamental data (earnings, financials, company info)
    - Corporate actions (splits, dividends)
    - Ownership data (institutional holders)

    This abstraction allows the backtester to work with any data source.
    """

    # ==================== PRICE & VOLUME DATA ====================

    @abstractmethod
    def get_prices(self, tickers: List[str], start: date, end: date) -> pd.DataFrame:
        """
        Get daily close prices for multiple tickers.

        Args:
            tickers: List of ticker symbols (e.g., ["AAPL", "MSFT", "GOOGL"])
            start: Start date (inclusive)
            end: End date (inclusive)

        Returns:
            pd.DataFrame with schema:
                - Index: pd.DatetimeIndex (dates in range)
                - Columns: List[str] (ticker symbols)
                - Values: float (close prices)

            Example:
                            AAPL    MSFT    GOOGL
                2024-01-02  185.58  376.04  140.93
                2024-01-03  182.67  370.73  139.69

            Returns empty DataFrame if no data available.
        """
        pass

    @abstractmethod
    def get_ohlcv(self, tickers: List[str], start: date, end: date) -> Dict[str, pd.DataFrame]:
        """
        Get OHLCV data for multiple tickers.

        Args:
            tickers: List of ticker symbols (e.g., ["AAPL", "MSFT"])
            start: Start date (inclusive)
            end: End date (inclusive)

        Returns:
            Dict[str, pd.DataFrame] with schema:
                - Keys: str (ticker symbols)
                - Values: pd.DataFrame per ticker with:
                    * Index: pd.DatetimeIndex (dates in range)
                    * Columns: ['Open', 'High', 'Low', 'Close', 'Volume']
                    * Values: float (prices) or int (volume)

            Example:
                {
                    'AAPL': DataFrame with columns [Open, High, Low, Close, Volume],
                    'MSFT': DataFrame with columns [Open, High, Low, Close, Volume]
                }

                Per ticker DataFrame:
                                Open     High      Low    Close      Volume
                2024-01-02  185.58   186.86   184.35   185.58   82488600
                2024-01-03  182.67   184.32   182.38   182.67   58414500

            Missing tickers are excluded from result.
        """
        pass

    @abstractmethod
    def get_bar(self, ticker: str, date: date) -> Optional[Dict[str, float]]:
        """
        Get single day's OHLCV for one ticker.

        Args:
            ticker: Ticker symbol (e.g., "AAPL")
            date: Date to fetch (e.g., date(2024, 1, 2))

        Returns:
            Dict[str, float] with schema:
                {
                    'open': float,      # Opening price
                    'high': float,      # High price
                    'low': float,       # Low price
                    'close': float,     # Close price
                    'volume': float     # Volume (int or float depending on source)
                }

            Example:
                {
                    'open': 185.58,
                    'high': 186.86,
                    'low': 184.35,
                    'close': 185.58,
                    'volume': 82488600.0
                }

            Returns None if no data available for this date (market closed, invalid ticker, etc.)
        """
        pass

    # ==================== FUNDAMENTAL DATA ====================

    @abstractmethod
    def get_earnings_data(self, ticker: str, as_of_date: date) -> Optional[Dict[str, any]]:
        """
        Get most recent earnings data as of a specific date (point-in-time accurate).

        Args:
            ticker: Ticker symbol (e.g., "AAPL")
            as_of_date: Date to check earnings as of (for point-in-time accuracy, no look-ahead bias)

        Returns:
            Dict[str, Any] with schema:
                {
                    'reported_eps': float,          # Actual reported EPS
                    'estimated_eps': float,         # Analyst consensus estimate
                    'earnings_date': pd.Timestamp,  # Date earnings were reported
                    'surprise_pct': float           # (reported - estimated) / |estimated|
                }

            Example:
                {
                    'reported_eps': 2.18,
                    'estimated_eps': 2.10,
                    'earnings_date': Timestamp('2024-02-01 16:00:00-05:00'),
                    'surprise_pct': 0.038  # 3.8% beat
                }

            Returns None if:
                - No earnings found before as_of_date
                - Most recent earnings > 90 days old
                - Missing required fields (reported_eps or estimated_eps)
        """
        pass

    @abstractmethod
    def get_info(self, ticker: str) -> Optional[Dict[str, any]]:
        """
        Get company fundamental information and metrics.

        Args:
            ticker: Ticker symbol (e.g., "AAPL")

        Returns:
            Dict[str, Any] with common keys (availability varies by data source):

            Valuation metrics:
                - marketCap: int (market capitalization in dollars)
                - trailingPE: float (trailing P/E ratio)
                - forwardPE: float (forward P/E ratio)
                - priceToBook: float (price to book ratio)
                - enterpriseValue: int (enterprise value)

            Profitability metrics:
                - profitMargins: float (net profit margin, 0.24 = 24%)
                - returnOnEquity: float (ROE, 1.5 = 150%)
                - returnOnAssets: float (ROA, 0.25 = 25%)

            Growth metrics:
                - revenueGrowth: float (YoY revenue growth, 0.096 = 9.6%)
                - earningsGrowth: float (YoY earnings growth)

            Dividends:
                - dividendYield: float (dividend yield, 0.004 = 0.4%)
                - dividendRate: float (annual dividend per share)

            Trading:
                - beta: float (volatility vs market)
                - volume: int (current volume)
                - averageVolume: int (average daily volume)

            Company info:
                - sector: str (e.g., "Technology")
                - industry: str (e.g., "Consumer Electronics")
                - fullTimeEmployees: int

            Example (subset):
                {
                    'marketCap': 3829117222912,
                    'trailingPE': 39.21,
                    'forwardPE': 31.05,
                    'profitMargins': 0.243,
                    'sector': 'Technology',
                    'industry': 'Consumer Electronics',
                    'beta': 1.094
                }

            Returns None if ticker not found or no data available.
        """
        pass

    @abstractmethod
    def get_institutional_holders(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        Get institutional ownership data (top holders).

        Args:
            ticker: Ticker symbol (e.g., "AAPL")

        Returns:
            pd.DataFrame with schema:
                - Index: int (0 to N-1, typically top 10 holders)
                - Columns:
                    * 'Holder': str (institution name)
                    * 'Shares': int (number of shares held)
                    * 'Date Reported': str or Timestamp (reporting date)
                    * 'pctHeld': float (percentage of shares, 0.0108 = 1.08%)
                    * 'Value': int (dollar value of holdings)
                    * 'pctChange': float (change from prior period, 0.0076 = 0.76% increase)

            Example:
                   Date Reported                    Holder  pctHeld        Shares         Value  pctChange
                0     2025-06-30        Vanguard Group Inc   0.0108  1415245000  365338966532     0.0108
                1     2025-06-30            Blackrock Inc.   0.0076  1148562000  296423423578     0.0076
                2     2025-06-30  State Street Corporation   0.0088   601234000  155134517104     0.0088

            Returns None if no institutional holder data available.
        """
        pass

    # ==================== CORPORATE ACTIONS ====================

    @abstractmethod
    def get_dividends(self, ticker: str, start: date, end: date) -> Optional[pd.DataFrame]:
        """
        Get dividend payment history within date range.

        Args:
            ticker: Ticker symbol (e.g., "AAPL")
            start: Start date (inclusive)
            end: End date (inclusive)

        Returns:
            pd.DataFrame with schema:
                - Index: pd.DatetimeIndex (ex-dividend dates)
                - Columns: ['Dividend']
                - Values: float (dividend amount per share)

            Example:
                                Dividend
                2024-02-09          0.24
                2024-05-10          0.25
                2024-08-12          0.25

            Returns None if no dividends paid in date range.
        """
        pass

    @abstractmethod
    def get_splits(self, ticker: str, start: date, end: date) -> Optional[pd.DataFrame]:
        """
        Get stock split history within date range.

        Args:
            ticker: Ticker symbol (e.g., "AAPL")
            start: Start date (inclusive)
            end: End date (inclusive)

        Returns:
            pd.DataFrame with schema:
                - Index: pd.DatetimeIndex (split effective dates)
                - Columns: ['Split Ratio']
                - Values: float (split ratio, e.g., 2.0 = 2-for-1 split, 7.0 = 7-for-1)

            Example:
                                Split Ratio
                2014-06-09              7.0
                2020-08-31              4.0

            Returns None if no splits in date range.
        """
        pass

    @abstractmethod
    def get_financials(self, ticker: str, statement_type: str = "income", period: str = "annual") -> Optional[pd.DataFrame]:
        """
        Get financial statement data (income statement, balance sheet, or cash flow).

        Args:
            ticker: Ticker symbol (e.g., "AAPL")
            statement_type: Type of financial statement
                - "income": Income statement (revenue, expenses, net income)
                - "balance": Balance sheet (assets, liabilities, equity)
                - "cash": Cash flow statement (operating, investing, financing)
            period: Reporting period
                - "annual": Annual statements (default)
                - "quarterly": Quarterly statements
                - "ttm": Trailing twelve months

        Returns:
            pd.DataFrame with schema:
                - Index: str (line item names)
                - Columns: pd.DatetimeIndex (reporting period dates, most recent first)
                - Values: int or float (dollar amounts, typically in native currency)

            Example (income statement, subset):
                                                    2024-09-30    2023-09-30    2022-09-30
                Total Revenue                    391035000000  383285000000  394328000000
                Cost Of Revenue                  210352000000  214137000000  223546000000
                Gross Profit                     180683000000  169148000000  170782000000
                Operating Income                 123216000000  114301000000  119437000000
                Net Income                        93736000000   96995000000   99803000000

            Returns None if no financial data available for this ticker/statement type.
        """
        pass

    @abstractmethod
    def get_calendar(self, ticker: str) -> Optional[Dict[str, any]]:
        """
        Get upcoming calendar events (earnings, dividends, etc.).

        Args:
            ticker: Ticker symbol (e.g., "AAPL")

        Returns:
            Dict[str, Any] with schema:
                {
                    'Earnings Date': list[date] or date,  # Upcoming earnings date(s)
                    'Ex-Dividend Date': date,             # Next ex-dividend date
                    'Dividend Date': date,                # Next dividend payment date
                    'Earnings Average': float,            # Consensus EPS estimate
                    'Earnings Low': float,                # Low EPS estimate
                    'Earnings High': float,               # High EPS estimate
                    'Revenue Average': int,               # Consensus revenue estimate
                    'Revenue Low': int,                   # Low revenue estimate
                    'Revenue High': int                   # High revenue estimate
                }

            Example:
                {
                    'Dividend Date': datetime.date(2025, 8, 13),
                    'Ex-Dividend Date': datetime.date(2025, 8, 10),
                    'Earnings Date': [datetime.date(2025, 10, 30)],
                    'Earnings High': 1.83,
                    'Earnings Low': 1.63,
                    'Earnings Average': 1.76216,
                    'Revenue High': 103220000000,
                    'Revenue Low': 97854000000,
                    'Revenue Average': 101719746060
                }

            Returns None if no calendar data available.
        """
        pass

    @abstractmethod
    def get_fast_info(self, ticker: str) -> Optional[Dict[str, any]]:
        """
        Get quick access to commonly used fundamental metrics (faster than get_info).

        Args:
            ticker: Ticker symbol (e.g., "AAPL")

        Returns:
            Dict[str, Any] with schema (subset of most critical metrics):
                {
                    'lastPrice': float,              # Most recent close price
                    'lastVolume': int,               # Most recent volume
                    'marketCap': int,                # Market capitalization
                    'shares': int,                   # Shares outstanding
                    'floatShares': int,              # Float shares
                    'yearHigh': float,               # 52-week high
                    'yearLow': float,                # 52-week low
                    'currency': str,                 # Trading currency
                    'exchange': str                  # Exchange (e.g., "NMS")
                }

            Example:
                {
                    'lastPrice': 258.02,
                    'lastVolume': 49155614,
                    'marketCap': 3829117222912,
                    'shares': 14840390000,
                    'yearHigh': 260.1,
                    'yearLow': 169.21,
                    'currency': 'USD',
                    'exchange': 'NMS'
                }

            Returns None if ticker not found.
            Note: This is significantly faster than get_info() for quick checks.
        """
        pass

    # ==================== UTILITY METHODS ====================

    def is_tradeable(self, ticker: str, date: date) -> bool:
        """
        Check if ticker has valid price data on a given date.

        Default implementation checks if get_bar returns data.
        Can be overridden by subclasses for more efficient checks.

        Args:
            ticker: Ticker symbol
            date: Date to check

        Returns:
            True if ticker traded on this date, False otherwise
        """
        bar = self.get_bar(ticker, date)
        return bar is not None
