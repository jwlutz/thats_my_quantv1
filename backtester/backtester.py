from datetime import date, timedelta
from typing import List, Dict, Optional
import logging
import pandas as pd
from backtester.portfolio import Portfolio
from backtester.strategy import Strategy
from backtester.dataprovider import DataProvider
from backtester.transactioncost import TransactionCost


class Backtester:
    """
    Main backtesting engine.

    Simulates trading strategy over historical data with realistic
    constraints and transaction costs.

    Key features:
    - Day-by-day simulation (time-driven)
    - Exit-before-entry processing (risk management first)
    - Respects max_positions and cash constraints
    - Tracks equity curve daily
    - Preloads price data for performance

    Example:
        >>> from backtester.backtester import Backtester
        >>> from backtester.strategy import Strategy
        >>> from backtester.yfinance_provider import YFinanceProvider
        >>>
        >>> bt = Backtester(
        ...     strategy=my_strategy,
        ...     data_provider=YFinanceProvider(),
        ...     initial_capital=100000,
        ...     start_date=date(2020, 1, 1),
        ...     end_date=date(2023, 12, 31),
        ...     commission=1.0,
        ...     slippage=0.001,
        ...     max_positions=10
        ... )
        >>>
        >>> results = bt.run()
        >>> results.print_summary()
    """

    def __init__(self,
                 strategy: Strategy,
                 data_provider: DataProvider,
                 initial_capital: float,
                 start_date: date,
                 end_date: date,
                 commission: float = 0.0,
                 slippage: float = 0.0,
                 max_positions: int = 10,
                 fractional_shares: bool = True):
        """
        Initialize backtester.

        Args:
            strategy: Strategy instance to backtest
            data_provider: DataProvider for market data (ABC, not implementation-specific!)
            initial_capital: Starting cash
            start_date: Backtest start date
            end_date: Backtest end date (inclusive)
            commission: Flat commission per trade ($)
            slippage: Slippage as decimal (0.001 = 0.1%)
            max_positions: Max concurrent positions
            fractional_shares: Allow fractional share quantities

        Raises:
            ValueError: If parameters invalid
        """
        # Validation
        if initial_capital <= 0:
            raise ValueError(f"initial_capital must be positive, got {initial_capital}")
        if start_date >= end_date:
            raise ValueError(f"start_date must be before end_date")
        if max_positions <= 0:
            raise ValueError(f"max_positions must be positive, got {max_positions}")

        self.strategy = strategy
        self.data_provider = data_provider
        self.initial_capital = initial_capital
        self.start_date = start_date
        self.end_date = end_date

        # Create transaction cost calculator
        self.transaction_cost = TransactionCost(
            commission=commission,
            slippage_pct=slippage
        )

        # Create portfolio
        self.portfolio = Portfolio(
            starting_capital=initial_capital,
            max_positions=max_positions,
            transaction_cost=self.transaction_cost,
            fractional_shares=fractional_shares
        )

        # Validate strategy before running
        self.strategy.validate()

        # Set up logging
        self.logger = logging.getLogger(__name__)

        # Will be populated by run()
        self.price_data: Optional[pd.DataFrame] = None
        self.trading_days: Optional[List[date]] = None

    def run(self) -> 'Results':
        """
        Run backtest simulation.

        Process:
        1. Preload price data for universe
        2. Get trading days calendar
        3. For each day:
           a. Process exits (FIRST!)
           b. Generate entry signals
           c. Process entries
           d. Record equity
        4. Close all positions at end
        5. Build Results object

        Returns:
            Results: Performance metrics and analysis

        Example:
            >>> results = backtester.run()
            >>> print(f"Total Return: {results.total_return:.2%}")
        """
        # Step 1: Preload price data
        self._preload_data()

        # Step 2: Get trading days
        self._get_trading_days()

        # Step 3: Main simulation loop
        for current_date in self.trading_days:
            self._process_day(current_date)

        # Step 4: Close all remaining positions at end
        self._close_all_positions(self.end_date)

        # Step 5: Build and return results
        from backtester.results import Results
        return Results(
            portfolio=self.portfolio,
            strategy=self.strategy,
            start_date=self.start_date,
            end_date=self.end_date,
            initial_capital=self.initial_capital
        )

    def _preload_data(self):
        """
        Preload price data for entire universe.

        Also preloads OHLCV and earnings data into provider's cache for performance.
        This is much faster than querying day-by-day and avoids rate limits.
        For V1 with reasonable universes (<500 tickers), RAM usage is fine.

        Sets:
            self.price_data: DataFrame with index=dates, columns=tickers
        """
        self.logger.info(f"Preloading data for {len(self.strategy.universe)} tickers...")

        # Preload OHLCV into data provider's cache
        # This makes subsequent get_bar() calls instant
        self.data_provider.get_ohlcv(
            tickers=self.strategy.universe,
            start=self.start_date,
            end=self.end_date
        )

        # Preload earnings data into cache (very slow API call, so preload once)
        # Call get_earnings_data() once per ticker to populate cache
        for ticker in self.strategy.universe:
            try:
                self.data_provider.get_earnings_data(ticker, self.end_date)
            except Exception as e:
                self.logger.debug(f"Could not preload earnings for {ticker}: {e}")

        # Also get close prices for convenience (used in multiple places)
        self.price_data = self.data_provider.get_prices(
            tickers=self.strategy.universe,
            start=self.start_date,
            end=self.end_date
        )

        if self.price_data is None or self.price_data.empty:
            raise ValueError("No price data available for universe")

        self.logger.info(f"Loaded {len(self.price_data)} days of data")

    def _get_trading_days(self):
        """
        Get list of trading days for backtest period.

        Uses SPY as market calendar (standard approach).
        Only processes days when market was open.

        Sets:
            self.trading_days: List of dates
        """
        # Use price_data index as trading calendar
        # (already filtered to valid trading days by data provider)
        self.trading_days = self.price_data.index.tolist()

        if not self.trading_days:
            raise ValueError("No trading days found in date range")

        self.logger.info(f"Backtesting {len(self.trading_days)} trading days")

    def _process_day(self, current_date: date):
        """
        Process single trading day.

        CRITICAL ORDER OF OPERATIONS:
        1. Process exits FIRST (risk management priority!)
        2. Generate entry signals
        3. Process entries
        4. Record equity

        Args:
            current_date: Current date to process
        """
        self.logger.debug(f"Processing {current_date}")

        # Get current prices for universe
        current_prices = self._get_current_prices(current_date)

        self.logger.debug(
            f"  Open positions: {len(self.portfolio.open_roundtrips)}, "
            f"Cash: ${self.portfolio.cash:,.2f}"
        )

        # STEP 1: EXITS FIRST (risk management priority)
        self._process_exits(current_date, current_prices)

        # STEP 2: Generate entry signals
        signals = self.strategy.generate_signals(
            current_date=current_date,
            data_provider=self.data_provider,
            portfolio=self.portfolio
        )

        if signals:
            self.logger.debug(f"  Generated {len(signals)} signals")

        # STEP 3: Process entries
        self._process_entries(current_date, current_prices, signals)

        # STEP 4: Record equity
        portfolio_value = self._calculate_portfolio_value(current_date, current_prices)
        self.portfolio.record_equity(current_date, portfolio_value)

    def _get_current_prices(self, current_date: date) -> Dict[str, float]:
        """
        Get current prices for all tickers.

        Safe lookup - handles missing data gracefully.

        Args:
            current_date: Current date

        Returns:
            Dict[str, float]: {ticker: price} for tickers with valid data
        """
        current_prices = {}

        # Check if date exists in price data
        if current_date not in self.price_data.index:
            return current_prices

        # Get prices for this date
        day_prices = self.price_data.loc[current_date]

        # Build dict, filtering out NaN/missing values
        for ticker in self.strategy.universe:
            if ticker in day_prices.index:
                price = day_prices[ticker]
                # Only include if valid price
                if pd.notna(price) and price > 0:
                    current_prices[ticker] = float(price)

        # Also add prices for any open positions not in universe
        # (in case a ticker was removed from universe but we still hold it)
        for rt_id, roundtrip in self.portfolio.open_roundtrips.items():
            ticker = roundtrip.ticker
            if ticker not in current_prices and ticker in day_prices.index:
                price = day_prices[ticker]
                if pd.notna(price) and price > 0:
                    current_prices[ticker] = float(price)

        return current_prices

    def _process_exits(self, current_date: date, current_prices: Dict[str, float]):
        """
        Check all open positions for exit signals.

        Processes exits BEFORE entries to free up capital and position slots.

        Args:
            current_date: Current date
            current_prices: Dict of {ticker: price}
        """
        # Collect positions to exit (can't modify dict during iteration)
        positions_to_exit = []

        for rt_id, roundtrip in list(self.portfolio.open_roundtrips.items()):
            ticker = roundtrip.ticker

            # Skip if no price data (delisted/suspended)
            if ticker not in current_prices:
                self.logger.warning(
                    f"{ticker} has no price data on {current_date} "
                    f"(likely delisted). Position value marked as $0."
                )
                continue

            current_price = current_prices[ticker]

            # Check exit rule
            should_exit, exit_portion, reason = roundtrip.exit_rule.should_exit(
                roundtrip=roundtrip,
                date=current_date,
                price=current_price
            )

            if should_exit:
                positions_to_exit.append((rt_id, exit_portion, current_price, reason))

        # Execute exits
        for rt_id, portion, price, reason in positions_to_exit:
            roundtrip = self.portfolio.open_roundtrips[rt_id]
            shares_to_exit = roundtrip.remaining_shares * portion

            # Full exit vs partial exit
            if portion >= 0.9999:  # Avoid floating point issues
                self.portfolio.close_position(rt_id, current_date, price, reason)
                self.logger.debug(f"  Closed {roundtrip.ticker} (reason: {reason})")
            else:
                self.portfolio.reduce_position(rt_id, current_date, price, shares_to_exit, reason)
                self.logger.debug(f"  Reduced {roundtrip.ticker} by {portion:.1%} (reason: {reason})")

    def _process_entries(self,
                        current_date: date,
                        current_prices: Dict[str, float],
                        signals: List):
        """
        Process entry signals in priority order.

        Opens positions until capital exhausted or max_positions reached.

        CRITICAL: Use CURRENT cash, not starting cash!

        Args:
            current_date: Current date
            current_prices: Dict of {ticker: price}
            signals: List of Signal objects (already sorted by priority)
        """
        # Filter signals - only process tickers with valid price data
        valid_signals = [s for s in signals if s.ticker in current_prices]

        # Process signals in priority order
        for signal in valid_signals:
            # Check if we can open more positions
            if not self.portfolio.can_open_position():
                break  # Max positions reached

            ticker = signal.ticker
            current_price = current_prices[ticker]

            # Calculate portfolio value ONCE (not per signal - expensive!)
            # But use CURRENT cash (decreases as we open positions)
            portfolio_value = self._calculate_portfolio_value(current_date, current_prices)

            # Calculate position size
            shares = self.strategy.position_sizer.calculate_shares(
                price=current_price,
                available_cash=self.portfolio.cash,  # CURRENT cash!
                portfolio_value=portfolio_value,
                portfolio=self.portfolio,
                ticker=ticker
            )

            # Skip if insufficient capital
            if shares <= 0:
                continue

            # Determine exit rule: signal override or strategy default
            exit_rule = signal.metadata.get('exit_rule', self.strategy.exit_rules)

            # Attempt to open position
            roundtrip = self.portfolio.open_position(
                ticker=ticker,
                date=current_date,
                price=current_price,
                shares=shares,
                exit_rule=exit_rule,
                signal_metadata=signal.metadata
            )

            # If open_position returned None, insufficient cash or other issue
            # Continue to next signal (maybe we can afford a cheaper stock)
            if roundtrip is None:
                self.logger.debug(f"  Failed to open {ticker} (insufficient cash)")
                continue

            # Successfully opened position!
            self.logger.debug(f"  Opened {ticker}: {shares:.2f} shares @ ${current_price:.2f}")
            # portfolio.cash has been automatically decremented

    def _calculate_portfolio_value(self,
                                   current_date: date,
                                   current_prices: Dict[str, float]) -> float:
        """
        Calculate total portfolio value.

        Args:
            current_date: Current date
            current_prices: Dict of {ticker: price}

        Returns:
            float: Cash + market value of positions
        """
        total_value = self.portfolio.cash

        # Add value of open positions
        for roundtrip in self.portfolio.open_roundtrips.values():
            ticker = roundtrip.ticker
            # Use current price if available, otherwise position has no value
            # (delisted, suspended, etc.)
            if ticker in current_prices:
                position_value = roundtrip.remaining_shares * current_prices[ticker]
                total_value += position_value

        return total_value

    def _close_all_positions(self, final_date: date):
        """
        Close all remaining open positions at backtest end.

        Uses final closing prices. If no price available, position is
        considered worthless (delisted, etc.).

        Args:
            final_date: Final date of backtest
        """
        # Get final prices
        final_prices = self._get_current_prices(final_date)

        # Close all open positions
        for rt_id, roundtrip in list(self.portfolio.open_roundtrips.items()):
            ticker = roundtrip.ticker

            # Get final price
            if ticker in final_prices:
                final_price = final_prices[ticker]
                self.portfolio.close_position(
                    roundtrip_id=rt_id,
                    date=final_date,
                    price=final_price,
                    reason='backtest_end'
                )
                self.logger.debug(f"Closed {ticker} at backtest end")
            else:
                # No price data - position is worthless (delisted)
                self.logger.warning(
                    f"{ticker} has no price data at backtest end "
                    f"(likely delisted). Position left open with $0 value."
                )
                # Leave position open - will show in Results as unrealized loss

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (f"Backtester(strategy='{self.strategy.name}', "
                f"capital=${self.initial_capital:,.0f}, "
                f"{self.start_date} to {self.end_date})")