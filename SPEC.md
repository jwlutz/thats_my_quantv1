# V1 Backtester - Final Pseudocode Specification

> **📍 PROJECT STATUS (60% Complete):**
> - ✅ **Phase 1 Complete:** Position Management (Transaction, RoundTrip, Portfolio, TransactionCost)
> - ✅ **Phase 2 Complete:** Data & Entry Rules (DataProvider, Calculation, Condition, EntryRule)
> - ✅ **Phase 3 Complete:** Exit Rules (TimeBasedExit, StopLossExit, TrailingStopExit, ProfitTargetExit, CompositeExitRule)
> - 🔄 **Next: Phase 4** - Backtester Engine & Results (see sections 8-11 below)
>
> **For Phase 4 Implementation:**
> - Build PositionSizer class (section 8, lines ~1124-1180)
> - Build Strategy class (section 9, lines ~1192-1295) - bundles entry + exit + universe
> - Build Backtester engine (section 10, lines ~1309-1463) - main simulation loop
> - Build Results class (section 11, lines ~1476-1721) - performance metrics & visualization
> - Tests: Full end-to-end backtest + all metrics + equity curve

> **⚠️ DESIGN NOTE:** This spec was originally written for a specific earnings-based strategy.
> However, the goal is to build a **GENERALIZED backtesting platform**.
> - Examples shown are **illustrations**, not constraints
> - Keep all components flexible and extensible
> - Avoid hardcoding strategy-specific logic
> - Use abstractions (ABC) for pluggable components

## Build Order

**Phase 1 (Weeks 1-3):** ✅ Transaction, RoundTrip, Portfolio
**Phase 2 (Weeks 4-6):** ✅ DataProvider, Entry Rules
**Phase 3 (Weeks 7-9):** 🔄 Exit Rules (NEXT), Backtester, Results
**Phase 4 (Weeks 10-11):** Config, Polish

---

## 1. Transaction (Immutable Record)

```python
from dataclasses import dataclass, field
from datetime import date
from uuid import uuid4

@dataclass(frozen=True)
class Transaction:
    """
    Immutable record of a single trade action.
    
    Attributes:
        id: Unique identifier (UUID)
        roundtrip_id: Parent RoundTrip ID
        ticker: Symbol
        date: Execution date
        transaction_type: "open", "add", "reduce", "close"
        shares: Fractional shares (float)
        price: Price per share
        net_amount: Actual cash impact (negative for buys, positive for sells)
                   Includes all costs (commission + slippage)
        reason: Why transaction occurred ("signal", "stop_loss", "time_exit", etc.)
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    roundtrip_id: str = ""
    ticker: str = ""
    date: date = None
    transaction_type: str = ""  # open, add, reduce, close
    shares: float = 0.0
    price: float = 0.0
    net_amount: float = 0.0
    reason: str = ""
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "roundtrip_id": self.roundtrip_id,
            "ticker": self.ticker,
            "date": self.date.isoformat(),
            "transaction_type": self.transaction_type,
            "shares": self.shares,
            "price": self.price,
            "net_amount": self.net_amount,
            "reason": self.reason
        }
```

