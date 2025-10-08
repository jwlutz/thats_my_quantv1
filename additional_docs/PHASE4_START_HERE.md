# Phase 4 Implementation Guide: Backtester Engine & Results

## 📍 Where You Left Off

**✅ Phase 3 Complete**: Exit Rules System (57/57 tests, 100%)
**Total Progress**: 60% Complete (336/336 tests passing)

**Phase 4 Components to Build** (SPEC lines 1096-1638):
1. PositionSizer - Calculate share quantities for entries
2. Strategy - Bundle entry rules + exit rules + universe
3. Backtester - Main simulation engine
4. Results - Performance metrics and visualization

---

## 🎯 Phase 4 Overview

**Goal**: Wire all components together into a complete backtesting engine that:
- Processes market data day by day (time series simulation)
- Evaluates exit conditions first (risk management priority)
- Generates entry signals from rules
- Sizes positions appropriately
- Tracks performance metrics
- Produces actionable results

**Estimated Time**: 10-12 hours
**Test Target**: 60+ new tests (total: ~400 tests)

---

## 1️⃣ PositionSizer Class (SPEC lines 1096-1162)

### Purpose
Calculate how many shares to buy when opening/adding to positions.

### Location
**File**: `backtester/positionsizer.py` (~100 lines)
**Tests**: `tests/test_positionsizer.py` (~300 lines, 20+ tests)

### Implementation

```python
from abc import ABC, abstractmethod
from typing import Optional

class PositionSizer(ABC):
    """
    Base class for position sizing algorithms.

    Determines share quantity based on available capital, risk parameters,
    and portfolio constraints.
    """

    @abstractmethod
    def calculate_shares(self,
                        price: float,
                        available_capital: float,
                        portfolio_value: float,
                        portfolio=None,
                        ticker: str = None) -> float:
        """
        Calculate shares to purchase.

        Args:
            price: Current price per share
            available_capital: Cash available for trading
            portfolio_value: Total portfolio value (cash + positions)
            portfolio: Optional Portfolio instance for position-aware sizing
            ticker: Optional ticker for position-specific rules

        Returns:
            float: Number of shares (fractional allowed)
        """
        pass

    @abstractmethod
    def to_dict(self) -> dict:
        """Serialize for config."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> 'PositionSizer':
        """Deserialize from config."""
        pass


class FixedDollarAmount(PositionSizer):
    """
    Allocate fixed dollar amount per position.

    Example: $5000 per position
    - At $100/share → 50 shares
    - At $250/share → 20 shares
    """

    def __init__(self, dollar_amount: float):
        if dollar_amount <= 0:
            raise ValueError("dollar_amount must be positive")
        self.dollar_amount = dollar_amount

    def calculate_shares(self, price, available_capital, portfolio_value,
                        portfolio=None, ticker=None):
        if price <= 0:
            raise ValueError("price must be positive")

        # Don't exceed available capital
        amount = min(self.dollar_amount, available_capital)
        return amount / price

    def to_dict(self):
        return {
            'type': 'FixedDollarAmount',
            'dollar_amount': self.dollar_amount
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data['dollar_amount'])


class PercentPortfolio(PositionSizer):
    """
    Allocate percentage of total portfolio value.

    Example: 10% of portfolio
    - Portfolio = $50k → $5k per position
    - Portfolio = $100k → $10k per position

    Positions grow/shrink with portfolio value.
    """

    def __init__(self, percent: float):
        if not 0 < percent <= 1.0:
            raise ValueError("percent must be between 0 and 1.0")
        self.percent = percent

    def calculate_shares(self, price, available_capital, portfolio_value,
                        portfolio=None, ticker=None):
        if price <= 0:
            raise ValueError("price must be positive")

        # Calculate target dollar amount
        target_amount = portfolio_value * self.percent

        # Don't exceed available capital
        amount = min(target_amount, available_capital)
        return amount / price

    def to_dict(self):
        return {
            'type': 'PercentPortfolio',
            'percent': self.percent
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data['percent'])


class MaxShares(PositionSizer):
    """
    Buy as many shares as possible with available capital.

    Uses all available cash (respects max_positions constraint).
    """

    def calculate_shares(self, price, available_capital, portfolio_value,
                        portfolio=None, ticker=None):
        if price <= 0:
            raise ValueError("price must be positive")

        return available_capital / price

    def to_dict(self):
        return {'type': 'MaxShares'}

    @classmethod
    def from_dict(cls, data):
        return cls()


# Factory function
def create_position_sizer(data: dict) -> PositionSizer:
    """
    Create PositionSizer from config dict.

    Args:
        data: Dict with 'type' key

    Returns:
        PositionSizer instance

    Raises:
        ValueError: If unknown sizer type
    """
    sizer_type = data.get('type')

    if sizer_type == 'FixedDollarAmount':
        return FixedDollarAmount.from_dict(data)
    elif sizer_type == 'PercentPortfolio':
        return PercentPortfolio.from_dict(data)
    elif sizer_type == 'MaxShares':
        return MaxShares.from_dict(data)
    else:
        raise ValueError(f"Unknown position sizer type: {sizer_type}")
```

### Test Strategy

```python
# tests/test_positionsizer.py

class TestFixedDollarAmount:
    def test_basic_calculation(self):
        """Test basic share calculation."""
        sizer = FixedDollarAmount(dollar_amount=5000)
        shares = sizer.calculate_shares(
            price=100.0,
            available_capital=10000,
            portfolio_value=50000
        )
        assert shares == 50.0  # $5000 / $100

    def test_respects_available_capital(self):
        """Don't exceed available capital."""
        sizer = FixedDollarAmount(dollar_amount=5000)
        shares = sizer.calculate_shares(
            price=100.0,
            available_capital=3000,  # Only $3k available
            portfolio_value=50000
        )
        assert shares == 30.0  # $3000 / $100 (not 50)

    def test_fractional_shares(self):
        """Support fractional shares."""
        sizer = FixedDollarAmount(dollar_amount=5000)
        shares = sizer.calculate_shares(
            price=333.33,
            available_capital=10000,
            portfolio_value=50000
        )
        assert abs(shares - 15.0) < 0.01  # $5000 / $333.33 ≈ 15

class TestPercentPortfolio:
    def test_scales_with_portfolio(self):
        """Position size grows with portfolio."""
        sizer = PercentPortfolio(percent=0.10)  # 10%

        # Small portfolio
        shares1 = sizer.calculate_shares(100.0, 5000, 50000)
        assert shares1 == 50.0  # $5k (10% of 50k) / $100

        # Larger portfolio
        shares2 = sizer.calculate_shares(100.0, 10000, 100000)
        assert shares2 == 100.0  # $10k (10% of 100k) / $100

# Test serialization for all classes...
```

**Edge Cases to Test**:
- Zero/negative price (should raise ValueError)
- Zero available capital (should return 0 shares)
- Percent > 1.0 (should raise ValueError in __init__)
- Serialization round-trip for all sizers

---

## 2️⃣ Strategy Class (SPEC lines 1165-1233)

### Purpose
Bundle entry rules, exit rules, universe, and position sizer into a complete trading strategy.

### Location
**File**: `backtester/strategy.py` (~150 lines)
**Tests**: `tests/test_strategy.py` (~250 lines, 15+ tests)

### Implementation

```python
from typing import List, Optional
from datetime import date
from backtester.entryrule import EntryRule, Signal
from backtester.exitrule import ExitRule
from backtester.positionsizer import PositionSizer

class Strategy:
    """
    Complete trading strategy combining:
    - Entry rules (when to buy)
    - Exit rules (when to sell)
    - Universe (what to trade)
    - Position sizer (how much to buy)

    Example:
        strategy = Strategy(
            name="Earnings Beat Value",
            entry_rules=[earnings_beat_rule, low_pe_rule],
            exit_rules=CompositeExitRule([...]),
            position_sizer=FixedDollarAmount(5000),
            universe=['AAPL', 'MSFT', 'GOOGL']
        )
    """

    def __init__(self,
                 name: str,
                 entry_rules: List[EntryRule],
                 exit_rules: ExitRule,
                 position_sizer: PositionSizer,
                 universe: List[str],
                 description: str = ""):
        """
        Args:
            name: Strategy name
            entry_rules: List of EntryRule instances
            exit_rules: Single ExitRule (use CompositeExitRule for multiple)
            position_sizer: PositionSizer instance
            universe: List of tickers to trade
            description: Optional strategy description
        """
        if not entry_rules:
            raise ValueError("Strategy requires at least one entry rule")
        if not universe:
            raise ValueError("Strategy requires non-empty universe")

        self.name = name
        self.entry_rules = entry_rules
        self.exit_rules = exit_rules
        self.position_sizer = position_sizer
        self.universe = universe
        self.description = description

    def generate_signals(self,
                        date: date,
                        data_provider,
                        portfolio=None) -> List[Signal]:
        """
        Generate entry signals for all tickers in universe.

        Args:
            date: Current date
            data_provider: DataProvider instance
            portfolio: Optional Portfolio for position-aware rules

        Returns:
            List[Signal]: All triggered signals, sorted by priority (high to low)
        """
        signals = []

        # Check each ticker in universe
        for ticker in self.universe:
            # Check each entry rule
            for rule in self.entry_rules:
                signal = rule.should_enter(ticker, date, data_provider, portfolio)
                if signal:
                    signals.append(signal)

        # Sort by priority (highest first)
        signals.sort(key=lambda s: s.priority, reverse=True)

        return signals

    def to_dict(self) -> dict:
        """Serialize for config."""
        return {
            'name': self.name,
            'description': self.description,
            'entry_rules': [rule.to_dict() for rule in self.entry_rules],
            'exit_rules': self.exit_rules.to_dict(),
            'position_sizer': self.position_sizer.to_dict(),
            'universe': self.universe
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Strategy':
        """Deserialize from config."""
        from backtester.entryrule import create_entry_rule
        from backtester.exitrule import create_exit_rule
        from backtester.positionsizer import create_position_sizer

        entry_rules = [create_entry_rule(r) for r in data['entry_rules']]
        exit_rules = create_exit_rule(data['exit_rules'])
        position_sizer = create_position_sizer(data['position_sizer'])

        return cls(
            name=data['name'],
            entry_rules=entry_rules,
            exit_rules=exit_rules,
            position_sizer=position_sizer,
            universe=data['universe'],
            description=data.get('description', '')
        )
```