**Tests needed:**
- Create transaction with all fields
- Verify immutability (can't modify after creation)
- Serialize to dict
- UUID generation works

---

## 2. RoundTrip (Position Lifecycle)

```python
from typing import List
from dataclasses import dataclass, field

@dataclass
class RoundTrip:
    """
    Manages lifecycle of a position from first entry to final exit.
    Supports multiple entries (DCA) and partial exits.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    ticker: str = ""
    transactions: List[Transaction] = field(default_factory=list)
    exit_rule: 'ExitRule' = None
    entry_signal_metadata: dict = field(default_factory=dict)
    
    # Internal tracking (updated as transactions added)
    _total_cost: float = 0.0  # Cumulative cost paid (all entries)
    _total_proceeds: float = 0.0  # Cumulative proceeds (all exits)
    
    def add_transaction(self, txn: Transaction):
        """Add transaction and update internal state."""
        self.transactions.append(txn)
        
        if txn.transaction_type in ["open", "add"]:
            # Entry transactions have negative net_amount (cash out)
            self._total_cost += abs(txn.net_amount)
        else:  # reduce or close
            # Exit transactions have positive net_amount (cash in)
            self._total_proceeds += txn.net_amount
    
    @property
    def is_open(self) -> bool:
        """True if position still has shares."""
        return self.remaining_shares > 0
    
    @property
    def total_shares(self) -> float:
        """Total shares ever held (entries only)."""
        return sum(t.shares for t in self.transactions 
                  if t.transaction_type in ["open", "add"])
    
    @property
    def remaining_shares(self) -> float:
        """Currently held shares."""
        entries = sum(t.shares for t in self.transactions 
                     if t.transaction_type in ["open", "add"])
        exits = sum(t.shares for t in self.transactions
                   if t.transaction_type in ["reduce", "close"])
        return entries - exits
    
    @property
    def average_entry_price(self) -> float:
        """Weighted average entry price (cost per share)."""
        total_shares = self.total_shares
        if total_shares == 0:
            return 0.0
        return self._total_cost / total_shares
    
    @property
    def realized_pnl(self) -> float:
        """P&L from shares already sold."""
        return self._total_proceeds - self._total_cost
    
    def get_unrealized_pnl(self, current_price: float) -> float:
        """P&L from shares still held."""
        if self.remaining_shares == 0:
            return 0.0
        current_value = self.remaining_shares * current_price
        cost_basis = self.remaining_shares * self.average_entry_price
        return current_value - cost_basis
    
    def get_holding_days(self, current_date: date) -> int:
        """Days since first entry."""
        if not self.transactions:
            return 0
        first_date = min(t.date for t in self.transactions)
        return (current_date - first_date).days
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticker": self.ticker,
            "is_open": self.is_open,
            "remaining_shares": self.remaining_shares,
            "average_entry_price": self.average_entry_price,
            "realized_pnl": self.realized_pnl,
            "total_cost": self._total_cost,
            "total_proceeds": self._total_proceeds,
            "transactions": [t.to_dict() for t in self.transactions]
        }
```

**Tests needed:**
- Open position (1 transaction)
- Add to position (DCA)
- Partial exit
- Full close
- P&L calculations (realized vs unrealized)
- Average entry price with multiple entries at different prices
- Edge case: close without open (should error)
- Edge case: reduce more shares than available (should error)

---

## 3. TransactionCost

```python
class TransactionCost:
    """
    Calculate trading costs (commission + slippage).
    Supports fractional shares.
    """
    def __init__(self, commission: float = 0.0, slippage_pct: float = 0.001):
        """
        Args:
            commission: Flat fee per trade (0 for Robinhood-style)
            slippage_pct: Slippage as decimal (0.001 = 0.1%)
        """
        self.commission = commission
        self.slippage_pct = slippage_pct
    
    def calculate_entry_cost(self, shares: float, price: float) -> float:
        """
        Total cost to buy shares (positive number).
        
        Cost = (shares × price × (1 + slippage)) + commission
        """
        if shares <= 0:
            raise ValueError(f"Shares must be positive, got {shares}")
        if price <= 0:
            raise ValueError(f"Price must be positive, got {price}")
        
        base_cost = shares * price
        slippage_cost = base_cost * self.slippage_pct
        total = base_cost + slippage_cost + self.commission
        
        return total
    
    def calculate_exit_value(self, shares: float, price: float) -> float:
        """
        Net proceeds from selling shares (positive number).
        
        Proceeds = (shares × price × (1 - slippage)) - commission
        """
        if shares <= 0:
            raise ValueError(f"Shares must be positive, got {shares}")
        if price <= 0:
            raise ValueError(f"Price must be positive, got {price}")
        
        gross_proceeds = shares * price
        slippage_cost = gross_proceeds * self.slippage_pct
        net_proceeds = gross_proceeds - slippage_cost - self.commission
        
        return net_proceeds
```

**Tests needed:**
- Entry cost calculation
- Exit value calculation
- Round trip cost (entry + exit)
- Fractional shares (0.5, 13.7, etc.)
- Zero commission
- Zero slippage
- Error handling (negative shares, zero price)

---

## 4. Portfolio

```python
from typing import Dict, List, Optional

class Portfolio:
    """
    Manages cash, positions (RoundTrips), and transaction history.
    """
    def __init__(self, 
                 starting_capital: float,
                 max_positions: int,
                 transaction_cost: TransactionCost,
                 fractional_shares: bool = True):
        """
        Args:
            starting_capital: Initial cash
            max_positions: Max concurrent positions
            transaction_cost: TransactionCost instance
            fractional_shares: If False, round shares to int
        """
        self.starting_capital = starting_capital
        self.cash = starting_capital
        self.max_positions = max_positions
        self.transaction_cost = transaction_cost
        self.fractional_shares = fractional_shares
        
        self.open_roundtrips: Dict[str, RoundTrip] = {}  # id -> RoundTrip
        self.closed_roundtrips: List[RoundTrip] = []
        self.transaction_log: List[Transaction] = []
        self.equity_history: List[dict] = []
    
    def can_open_position(self) -> bool:
        """Check if room for another position."""
        return len(self.open_roundtrips) < self.max_positions
    
    def _round_shares(self, shares: float) -> float:
        """Round shares if fractional not allowed."""
        if self.fractional_shares:
            return shares
        return float(int(shares))
    
    def open_position(self,
                     ticker: str,
                     date: date,
                     price: float,
                     shares: float,
                     exit_rule: 'ExitRule',
                     signal_metadata: dict = None) -> Optional[RoundTrip]:
        """
        Open new position.
        
        Returns:
            RoundTrip if successful, None if insufficient funds
        """
        # Round shares if needed
        shares = self._round_shares(shares)
        
        if shares <= 0:
            return None
        
        # Check room
        if not self.can_open_position():
            return None
        
        # Calculate cost
        entry_cost = self.transaction_cost.calculate_entry_cost(shares, price)
        
        # Check cash
        if entry_cost > self.cash:
            return None
        
        # Create RoundTrip and Transaction
        roundtrip_id = str(uuid4())
        
        transaction = Transaction(
            id=str(uuid4()),
            roundtrip_id=roundtrip_id,
            ticker=ticker,
            date=date,
            transaction_type="open",
            shares=shares,
            price=price,
            net_amount=-entry_cost,  # Negative (cash out)
            reason="signal"
        )
        
        roundtrip = RoundTrip(
            id=roundtrip_id,
            ticker=ticker,
            transactions=[],
            exit_rule=exit_rule,
            entry_signal_metadata=signal_metadata or {}
        )
        
        roundtrip.add_transaction(transaction)
        
        # Update state
        self.cash -= entry_cost
        self.open_roundtrips[roundtrip_id] = roundtrip
        self.transaction_log.append(transaction)
        
        return roundtrip
    
    def add_to_position(self,
                       roundtrip_id: str,
                       date: date,
                       price: float,
                       shares: float,
                       reason: str = "add") -> bool:
        """
        Add shares to existing RoundTrip (DCA).
        
        Returns:
            True if successful, False if insufficient funds
        """
        if roundtrip_id not in self.open_roundtrips:
            raise ValueError(f"RoundTrip {roundtrip_id} not found")
        
        roundtrip = self.open_roundtrips[roundtrip_id]
        
        # Round shares if needed
        shares = self._round_shares(shares)
        
        if shares <= 0:
            return False
        
        # Calculate cost
        add_cost = self.transaction_cost.calculate_entry_cost(shares, price)
        
        # Check cash
        if add_cost > self.cash:
            return False
        
        # Create transaction
        transaction = Transaction(
            id=str(uuid4()),
            roundtrip_id=roundtrip_id,
            ticker=roundtrip.ticker,
            date=date,
            transaction_type="add",
            shares=shares,
            price=price,
            net_amount=-add_cost,
            reason=reason
        )
        
        # Update
        roundtrip.add_transaction(transaction)
        self.cash -= add_cost
        self.transaction_log.append(transaction)
        
        return True
    
    def reduce_position(self,
                       roundtrip_id: str,
                       date: date,
                       price: float,
                       shares: float,
                       reason: str) -> float:
        """
        Partially close RoundTrip.
        
        Returns:
            Realized P&L from this exit
        """
        if roundtrip_id not in self.open_roundtrips:
            raise ValueError(f"RoundTrip {roundtrip_id} not found")
        
        roundtrip = self.open_roundtrips[roundtrip_id]
        
        # Validate shares
        if shares > roundtrip.remaining_shares:
            raise ValueError(
                f"Cannot exit {shares} shares, only {roundtrip.remaining_shares} available"
            )
        
        # Calculate proceeds
        exit_value = self.transaction_cost.calculate_exit_value(shares, price)
        
        # Create transaction
        transaction = Transaction(
            id=str(uuid4()),
            roundtrip_id=roundtrip_id,
            ticker=roundtrip.ticker,
            date=date,
            transaction_type="reduce",
            shares=shares,
            price=price,
            net_amount=exit_value,  # Positive (cash in)
            reason=reason
        )
        
        # Calculate P&L before updating
        cost_of_shares_sold = roundtrip.average_entry_price * shares
        realized_pnl = exit_value - cost_of_shares_sold
        
        # Update
        roundtrip.add_transaction(transaction)
        self.cash += exit_value
        self.transaction_log.append(transaction)
        
        # If fully closed, move to closed list
        if roundtrip.remaining_shares == 0:
            self.closed_roundtrips.append(roundtrip)
            del self.open_roundtrips[roundtrip_id]
        
        return realized_pnl
    
    def close_position(self,
                      roundtrip_id: str,
                      date: date,
                      price: float,
                      reason: str) -> float:
        """
        Fully close RoundTrip.
        
        Returns:
            Realized P&L
        """
        if roundtrip_id not in self.open_roundtrips:
            raise ValueError(f"RoundTrip {roundtrip_id} not found")
        
        roundtrip = self.open_roundtrips[roundtrip_id]
        return self.reduce_position(
            roundtrip_id, date, price, 
            roundtrip.remaining_shares, reason
        )
    
    def get_total_value(self, date: date, current_prices: Dict[str, float]) -> float:
        """
        Calculate total portfolio value.
        
        Args:
            current_prices: Dict of {ticker: price}
        
        Returns:
            Cash + market value of open positions
        """
        total = self.cash
        
        for roundtrip in self.open_roundtrips.values():
            price = current_prices.get(roundtrip.ticker)
            if price is not None:
                total += roundtrip.remaining_shares * price
            # If no price, position value = 0 (delisted/suspended)
        
        return total
    
    def record_equity(self, date: date, value: float):
        """Record daily portfolio value."""
        self.equity_history.append({
            'date': date,
            'value': value
        })
    
    def get_transaction_log_df(self):
        """Export transaction log as DataFrame."""
        import pandas as pd
        return pd.DataFrame([t.to_dict() for t in self.transaction_log])
```

**Tests needed:**
- Open position (success and failure cases)
- Add to position (DCA)
- Reduce position (partial exit)
- Close position (full exit)
- Get total value (with and without prices)
- Fractional vs whole shares
- Multiple positions same ticker
- Run out of cash
- Try to exit more shares than available
- Record equity

---

## 5. DataProvider

> **💡 GENERALIZATION NOTE:** This example shows yfinance implementation.
> In practice, use **abstract base class** with concrete providers (YFinanceProvider, AlpacaProvider, etc.)
> to support multiple data sources. Add methods for ALL useful data (not just earnings):
> - Fundamentals (P/E, market cap, sector)
> - Ownership (institutional holders)
> - Corporate actions (splits, dividends)
> - Financials (income statement, balance sheet)
> The backtester should work with ANY data source via the abstract interface.

```python
import yfinance as yf
import pandas as pd
from typing import List, Dict, Optional
from datetime import date, timedelta

class DataProvider:
    """
    Fetch and cache market data from yfinance.
    """
    def __init__(self):
        self._price_cache: Dict[str, pd.DataFrame] = {}
        self._ohlcv_cache: Dict[str, pd.DataFrame] = {}
        self._earnings_cache: Dict[str, pd.DataFrame] = {}
    
    def get_prices(self, tickers: List[str], start: date, end: date) -> pd.DataFrame:
        """
        Get daily close prices.
        
        Returns:
            DataFrame with index=dates, columns=tickers
        """
        # Convert to list if single ticker
        if isinstance(tickers, str):
            tickers = [tickers]
        
        # Fetch all at once
        data = yf.download(
            tickers,
            start=start,
            end=end + timedelta(days=1),  # yf is exclusive on end
            progress=False,
            auto_adjust=True
        )
        
        if data.empty:
            return pd.DataFrame()
        
        # Extract close prices
        if len(tickers) == 1:
            # Single ticker returns Series
            prices = pd.DataFrame({tickers[0]: data['Close']})
        else:
            # Multiple tickers
            prices = data['Close']
        
        return prices
    
    def get_ohlcv(self, tickers: List[str], start: date, end: date) -> Dict[str, pd.DataFrame]:
        """
        Get OHLCV data.
        
        Returns:
            Dict of {ticker: DataFrame with OHLCV columns}
        """
        if isinstance(tickers, str):
            tickers = [tickers]
        
        result = {}
        
        for ticker in tickers:
            # Check cache
            if ticker in self._ohlcv_cache:
                cached = self._ohlcv_cache[ticker]
                if start in cached.index and end in cached.index:
                    result[ticker] = cached.loc[start:end]
                    continue
            
            # Fetch
            data = yf.download(
                ticker,
                start=start,
                end=end + timedelta(days=1),
                progress=False,
                auto_adjust=True
            )
            
            if not data.empty:
                self._ohlcv_cache[ticker] = data
                result[ticker] = data
        
        return result
    
    def get_bar(self, ticker: str, date: date) -> Optional[Dict[str, float]]:
        """
        Get single day's OHLCV for one ticker.
        
        Returns:
            Dict with keys: open, high, low, close, volume
            None if no data
        """
        # Try to get from cache first
        if ticker in self._ohlcv_cache:
            df = self._ohlcv_cache[ticker]
            if date in df.index:
                row = df.loc[date]
                return {
                    'open': row['Open'],
                    'high': row['High'],
                    'low': row['Low'],
                    'close': row['Close'],
                    'volume': row['Volume']
                }
        
        # Fetch just this date
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
        return {
            'open': row['Open'],
            'high': row['High'],
            'low': row['Low'],
            'close': row['Close'],
            'volume': row['Volume']
        }
    
    def get_earnings_surprise(self, ticker: str, as_of_date: date) -> Optional[float]:
        """
        Get most recent earnings surprise as of date.
        
        Returns:
            Surprise percentage (0.05 = 5% beat), or None
        
        Fixes V0 bugs:
        - Handle negative estimates correctly
        - Validate earnings freshness
        """
        # Fetch earnings
        stock = yf.Ticker(ticker)
        earnings = stock.earnings_dates
        
        if earnings is None or earnings.empty:
            return None
        
        # Filter to past earnings only
        as_of_datetime = pd.Timestamp(as_of_date)
        past_earnings = earnings[earnings.index < as_of_datetime]
        
        if past_earnings.empty:
            return None
        
        # Sort explicitly (don't assume yfinance order)
        past_earnings = past_earnings.sort_index(ascending=False)
        
        # Get most recent
        most_recent = past_earnings.iloc[0]
        
        # Validate freshness (within 90 days)
        days_ago = (as_of_datetime - most_recent.name).days
        if days_ago > 90:
            return None
        
        # Extract data
        reported = most_recent.get('Reported EPS')
        estimate = most_recent.get('EPS Estimate')
        
        if pd.isna(reported) or pd.isna(estimate):
            return None
        
        # Calculate surprise (fix for negative estimates)
        if estimate >= 0:
            surprise = (reported - estimate) / estimate
        else:
            # For negative estimates: worse = more negative
            # If estimate = -0.50 and reported = -0.30, that's better (30% beat)
            # If estimate = -0.50 and reported = -0.70, that's worse (miss)
            surprise = -((reported - estimate) / abs(estimate))
        
        return surprise
    
    def is_tradeable(self, ticker: str, date: date) -> bool:
        """Check if ticker has valid price data on date."""
        bar = self.get_bar(ticker, date)
        return bar is not None
```

**Tests needed:**
- Fetch prices for single ticker
- Fetch prices for multiple tickers
- Fetch OHLCV data
- Get single bar
- Earnings surprise (positive and negative EPS)
- Earnings surprise freshness check
- Missing data handling
- Cache hit/miss

---

## 6. EntryRule (Base + Concrete Rules)

> **✅ IMPLEMENTATION NOTE (Phase 2B Complete):**
> The entry rule system has been implemented with a **Calculation + Condition** composable architecture.
> This separates data extraction (Calculation) from decision logic (Condition), enabling:
> - Independent testing of calculations
> - Reusable calculations across multiple rules
> - Easy analysis-to-strategy pipeline (test in notebooks, then convert to rules)
> - Adding new calculations/conditions without touching base classes
>
> **Files implemented:**
> - `backtester/calculation.py` - Calculation ABC + EarningsSurprise, DayChange, PERatio, InstitutionalOwnership
> - `backtester/condition.py` - Condition ABC + GreaterThan, LessThan, Between
> - `backtester/entryrule.py` - Signal, EntryRule, CompositeEntryRule
> - Tests: 110/110 passing (100%)
>
> **The SPEC examples below show the ORIGINAL hardcoded pattern. The ACTUAL implementation is more flexible.**

> **💡 GENERALIZATION NOTE:** Examples show EarningsBeat, RedDay, GreenDay rules.
> These are **sample implementations** to demonstrate the pattern.
> The system should support ANY entry logic:
> - Technical indicators (RSI, MACD, moving averages)
> - Fundamental filters (P/E ratio, revenue growth)
> - Alternative data (sentiment, insider trades, options flow)
> - Custom user logic
> Keep the ABC flexible - EntryRules just need to return Signal or None.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class Signal:
    """Entry signal with metadata."""
    ticker: str
    date: date
    signal_type: str
    metadata: dict
    priority: float  # For ranking when multiple signals

class EntryRule(ABC):
    """Base class for entry rules."""
    
    @abstractmethod
    def should_enter(self, 
                    ticker: str, 
                    date: date, 
                    data_provider: DataProvider) -> Optional[Signal]:
        """
        Check if should enter position.
        
        Returns:
            Signal if condition met, None otherwise
        """
        pass
    
    @abstractmethod
    def to_dict(self) -> dict:
        """Serialize for config."""
        pass
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> 'EntryRule':
        """Deserialize from config."""
        pass

# Concrete implementations

class EarningsBeatRule(EntryRule):
    """Enter if earnings beat by threshold."""
    
    def __init__(self, eps_threshold: float):
        self.eps_threshold = eps_threshold
    
    def should_enter(self, ticker, date, data_provider):
        surprise = data_provider.get_earnings_surprise(ticker, date)
        
        if surprise is None:
            return None
        
        if surprise >= self.eps_threshold:
            return Signal(
                ticker=ticker,
                date=date,
                signal_type="earnings_beat",
                metadata={"surprise_pct": surprise},
                priority=surprise
            )
        
        return None
    
    def to_dict(self):
        return {
            "type": "EarningsBeatRule",
            "params": {"eps_threshold": self.eps_threshold}
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(eps_threshold=data["params"]["eps_threshold"])

class RedDayRule(EntryRule):
    """Enter if close < open (red candle)."""
    
    def should_enter(self, ticker, date, data_provider):
        bar = data_provider.get_bar(ticker, date)
        
        if bar is None:
            return None
        
        if bar['close'] < bar['open']:
            red_pct = (bar['open'] - bar['close']) / bar['open']
            return Signal(
                ticker=ticker,
                date=date,
                signal_type="red_day",
                metadata={"red_pct": red_pct},
                priority=red_pct
            )
        
        return None
    
    def to_dict(self):
        return {"type": "RedDayRule", "params": {}}
    
    @classmethod
    def from_dict(cls, data):
        return cls()

class GreenDayRule(EntryRule):
    """Enter if close > open (green candle)."""
    
    def should_enter(self, ticker, date, data_provider):
        bar = data_provider.get_bar(ticker, date)
        
        if bar is None:
            return None
        
        if bar['close'] > bar['open']:
            green_pct = (bar['close'] - bar['open']) / bar['open']
            return Signal(
                ticker=ticker,
                date=date,
                signal_type="green_day",
                metadata={"green_pct": green_pct},
                priority=green_pct
            )
        
        return None
    
    def to_dict(self):
        return {"type": "GreenDayRule", "params": {}}
    
    @classmethod
    def from_dict(cls, data):
        return cls()

# Add more as needed:
# - VolumeSpike
# - PriceAboveMA
# - etc.
```

**Tests needed:**
- Each concrete rule with valid signal
- Each rule with no signal
- Signal priority calculation
- Serialization round-trip

---

## 7. ExitRule (Base + Concrete + Composite)

> **✅ IMPLEMENTATION NOTE (Phase 3 Complete):**
> Exit rules system has been fully implemented with 4 concrete rules + CompositeExitRule.
> **Files implemented:**
> - `backtester/exitrule.py` - ExitRule ABC + TimeBasedExit, StopLossExit, TrailingStopExit, ProfitTargetExit, CompositeExitRule
> - Tests: 57/57 passing (100%)
> - Total system tests: 336/336 passing (100%)
>
> **Key features:**
> - Stateful tracking (TrailingStopExit tracks peak prices)
> - Partial exits (exit_portion 0.0-1.0)
> - Priority ordering (CompositeExitRule, first match wins)
> - Full serialization support

> **💡 GENERALIZATION NOTE:** Examples show time-based, stop-loss, trailing-stop, profit-target exits.
> These are **common patterns**, not exhaustive.
> The system should support ANY exit logic:
> - Technical signals (RSI overbought, MACD crossover)
> - Fundamental changes (earnings miss, downgrades)
> - Risk management (volatility spikes, correlation breaks)
> - Custom user logic
> CompositeExitRule allows combining multiple exit conditions with priority ordering.

```python
from typing import Tuple, List

class ExitRule(ABC):
    """Base class for exit rules."""
    
    @abstractmethod
    def should_exit(self,
                   roundtrip: RoundTrip,
                   date: date,
                   price: float) -> Tuple[bool, float, str]:
        """
        Check if should exit position.
        
        Returns:
            (should_exit, exit_portion, reason)
            - should_exit: bool
            - exit_portion: 0.0 to 1.0 (1.0 = full exit)
            - reason: string like "stop_loss", "time_exit"
        """
        pass
    
    @abstractmethod
    def to_dict(self) -> dict:
        pass
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> 'ExitRule':
        pass

# Concrete implementations

class TimeBasedExit(ExitRule):
    """Exit after N days."""
    
    def __init__(self, holding_days: int):
        self.holding_days = holding_days
    
    def should_exit(self, roundtrip, date, price):
        if roundtrip.get_holding_days(date) >= self.holding_days:
            return (True, 1.0, "time_exit")
        return (False, 0, "")
    
    def to_dict(self):
        return {
            "type": "TimeBasedExit",
            "params": {"holding_days": self.holding_days}
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(holding_days=data["params"]["holding_days"])

class StopLossExit(ExitRule):
    """Exit if loss exceeds threshold."""
    
    def __init__(self, stop_pct: float):
        self.stop_pct = stop_pct
    
    def should_exit(self, roundtrip, date, price):
        avg_entry = roundtrip.average_entry_price
        pnl_pct = (price - avg_entry) / avg_entry
        
        if pnl_pct <= -self.stop_pct:
            return (True, 1.0, "stop_loss")
        
        return (False, 0, "")
    
    def to_dict(self):
        return {
            "type": "StopLossExit",
            "params": {"stop_pct": self.stop_pct}
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(stop_pct=data["params"]["stop_pct"])

class TrailingStopExit(ExitRule):
    """Exit if price drops X% from peak."""
    
    def __init__(self, trailing_pct: float):
        self.trailing_pct = trailing_pct
        self._peak_prices = {}  # roundtrip_id -> peak_price
    
    def should_exit(self, roundtrip, date, price):
        # Track peak price for this position
        if roundtrip.id not in self._peak_prices:
            self._peak_prices[roundtrip.id] = roundtrip.average_entry_price
        
        # Update peak
        if price > self._peak_prices[roundtrip.id]:
            self._peak_prices[roundtrip.id] = price
        
        # Check trailing stop
        peak = self._peak_prices[roundtrip.id]
        drawdown = (peak - price) / peak
        
        if drawdown >= self.trailing_pct:
            return (True, 1.0, "trailing_stop")
        
        return (False, 0, "")
    
    def to_dict(self):
        return {
            "type": "TrailingStopExit",
            "params": {"trailing_pct": self.trailing_pct}
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(trailing_pct=data["params"]["trailing_pct"])

class ProfitTargetExit(ExitRule):
    """Exit when profit exceeds threshold."""
    
    def __init__(self, target_pct: float, exit_portion: float = 1.0):
        self.target_pct = target_pct
        self.exit_portion = exit_portion  # Can do partial exits
    
    def should_exit(self, roundtrip, date, price):
        avg_entry = roundtrip.average_entry_price
        pnl_pct = (price - avg_entry) / avg_entry
        
        if pnl_pct >= self.target_pct:
            return (True, self.exit_portion, "profit_target")
        
        return (False, 0, "")
    
    def to_dict(self):
        return {
            "type": "ProfitTargetExit",
            "params": {
                "target_pct": self.target_pct,
                "exit_portion": self.exit_portion
            }
        }
    
    @classmethod
    def from_dict(cls, data):
        params = data["params"]
        return cls(
            target_pct=params["target_pct"],
            exit_portion=params.get("exit_portion", 1.0)
        )

# The critical one: CompositeExitRule

class CompositeExitRule(ExitRule):
    """
    Evaluate multiple exit rules in priority order.
    First rule that triggers wins.
    """
    
    def __init__(self, rules: List[Tuple[ExitRule, float]]):
        """
        Args:
            rules: List of (ExitRule, exit_portion) tuples
                   Evaluated in order, first match wins
        """
        self.rules = rules
    
    def should_exit(self, roundtrip, date, price):
        # Try each rule in order
        for rule, portion in self.rules:
            should_exit, _, reason = rule.should_exit(roundtrip, date, price)
            
            if should_exit:
                # Use configured portion, not rule's portion
                return (True, portion, reason)
        
        return (False, 0, "")
    
    def to_dict(self):
        return {
            "type": "CompositeExitRule",
            "rules": [
                {
                    "rule": rule.to_dict(),
                    "portion": portion
                }
                for rule, portion in self.rules
            ]
        }
    
    @classmethod
    def from_dict(cls, data):
        rules = []
        for rule_data in data["rules"]:
            # Recursively construct rule
            rule = _construct_exit_rule(rule_data["rule"])
            portion = rule_data["portion"]
            rules.append((rule, portion))
        
        return cls(rules)

def _construct_exit_rule(data: dict) -> ExitRule:
    """Helper to construct exit rule from dict."""
    rule_type = data["type"]
    
    if rule_type == "TimeBasedExit":
        return TimeBasedExit.from_dict(data)
    elif rule_type == "StopLossExit":
        return StopLossExit.from_dict(data)
    elif rule_type == "TrailingStopExit":
        return TrailingStopExit.from_dict(data)
    elif rule_type == "ProfitTargetExit":
        return ProfitTargetExit.from_dict(data)
    elif rule_type == "CompositeExitRule":
        return CompositeExitRule.from_dict(data)
    else:
        raise ValueError(f"Unknown exit rule type: {rule_type}")
```

**Tests needed:**
- Each concrete rule triggers correctly
- TimeBasedExit at exact day threshold
- StopLossExit at exact threshold
- TrailingStopExit tracks peak correctly
- ProfitTargetExit with partial exit
- CompositeExitRule priority evaluation
- CompositeExitRule with nested composite
- Serialization round-trip for all rules

---

## 8. PositionSizer

```python
class PositionSizer:
    """Calculate number of shares to buy."""
    
    def calculate_shares(self,
                        method: str,
                        portfolio_value: float,
                        available_cash: float,
                        price: float,
                        params: dict,
                        max_positions: int) -> float:
        """
        Calculate shares based on sizing method.
        
        Args:
            method: "equal_weight", "fixed_dollar", "percent_portfolio", "fixed_shares"
            portfolio_value: Total portfolio value
            available_cash: Cash available for new positions
            price: Current stock price
            params: Method-specific parameters
            max_positions: Max concurrent positions
        
        Returns:
            Number of shares (float for fractional support)
        """
        if method == "equal_weight":
            # Use available cash, not total portfolio (V0 bug fix)
            allocation = available_cash / max_positions
            shares = allocation / price
        
        elif method == "fixed_dollar":
            amount = params.get("amount", 0)
            shares = amount / price
        
        elif method == "percent_portfolio":
            pct = params.get("pct", 0)
            allocation = portfolio_value * pct
            shares = allocation / price
        
        elif method == "fixed_shares":
            shares = params.get("shares", 0)
        
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Return 0 if negative or too small
        return shares if shares > 0 else 0.0
    
    def to_dict(self):
        return {"type": "PositionSizer"}
    
    @classmethod
    def from_dict(cls, data):
        return cls()
```

**Tests needed:**
- Equal weight calculation
- Fixed dollar
- Percent portfolio
- Fixed shares
- Returns 0 for invalid inputs
- Fractional shares returned

---

## 9. Strategy

```python
import yaml

class Strategy:
    """Bundle entry rule, exit rule, sizer, and universe."""
    
    def __init__(self,
                 name: str,
                 entry_rule: EntryRule,
                 exit_rule: ExitRule,
                 position_sizer: PositionSizer,
                 universe: List[str],
                 description: str = ""):
        self.name = name
        self.entry_rule = entry_rule
        self.exit_rule = exit_rule
        self.position_sizer = position_sizer
        self.universe = universe
        self.description = description
    
    def generate_signals(self, date: date, data_provider: DataProvider) -> List[Signal]:
        """Generate and rank signals for universe."""
        signals = []
        
        for ticker in self.universe:
            signal = self.entry_rule.should_enter(ticker, date, data_provider)
            if signal:
                signals.append(signal)
        
        # Sort by priority (highest first)
        signals.sort(key=lambda s: s.priority, reverse=True)
        
        return signals
    
    def validate(self):
        """Validate configuration."""
        if not self.universe:
            raise ValueError("Universe cannot be empty")
        if self.entry_rule is None:
            raise ValueError("Entry rule required")
        if self.exit_rule is None:
            raise ValueError("Exit rule required")
        if self.position_sizer is None:
            raise ValueError("Position sizer required")
        return True
    
    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "entry_rule": self.entry_rule.to_dict(),
            "exit_rule": self.exit_rule.to_dict(),
            "position_sizer": self.position_sizer.to_dict(),
            "universe": self.universe
        }
    
    @classmethod
    def from_dict(cls, data):
        # Construct entry rule
        entry_rule = _construct_entry_rule(data["entry_rule"])
        
        # Construct exit rule
        exit_rule = _construct_exit_rule(data["exit_rule"])
        
        # Construct position sizer
        position_sizer = PositionSizer.from_dict(data["position_sizer"])
        
        return cls(
            name=data["name"],
            entry_rule=entry_rule,
            exit_rule=exit_rule,
            position_sizer=position_sizer,
            universe=data["universe"],
            description=data.get("description", "")
        )
    
    def to_yaml(self, path: str):
        """Save strategy to YAML file."""
        with open(path, 'w') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)
    
    @classmethod
    def from_yaml(cls, path: str):
        """Load strategy from YAML file."""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)

def _construct_entry_rule(data: dict) -> EntryRule:
    """Helper to construct entry rule from dict."""
    rule_type = data["type"]
    
    if rule_type == "EarningsBeatRule":
        return EarningsBeatRule.from_dict(data)
    elif rule_type == "RedDayRule":
        return RedDayRule.from_dict(data)
    elif rule_type == "GreenDayRule":
        return GreenDayRule.from_dict(data)
    # Add more as needed
    else:
        raise ValueError(f"Unknown entry rule type: {rule_type}")
```

**Tests needed:**
- Create strategy
- Generate signals
- Validate configuration
- Serialize to dict
- Deserialize from dict
- Save to YAML
- Load from YAML
- Round-trip YAML test

---

## 10. Backtester

```python
import logging
from tqdm import tqdm

class Backtester:
    """Main simulation engine."""
    
    def __init__(self,
                 strategy: Strategy,
                 portfolio: Portfolio,
                 data_provider: DataProvider,
                 start_date: date,
                 end_date: date):
        self.strategy = strategy
        self.portfolio = portfolio
        self.data_provider = data_provider
        self.start_date = start_date
        self.end_date = end_date
        self.logger = logging.getLogger("backtester")
    
    def run(self, show_progress: bool = True):
        """Run backtest and return Results."""
        # Validate
        self._validate()
        
        # Preload data
        self._preload_data()
        
        # Get trading days
        trading_days = self._get_trading_days()
        
        # Main loop
        iterator = tqdm(trading_days, desc="Backtesting") if show_progress else trading_days
        
        for day in iterator:
            self._process_day(day)
        
        from backtester.results import Results
        return Results(self.portfolio)
    
    def _validate(self):
        """Pre-flight checks."""
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        
        self.strategy.validate()
        
        self.logger.info(f"Backtest: {self.start_date} to {self.end_date}")
        self.logger.info(f"Universe: {len(self.strategy.universe)} tickers")
        self.logger.info(f"Capital: ${self.portfolio.starting_capital:,.2f}")
    
    def _preload_data(self):
        """Preload price data for universe."""
        self.logger.info("Preloading data...")
        
        self.price_data = self.data_provider.get_prices(
            self.strategy.universe,
            self.start_date,
            self.end_date
        )
        
        self.logger.info(f"Loaded {len(self.price_data)} days")
    
    def _get_trading_days(self):
        """Get list of trading days."""
        # Use SPY as calendar
        spy_prices = self.data_provider.get_prices(['SPY'], self.start_date, self.end_date)
        return spy_prices.index.tolist()
    
    def _process_day(self, current_date: date):
        """Process single trading day."""
        # Skip if no data
        if current_date not in self.price_data.index:
            return
        
        # Get universe tickers
        universe = self.strategy.universe
        
        # Build current prices dict
        day_prices = self.price_data.loc[current_date]
        current_prices = {}
        
        for ticker in universe:
            if ticker in day_prices.index and pd.notna(day_prices[ticker]):
                current_prices[ticker] = day_prices[ticker]
        
        # Add prices for open positions not in universe
        for roundtrip in list(self.portfolio.open_roundtrips.values()):
            if roundtrip.ticker not in current_prices:
                if roundtrip.ticker in day_prices.index and pd.notna(day_prices[roundtrip.ticker]):
                    current_prices[roundtrip.ticker] = day_prices[roundtrip.ticker]
        
        # 1. Check exits
        for rt_id, roundtrip in list(self.portfolio.open_roundtrips.items()):
            # Skip if no price
            if roundtrip.ticker not in current_prices:
                continue
            
            price = current_prices[roundtrip.ticker]
            
            # Check exit rule
            should_exit, exit_portion, reason = roundtrip.exit_rule.should_exit(
                roundtrip, current_date, price
            )
            
            if should_exit:
                if exit_portion >= 1.0:
                    # Full exit
                    self.portfolio.close_position(rt_id, current_date, price, reason)
                else:
                    # Partial exit
                    shares_to_exit = roundtrip.remaining_shares * exit_portion
                    self.portfolio.reduce_position(rt_id, current_date, price, 
                                                  shares_to_exit, reason)
        
        # 2. Generate signals
        signals = self.strategy.generate_signals(current_date, self.data_provider)
        
        # Filter signals with no price data
        signals = [s for s in signals if s.ticker in current_prices]
        
        # 3. Open positions
        for signal in signals:
            # Check room
            if not self.portfolio.can_open_position():
                break
            
            price = current_prices[signal.ticker]
            
            # Calculate shares
            shares = self.strategy.position_sizer.calculate_shares(
                method="equal_weight",  # Could make configurable
                portfolio_value=self.portfolio.get_total_value(current_date, current_prices),
                available_cash=self.portfolio.cash,
                price=price,
                params={},
                max_positions=self.portfolio.max_positions
            )
            
            if shares > 0:
                self.portfolio.open_position(
                    ticker=signal.ticker,
                    date=current_date,
                    price=price,
                    shares=shares,
                    exit_rule=self.strategy.exit_rule,
                    signal_metadata=signal.metadata
                )
        
        # 4. Record equity
        equity = self.portfolio.get_total_value(current_date, current_prices)
        self.portfolio.record_equity(current_date, equity)
```

**Tests needed:**
- Full backtest end-to-end
- Empty signals day
- All positions exit same day
- Portfolio full (can't open more)
- Missing price data handling
- Preload data caching

---

## 11. Results

```python
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

class Results:
    """Analyze backtest performance."""
    
    def __init__(self, portfolio: Portfolio):
        self.portfolio = portfolio
        self.roundtrips = portfolio.closed_roundtrips
        self.transaction_log = portfolio.transaction_log
        self.equity_curve = pd.DataFrame(portfolio.equity_history)
        self.starting_capital = portfolio.starting_capital
        
        if len(self.equity_curve) > 0:
            self.ending_capital = self.equity_curve['value'].iloc[-1]
        else:
            self.ending_capital = portfolio.cash
    
    # Basic metrics
    
    def total_return(self) -> float:
        """Total return as decimal."""
        return (self.ending_capital - self.starting_capital) / self.starting_capital
    
    def annualized_return(self) -> float:
        """CAGR."""
        if len(self.equity_curve) < 2:
            return 0.0
        
        days = (self.equity_curve['date'].iloc[-1] - 
                self.equity_curve['date'].iloc[0]).days
        years = days / 365.25
        
        return (self.ending_capital / self.starting_capital) ** (1 / years) - 1
    
    def win_rate(self) -> float:
        """Percentage of profitable trades."""
        if len(self.roundtrips) == 0:
            return 0.0
        
        winners = sum(1 for rt in self.roundtrips if rt.realized_pnl > 0)
        return winners / len(self.roundtrips)
    
    # Risk metrics
    
    def sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Annualized Sharpe ratio."""
        if len(self.equity_curve) < 2:
            return 0.0
        
        returns = self.equity_curve['value'].pct_change().dropna()
        
        excess_return = returns.mean() * 252 - risk_free_rate
        volatility = returns.std() * np.sqrt(252)
        
        return excess_return / volatility if volatility > 0 else 0.0
    
    def sortino_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Annualized Sortino ratio."""
        if len(self.equity_curve) < 2:
            return 0.0
        
        returns = self.equity_curve['value'].pct_change().dropna()
        downside_returns = returns[returns < 0]
        
        excess_return = returns.mean() * 252 - risk_free_rate
        downside_vol = downside_returns.std() * np.sqrt(252)
        
        return excess_return / downside_vol if downside_vol > 0 else 0.0
    
    def calmar_ratio(self) -> float:
        """Annualized return / max drawdown."""
        mdd = self.max_drawdown()
        if mdd == 0:
            return 0.0
        return self.annualized_return() / mdd
    
    def max_drawdown(self) -> float:
        """Maximum peak-to-trough decline."""
        if len(self.equity_curve) == 0:
            return 0.0
        
        values = self.equity_curve['value']
        max_dd = 0.0
        peak = values.iloc[0]
        
        for value in values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            if drawdown > max_dd:
                max_dd = drawdown
        
        return max_dd
    
    def max_drawdown_duration(self) -> int:
        """Longest drawdown period in days."""
        if len(self.equity_curve) == 0:
            return 0
        
        values = self.equity_curve['value']
        dates = self.equity_curve['date']
        
        peak = values.iloc[0]
        peak_date = dates.iloc[0]
        max_duration = 0
        
        for value, dt in zip(values, dates):
            if value >= peak:
                peak = value
                peak_date = dt
            else:
                duration = (dt - peak_date).days
                if duration > max_duration:
                    max_duration = duration
        
        return max_duration
    
    # Trade statistics
    
    def profit_factor(self) -> float:
        """Gross profit / gross loss."""
        if len(self.roundtrips) == 0:
            return 0.0
        
        gross_profit = sum(rt.realized_pnl for rt in self.roundtrips if rt.realized_pnl > 0)
        gross_loss = sum(abs(rt.realized_pnl) for rt in self.roundtrips if rt.realized_pnl < 0)
        
        return gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    def average_win(self) -> float:
        """Average profit of winning trades."""
        winners = [rt.realized_pnl for rt in self.roundtrips if rt.realized_pnl > 0]
        return sum(winners) / len(winners) if winners else 0.0
    
    def average_loss(self) -> float:
        """Average loss of losing trades."""
        losers = [rt.realized_pnl for rt in self.roundtrips if rt.realized_pnl < 0]
        return sum(losers) / len(losers) if losers else 0.0
    
    def win_loss_ratio(self) -> float:
        """Average win / average loss."""
        avg_loss = self.average_loss()
        if avg_loss == 0:
            return 0.0
        return self.average_win() / abs(avg_loss)
    
    # Data exports
    
    def get_transaction_log_df(self) -> pd.DataFrame:
        """Export transaction log."""
        return pd.DataFrame([t.to_dict() for t in self.transaction_log])
    
    def get_roundtrips_df(self) -> pd.DataFrame:
        """Export roundtrips summary."""
        return pd.DataFrame([{
            'id': rt.id,
            'ticker': rt.ticker,
            'entry_date': rt.transactions[0].date,
            'exit_date': rt.transactions[-1].date if not rt.is_open else None,
            'shares': rt.total_shares,
            'avg_entry_price': rt.average_entry_price,
            'realized_pnl': rt.realized_pnl,
            'holding_days': (rt.transactions[-1].date - rt.transactions[0].date).days 
                           if not rt.is_open else None
        } for rt in self.roundtrips])
    
    def get_monthly_returns(self) -> pd.DataFrame:
        """Monthly returns."""
        if len(self.equity_curve) == 0:
            return pd.DataFrame()
        
        df = self.equity_curve.copy()
        df['month'] = pd.to_datetime(df['date']).dt.to_period('M')
        
        monthly = df.groupby('month')['value'].agg(['first', 'last'])
        monthly['return'] = (monthly['last'] - monthly['first']) / monthly['first']
        
        return monthly
    
    # Visualizations
    
    def plot_equity_curve(self, save_path: str = None, show: bool = True):
        """Plot equity curve."""
        plt.figure(figsize=(12, 6))
        plt.plot(self.equity_curve['date'], self.equity_curve['value'])
        plt.xlabel('Date')
        plt.ylabel('Portfolio Value ($)')
        plt.title('Equity Curve')
        plt.grid(True)
        
        if save_path:
            plt.savefig(save_path)
        if show:
            plt.show()
    
    def plot_drawdown(self, save_path: str = None, show: bool = True):
        """Plot drawdown over time."""
        values = self.equity_curve['value']
        dates = self.equity_curve['date']
        
        # Calculate running drawdown
        peak = values.expanding().max()
        drawdown = (values - peak) / peak
        
        plt.figure(figsize=(12, 6))
        plt.fill_between(dates, drawdown, 0, alpha=0.3, color='red')
        plt.plot(dates, drawdown, color='red')
        plt.xlabel('Date')
        plt.ylabel('Drawdown')
        plt.title('Drawdown Over Time')
        plt.grid(True)
        
        if save_path:
            plt.savefig(save_path)
        if show:
            plt.show()
    
    def summary(self) -> str:
        """Print-friendly summary."""
        return f"""
=== Backtest Results ===
Starting Capital: ${self.starting_capital:,.2f}
Ending Capital: ${self.ending_capital:,.2f}
Total Return: {self.total_return()*100:.2f}%
Annualized Return: {self.annualized_return()*100:.2f}%

Risk Metrics:
  Sharpe Ratio: {self.sharpe_ratio():.2f}
  Sortino Ratio: {self.sortino_ratio():.2f}
  Calmar Ratio: {self.calmar_ratio():.2f}
  Max Drawdown: {self.max_drawdown()*100:.2f}%
  Max DD Duration: {self.max_drawdown_duration()} days

Trade Statistics:
  Total Trades: {len(self.roundtrips)}
  Win Rate: {self.win_rate()*100:.1f}%
  Profit Factor: {self.profit_factor():.2f}
  Average Win: ${self.average_win():.2f}
  Average Loss: ${self.average_loss():.2f}
  Win/Loss Ratio: {self.win_loss_ratio():.2f}
"""
```

**Tests needed:**
- All metrics with known data
- Edge cases (zero trades, all winners, all losers)
- Export functions
- Visualizations render
- Summary format

---

## YAML Config Example

> **💡 GENERALIZATION NOTE:** This is ONE example strategy (Mag7 DCA on red days).
> The config system should support:
> - ANY universe (not just Mag7)
> - ANY entry/exit rules
> - ANY combination of rules via CompositeExitRule
> - User-defined custom rules
> This example demonstrates the YAML structure, not the only strategy to build.

```yaml
# mag7_dca_strategy.yaml

name: "Mag7 DCA on Red Days"
description: "Buy Magnificent 7 stocks on red days with stop loss"

entry_rule:
  type: RedDayRule
  params: {}

exit_rule:
  type: CompositeExitRule
  rules:
    - rule:
        type: StopLossExit
        params:
          stop_pct: 0.08
      portion: 1.0
    - rule:
        type: TimeBasedExit
        params:
          holding_days: 30
      portion: 1.0

position_sizer:
  type: PositionSizer

universe:
  - AAPL
  - MSFT
  - GOOGL
  - AMZN
  - NVDA
  - META
  - TSLA
```

---

## Implementation Timeline

**Week 1:** Transaction + RoundTrip + tests
**Week 2:** Portfolio refactor + tests  
**Week 3:** Fractional shares + integration tests
**Week 4:** DataProvider OHLCV + tests
**Week 5:** EntryRules (3-4 rules) + tests
**Week 6:** ExitRules + CompositeExitRule + tests
**Week 7:** Backtester updates + tests
**Week 8:** Results enhancements + tests
**Week 9:** YAML config + serialization + tests
**Week 10:** Visualizations + documentation
**Week 11:** Bug fixes + polish

---

## Questions?

Anything unclear before you start building?