### Test Strategy

```python
# tests/test_strategy.py

def test_generate_signals_multiple_tickers():
    """Test signal generation across universe."""
    rule = EntryRule(
        calculation=EarningsSurprise(),
        condition=GreaterThan(0.05),
        signal_type='earnings_beat',
        priority=2.0
    )

    strategy = Strategy(
        name="Test",
        entry_rules=[rule],
        exit_rules=TimeBasedExit(30),
        position_sizer=FixedDollarAmount(5000),
        universe=['AAPL', 'MSFT']
    )

    # Mock provider returns beat for AAPL, miss for MSFT
    signals = strategy.generate_signals(date(2024, 2, 5), mock_provider)

    assert len(signals) == 1
    assert signals[0].ticker == 'AAPL'
    assert signals[0].signal_type == 'earnings_beat'

def test_signals_sorted_by_priority():
    """Signals sorted highest priority first."""
    rule1 = EntryRule(..., priority=1.0)
    rule2 = EntryRule(..., priority=3.0)
    rule3 = EntryRule(..., priority=2.0)

    strategy = Strategy(entry_rules=[rule1, rule2, rule3], ...)
    signals = strategy.generate_signals(...)

    # Should be ordered: rule2 (3.0), rule3 (2.0), rule1 (1.0)
    assert signals[0].priority == 3.0
    assert signals[1].priority == 2.0
```

---

## 3️⃣ Backtester Class (SPEC lines 1236-1408) ⚠️ CRITICAL

### Purpose
Main simulation engine that orchestrates the entire backtest.

### Location
**File**: `backtester/backtester.py` (~250 lines)
**Tests**: `tests/test_backtester.py` (~400 lines, 25+ tests)

### Architecture

**Key Insight**: The daily loop follows this EXACT order:
1. **Process exits first** (risk management priority)
2. **Generate entry signals** from strategy
3. **Rank signals** by priority
4. **Open positions** until capital exhausted or max positions reached
5. **Record equity** for performance tracking

### Implementation

```python
from datetime import date, timedelta
from typing import List, Tuple
import pandas as pd
from backtester.portfolio import Portfolio
from backtester.strategy import Strategy
from backtester.dataprovider import DataProvider
from backtester.results import Results

class Backtester:
    """
    Main backtesting engine.

    Simulates trading strategy over historical data with realistic
    constraints and transaction costs.

    Example:
        bt = Backtester(
            strategy=my_strategy,
            data_provider=yf_provider,
            initial_capital=100000,
            start_date=date(2020, 1, 1),
            end_date=date(2023, 12, 31),
            commission=1.0,
            slippage=0.001
        )

        results = bt.run()
        print(results.total_return)
        results.plot_equity_curve()
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
        Args:
            strategy: Strategy instance to backtest
            data_provider: DataProvider for market data
            initial_capital: Starting cash
            start_date: Backtest start date
            end_date: Backtest end date (inclusive)
            commission: Flat commission per trade
            slippage: Slippage as decimal (0.001 = 0.1%)
            max_positions: Max concurrent positions
            fractional_shares: Allow fractional share quantities
        """
        if initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if start_date >= end_date:
            raise ValueError("start_date must be before end_date")

        self.strategy = strategy
        self.data_provider = data_provider
        self.initial_capital = initial_capital
        self.start_date = start_date
        self.end_date = end_date

        # Create portfolio
        self.portfolio = Portfolio(
            initial_capital=initial_capital,
            max_positions=max_positions,
            commission=commission,
            slippage=slippage,
            fractional_shares=fractional_shares
        )

    def run(self) -> 'Results':
        """
        Run backtest simulation.

        Returns:
            Results: Performance metrics and visualization data
        """
        current_date = self.start_date

        while current_date <= self.end_date:
            self._process_day(current_date)
            current_date += timedelta(days=1)

        # Close all remaining positions at end
        self._close_all_positions(self.end_date)

        # Build results
        return Results(
            portfolio=self.portfolio,
            strategy=self.strategy,
            start_date=self.start_date,
            end_date=self.end_date,
            initial_capital=self.initial_capital
        )

    def _process_day(self, current_date: date):
        """
        Process single trading day.

        Order of operations (CRITICAL):
        1. Process exits (risk management first!)
        2. Generate entry signals
        3. Rank and execute entries
        4. Record equity
        """
        # 1. EXITS FIRST (risk management priority)
        self._process_exits(current_date)

        # 2. Generate entry signals from strategy
        signals = self.strategy.generate_signals(
            date=current_date,
            data_provider=self.data_provider,
            portfolio=self.portfolio
        )

        # 3. Process entries (signals already sorted by priority)
        self._process_entries(current_date, signals)

        # 4. Record equity for performance tracking
        total_value = self.portfolio.get_total_value(current_date, self.data_provider)
        self.portfolio.record_equity(current_date, total_value)

    def _process_exits(self, current_date: date):
        """
        Check all open positions for exit signals.

        Closes or reduces positions based on exit rules.
        """
        # Get current prices for all positions
        positions_to_exit = []

        for ticker, roundtrips in self.portfolio.positions.items():
            for rt in roundtrips:
                # Skip closed positions
                if rt.shares == 0:
                    continue

                # Get current price
                bar = self.data_provider.get_bar(ticker, current_date)
                if not bar:
                    continue  # No data available

                current_price = bar['close']

                # Check exit rules
                should_exit, exit_portion, reason = self.strategy.exit_rules.should_exit(
                    roundtrip=rt,
                    date=current_date,
                    price=current_price
                )

                if should_exit:
                    positions_to_exit.append((ticker, rt, exit_portion, current_price, reason))

        # Execute exits
        for ticker, rt, portion, price, reason in positions_to_exit:
            shares_to_exit = rt.shares * portion

            if portion >= 0.9999:  # Close entirely (avoid floating point issues)
                self.portfolio.close_position(ticker, rt.id, current_date, price, reason)
            else:  # Partial exit
                self.portfolio.reduce_position(ticker, rt.id, shares_to_exit,
                                              current_date, price, reason)

    def _process_entries(self, current_date: date, signals: List):
        """
        Process entry signals in priority order.

        Opens positions until capital exhausted or max positions reached.
        """
        for signal in signals:
            # Check if we can open more positions
            if not self.portfolio.can_open_position():
                break  # Max positions reached

            # Get current price
            bar = self.data_provider.get_bar(signal.ticker, current_date)
            if not bar:
                continue  # No data available

            current_price = bar['close']

            # Calculate position size
            available_capital = self.portfolio.cash
            portfolio_value = self.portfolio.get_total_value(current_date, self.data_provider)

            shares = self.strategy.position_sizer.calculate_shares(
                price=current_price,
                available_capital=available_capital,
                portfolio_value=portfolio_value,
                portfolio=self.portfolio,
                ticker=signal.ticker
            )

            # Skip if insufficient capital
            if shares <= 0:
                continue

            # Open position
            try:
                self.portfolio.open_position(
                    ticker=signal.ticker,
                    date=current_date,
                    price=current_price,
                    shares=shares,
                    reason=signal.signal_type
                )
            except ValueError:
                # Insufficient capital or other error
                continue

    def _close_all_positions(self, final_date: date):
        """Close all remaining positions at backtest end."""
        for ticker, roundtrips in list(self.portfolio.positions.items()):
            for rt in roundtrips:
                if rt.shares > 0:
                    bar = self.data_provider.get_bar(ticker, final_date)
                    if bar:
                        self.portfolio.close_position(
                            ticker=ticker,
                            roundtrip_id=rt.id,
                            date=final_date,
                            price=bar['close'],
                            reason='backtest_end'
                        )
```

### Test Strategy

```python
# tests/test_backtester.py

def test_exits_processed_before_entries():
    """Critical: Exits must be processed before new entries."""
    # Create strategy with entry rule that always triggers
    # and exit rule that closes on day 2

    bt = Backtester(...)

    # Day 1: Open position
    bt._process_day(date(2024, 1, 1))
    assert len(bt.portfolio.positions['AAPL']) == 1
    assert bt.portfolio.positions['AAPL'][0].shares > 0

    # Day 2: Should exit before processing new entry
    bt._process_day(date(2024, 1, 2))

    # Verify exit happened (check transaction log)
    txns = bt.portfolio.get_transaction_log_df()
    close_txn = txns[txns['transaction_type'] == 'close']
    assert len(close_txn) == 1
    assert close_txn.iloc[0]['date'] == date(2024, 1, 2)

def test_respects_max_positions():
    """Don't exceed max_positions limit."""
    strategy = Strategy(
        entry_rules=[AlwaysTriggerRule()],  # Always signals
        universe=['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA'],
        ...
    )

    bt = Backtester(strategy=strategy, max_positions=3, ...)
    bt.run()

    # Check that we never held more than 3 positions
    for date in bt.portfolio.equity_history.keys():
        active_positions = sum(
            1 for roundtrips in bt.portfolio.positions.values()
            for rt in roundtrips if rt.shares > 0
        )
        assert active_positions <= 3

def test_partial_exits():
    """Test partial position exits."""
    # Strategy with ProfitTargetExit(0.20, exit_portion=0.5)
    bt = Backtester(...)

    # Open position at $100
    # Price moves to $125 (25% gain)
    # Should exit 50% of shares

    result = bt.run()

    # Verify 50% exit in transaction log
    txns = bt.portfolio.get_transaction_log_df()
    reduce_txn = txns[txns['transaction_type'] == 'reduce']

    assert len(reduce_txn) == 1
    # Original shares * 0.5 should be reduced
```

**Critical Edge Cases**:
- Empty universe (no tickers to trade)
- No signals triggered during entire backtest
- All positions exit on same day
- Insufficient capital for any entries
- Data gaps (missing bars for some days)
- Exit and entry signals for same ticker on same day

---

## 4️⃣ Results Class (SPEC lines 1411-1638)

### Purpose
Calculate performance metrics and provide visualization capabilities.

### Location
**File**: `backtester/results.py` (~300 lines)
**Tests**: `tests/test_results.py` (~200 lines, 15+ tests)

### Implementation

```python
from datetime import date
from typing import Dict, List
import pandas as pd
import numpy as np
from backtester.portfolio import Portfolio
from backtester.strategy import Strategy

class Results:
    """
    Backtest performance metrics and visualization.

    Provides comprehensive analysis including:
    - Returns (total, annualized, per-trade)
    - Risk metrics (Sharpe, max drawdown, volatility)
    - Trade statistics (win rate, avg win/loss)
    - Equity curve and drawdown visualization

    Example:
        results = backtester.run()

        print(f"Total Return: {results.total_return:.2%}")
        print(f"Sharpe Ratio: {results.sharpe_ratio:.2f}")
        print(f"Win Rate: {results.win_rate:.2%}")

        results.plot_equity_curve()
        results.print_summary()
    """

    def __init__(self,
                 portfolio: Portfolio,
                 strategy: Strategy,
                 start_date: date,
                 end_date: date,
                 initial_capital: float):
        """
        Args:
            portfolio: Portfolio instance after backtest
            strategy: Strategy that was backtested
            start_date: Backtest start date
            end_date: Backtest end date
            initial_capital: Starting capital
        """
        self.portfolio = portfolio
        self.strategy = strategy
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital

        # Build DataFrames for analysis
        self._equity_df = self._build_equity_df()
        self._trades_df = self._build_trades_df()

    def _build_equity_df(self) -> pd.DataFrame:
        """Build DataFrame from equity history."""
        if not self.portfolio.equity_history:
            return pd.DataFrame(columns=['date', 'equity'])

        df = pd.DataFrame([
            {'date': date, 'equity': equity}
            for date, equity in self.portfolio.equity_history.items()
        ])
        df = df.sort_values('date').reset_index(drop=True)
        return df

    def _build_trades_df(self) -> pd.DataFrame:
        """Build DataFrame of closed trades."""
        trades = []

        for ticker, roundtrips in self.portfolio.positions.items():
            for rt in roundtrips:
                if rt.status == 'closed':
                    trades.append({
                        'ticker': ticker,
                        'entry_date': rt.entry_date,
                        'exit_date': rt.exit_date,
                        'holding_days': rt.holding_days,
                        'shares': rt.initial_shares,
                        'entry_price': rt.average_entry_price,
                        'exit_price': rt.exit_price,
                        'pnl': rt.realized_pnl,
                        'pnl_pct': rt.realized_pnl / rt.total_cost if rt.total_cost > 0 else 0
                    })

        if not trades:
            return pd.DataFrame()

        return pd.DataFrame(trades)

    # === RETURN METRICS ===

    @property
    def total_return(self) -> float:
        """
        Total return over backtest period.

        Returns:
            float: (final_equity - initial_capital) / initial_capital
        """
        if self._equity_df.empty:
            return 0.0

        final_equity = self._equity_df.iloc[-1]['equity']
        return (final_equity - self.initial_capital) / self.initial_capital

    @property
    def annualized_return(self) -> float:
        """
        Annualized return (CAGR).

        Returns:
            float: Compound annual growth rate
        """
        if self._equity_df.empty or len(self._equity_df) < 2:
            return 0.0

        days = (self.end_date - self.start_date).days
        years = days / 365.25

        if years <= 0:
            return 0.0

        final_equity = self._equity_df.iloc[-1]['equity']
        cagr = (final_equity / self.initial_capital) ** (1 / years) - 1
        return cagr

    # === RISK METRICS ===

    @property
    def volatility(self) -> float:
        """
        Annualized volatility of daily returns.

        Returns:
            float: Standard deviation of returns * sqrt(252)
        """
        if len(self._equity_df) < 2:
            return 0.0

        daily_returns = self._equity_df['equity'].pct_change().dropna()
        return daily_returns.std() * np.sqrt(252)

    @property
    def sharpe_ratio(self, risk_free_rate: float = 0.0) -> float:
        """
        Sharpe ratio (annualized).

        Args:
            risk_free_rate: Annual risk-free rate (default 0%)

        Returns:
            float: (annualized_return - risk_free_rate) / volatility
        """
        vol = self.volatility
        if vol == 0:
            return 0.0

        return (self.annualized_return - risk_free_rate) / vol

    @property
    def max_drawdown(self) -> float:
        """
        Maximum peak-to-trough drawdown.

        Returns:
            float: Largest decline from peak as decimal (0.20 = 20% drawdown)
        """
        if self._equity_df.empty:
            return 0.0

        equity = self._equity_df['equity']
        cummax = equity.cummax()
        drawdown = (equity - cummax) / cummax
        return abs(drawdown.min())

    # === TRADE STATISTICS ===

    @property
    def total_trades(self) -> int:
        """Number of closed trades."""
        return len(self._trades_df)

    @property
    def win_rate(self) -> float:
        """
        Percentage of winning trades.

        Returns:
            float: Wins / total_trades
        """
        if self.total_trades == 0:
            return 0.0

        wins = (self._trades_df['pnl'] > 0).sum()
        return wins / self.total_trades

    @property
    def avg_win(self) -> float:
        """Average P&L of winning trades."""
        wins = self._trades_df[self._trades_df['pnl'] > 0]['pnl']
        return wins.mean() if len(wins) > 0 else 0.0

    @property
    def avg_loss(self) -> float:
        """Average P&L of losing trades (negative value)."""
        losses = self._trades_df[self._trades_df['pnl'] < 0]['pnl']
        return losses.mean() if len(losses) > 0 else 0.0

    @property
    def profit_factor(self) -> float:
        """
        Ratio of gross profits to gross losses.

        Returns:
            float: total_wins / abs(total_losses)
        """
        wins = self._trades_df[self._trades_df['pnl'] > 0]['pnl'].sum()
        losses = abs(self._trades_df[self._trades_df['pnl'] < 0]['pnl'].sum())

        if losses == 0:
            return float('inf') if wins > 0 else 0.0

        return wins / losses

    # === SUMMARY ===

    def print_summary(self):
        """Print formatted summary of results."""
        print("=" * 60)
        print(f"BACKTEST RESULTS: {self.strategy.name}")
        print("=" * 60)
        print(f"\nPeriod: {self.start_date} to {self.end_date}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")

        if not self._equity_df.empty:
            final_equity = self._equity_df.iloc[-1]['equity']
            print(f"Final Equity: ${final_equity:,.2f}")

        print(f"\n--- Returns ---")
        print(f"Total Return: {self.total_return:.2%}")
        print(f"Annualized Return: {self.annualized_return:.2%}")

        print(f"\n--- Risk ---")
        print(f"Volatility: {self.volatility:.2%}")
        print(f"Sharpe Ratio: {self.sharpe_ratio:.2f}")
        print(f"Max Drawdown: {self.max_drawdown:.2%}")

        print(f"\n--- Trades ---")
        print(f"Total Trades: {self.total_trades}")
        print(f"Win Rate: {self.win_rate:.2%}")
        print(f"Avg Win: ${self.avg_win:,.2f}")
        print(f"Avg Loss: ${self.avg_loss:,.2f}")
        print(f"Profit Factor: {self.profit_factor:.2f}")

        print("=" * 60)

    def to_dict(self) -> dict:
        """Export all metrics as dict."""
        return {
            'strategy_name': self.strategy.name,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'initial_capital': self.initial_capital,
            'total_return': self.total_return,
            'annualized_return': self.annualized_return,
            'volatility': self.volatility,
            'sharpe_ratio': self.sharpe_ratio,
            'max_drawdown': self.max_drawdown,
            'total_trades': self.total_trades,
            'win_rate': self.win_rate,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'profit_factor': self.profit_factor
        }
```

### Test Strategy

```python
# tests/test_results.py

def test_total_return_calculation():
    """Test total return calculation."""
    portfolio = Portfolio(initial_capital=100000)
    portfolio.record_equity(date(2024, 1, 1), 100000)
    portfolio.record_equity(date(2024, 12, 31), 120000)

    results = Results(
        portfolio=portfolio,
        strategy=mock_strategy,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        initial_capital=100000
    )

    assert results.total_return == 0.20  # 20% gain

def test_max_drawdown():
    """Test max drawdown calculation."""
    portfolio = Portfolio(initial_capital=100000)
    portfolio.record_equity(date(2024, 1, 1), 100000)
    portfolio.record_equity(date(2024, 2, 1), 120000)  # Peak
    portfolio.record_equity(date(2024, 3, 1), 90000)   # Trough (-25% from peak)
    portfolio.record_equity(date(2024, 4, 1), 110000)  # Recovery

    results = Results(...)

    assert abs(results.max_drawdown - 0.25) < 0.01  # 25% drawdown

def test_win_rate():
    """Test win rate calculation."""
    # Create portfolio with 3 closed trades: 2 wins, 1 loss
    portfolio = create_portfolio_with_trades([
        {'pnl': 500},   # Win
        {'pnl': -200},  # Loss
        {'pnl': 300}    # Win
    ])

    results = Results(...)

    assert results.win_rate == 2/3  # 66.67%
    assert results.total_trades == 3
```

---

## 🔄 Implementation Order

### Day 1 (4 hours)
1. **PositionSizer** - Simplest component
   - Implement FixedDollarAmount, PercentPortfolio, MaxShares
   - Write 20 tests
   - Verify serialization

### Day 2 (3 hours)
2. **Strategy** - Glue layer
   - Implement Strategy class
   - Test signal generation
   - Test serialization

### Day 3 (5 hours) ⚠️ HARDEST
3. **Backtester** - Main engine
   - Implement daily loop carefully
   - Test exit-before-entry ordering
   - Test max_positions constraint
   - Test partial exits

### Day 4 (4 hours)
4. **Results** - Metrics and analysis
   - Implement all metrics
   - Test calculations with known values
   - Add print_summary()

### Day 5 (2 hours)
5. **Integration Testing**
   - End-to-end backtest with real data
   - Verify all components work together
   - Document Phase 4 completion

---

## ✅ Success Criteria

**Phase 4 Complete When:**
- [ ] All 4 classes implemented
- [ ] 60+ new tests written (total ~400 tests)
- [ ] All tests passing (100%)
- [ ] Can run complete backtest start-to-finish
- [ ] Results print_summary() works
- [ ] Transaction log exports correctly
- [ ] CHANGELOG.md updated
- [ ] to_do.md updated to 80%
- [ ] SPEC.md updated with Phase 4 notes

---

## 🚨 Common Pitfalls

### Backtester Loop Order
**WRONG ORDER** ❌:
```python
# DON'T DO THIS
signals = strategy.generate_signals(...)
process_entries(signals)  # Entries first
process_exits(...)        # Exits second
```

**CORRECT ORDER** ✅:
```python
# DO THIS
process_exits(...)        # Exits FIRST (risk management)
signals = strategy.generate_signals(...)
process_entries(signals)  # Entries second
```

### Partial Exits
**WRONG** ❌:
```python
# Don't assume full exit
portfolio.close_position(...)  # Always closes 100%
```

**CORRECT** ✅:
```python
# Check exit_portion
if exit_portion >= 0.9999:
    portfolio.close_position(...)
else:
    shares_to_exit = roundtrip.shares * exit_portion
    portfolio.reduce_position(..., shares_to_exit, ...)
```

### Equity Recording
**WRONG** ❌:
```python
# Don't record before processing day
portfolio.record_equity(date, ...)
process_exits(date)
process_entries(date)
```

**CORRECT** ✅:
```python
# Record AFTER all transactions
process_exits(date)
process_entries(date)
value = portfolio.get_total_value(date, provider)
portfolio.record_equity(date, value)  # Last step
```

---

## 📚 Integration Example

```python
# Complete end-to-end example

from datetime import date
from backtester.yfinance_provider import YFinanceProvider
from backtester.entryrule import EntryRule
from backtester.calculation import EarningsSurprise
from backtester.condition import GreaterThan
from backtester.exitrule import CompositeExitRule, StopLossExit, TimeBasedExit
from backtester.positionsizer import FixedDollarAmount
from backtester.strategy import Strategy
from backtester.backtester import Backtester

# 1. Setup data provider
provider = YFinanceProvider()

# 2. Define entry rule
entry_rule = EntryRule(
    calculation=EarningsSurprise(),
    condition=GreaterThan(0.05),  # 5%+ beat
    signal_type='earnings_beat',
    priority=2.0
)

# 3. Define exit rules
exit_rules = CompositeExitRule(rules=[
    (StopLossExit(0.08), 1.0),      # 8% stop loss
    (TimeBasedExit(30), 1.0)        # 30 day time exit
])

# 4. Define position sizer
sizer = FixedDollarAmount(5000)

# 5. Create strategy
strategy = Strategy(
    name="Earnings Beat",
    entry_rules=[entry_rule],
    exit_rules=exit_rules,
    position_sizer=sizer,
    universe=['AAPL', 'MSFT', 'GOOGL', 'NVDA']
)

# 6. Run backtest
backtester = Backtester(
    strategy=strategy,
    data_provider=provider,
    initial_capital=100000,
    start_date=date(2020, 1, 1),
    end_date=date(2023, 12, 31),
    commission=1.0,
    slippage=0.001,
    max_positions=5
)

results = backtester.run()

# 7. Analyze results
results.print_summary()

# Output:
# ==========================================================
# BACKTEST RESULTS: Earnings Beat
# ==========================================================
#
# Period: 2020-01-01 to 2023-12-31
# Initial Capital: $100,000.00
# Final Equity: $142,500.00
#
# --- Returns ---
# Total Return: 42.50%
# Annualized Return: 9.35%
#
# --- Risk ---
# Volatility: 18.23%
# Sharpe Ratio: 0.51
# Max Drawdown: 15.67%
#
# --- Trades ---
# Total Trades: 23
# Win Rate: 65.22%
# Avg Win: $2,341.23
# Avg Loss: -$1,123.45
# Profit Factor: 1.82
# ==========================================================
```

---

## 🎯 Next Steps After Phase 4

Once Phase 4 complete (80% progress), Phase 5 begins:
1. YAML config loading/saving
2. Visualization (equity curve, drawdown chart)
3. CSV export for transaction log
4. Strategy optimization helpers
5. Documentation polish
6. Bug fixes and edge case handling

**Target**: V1 Complete at 100%

---

## 💡 Tips for Success

1. **Test incrementally** - Don't write entire class then test. Write method, test method, repeat.

2. **Use real data early** - Don't rely on mocks. Test with YFinanceProvider on real tickers.

3. **Check SPEC constantly** - Every method signature should match SPEC exactly.

4. **Focus on correctness** - Phase 4 is the heart of the backtester. Get it RIGHT, not fast.

5. **Verify order of operations** - The exit-before-entry ordering is CRITICAL for realistic results.

6. **Test edge cases thoroughly**:
   - No signals for entire backtest
   - All positions exit same day
   - Insufficient capital for entries
   - Data gaps (missing bars)

7. **Use print_summary() early** - Great for debugging. Add it to Results first.

---

## 🔧 Debugging Checklist

If backtest results look wrong:

- [ ] Are exits processed before entries?
- [ ] Is equity recorded after all transactions?
- [ ] Are transaction costs applied correctly?
- [ ] Is max_positions constraint respected?
- [ ] Are partial exits handled correctly?
- [ ] Is final equity calculation including open positions?
- [ ] Are dates timezone-aware and consistent?
- [ ] Is position sizing respecting available capital?

---

## 📞 When You Get Stuck

**Before asking for help, check:**
1. Read the SPEC section for that component
2. Look at similar patterns in Phase 1-3 code
3. Run single test with `-v --tb=long` for full traceback
4. Print intermediate values in the failing code
5. Verify your test data is realistic

**Good question format:**
```
I'm implementing [component] and getting [error].

Expected: [what should happen]
Actual: [what's happening]

Code snippet:
[relevant code]

Test that fails:
[test name and assertion]
```

---

## 🎊 You've Got This!

You've already built:
- ✅ Complete position management (Phase 1)
- ✅ Data provider integration (Phase 2A)
- ✅ Entry rules system (Phase 2B)
- ✅ Exit rules system (Phase 3)

Phase 4 ties it all together into a working backtester. Take your time, test thoroughly, and trust the architecture you've built.

**The foundation is rock-solid. Time to bring it home!** 🚀
