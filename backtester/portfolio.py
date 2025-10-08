from typing import Dict, List, Optional
from datetime import date
from uuid import uuid4
from backtester.transaction import Transaction
from backtester.roundtrip import RoundTrip
from backtester.transactioncost import TransactionCost

class Portfolio:
    def __init__(self, starting_capital: float, max_positions: int, transaction_cost: TransactionCost, fractional_shares: bool = True):
        self.starting_capital = starting_capital
        self.cash = starting_capital
        self.max_positions = max_positions
        self.transaction_cost = transaction_cost
        self.fractional_shares = fractional_shares
        self.open_roundtrips: Dict[str, RoundTrip] = {}
        self.closed_roundtrips: List[RoundTrip] = []
        self.transaction_log: List[Transaction] = []
        self.equity_history: List[dict] = []
    
    def can_open_position(self):
        return len(self.open_roundtrips) < self.max_positions
    
    def _round_shares(self, shares: float):
        if self.fractional_shares:
            return shares
        return float(int(shares))
    
    def record_equity(self, date: date, value: float):
        self.equity_history.append({
            'date': date,
            'value': value
        })

    def get_transaction_log_df(self):
        import pandas as pd
        return pd.DataFrame([t.to_dict() for t in self.transaction_log])
    
    def open_position(self,
                      ticker: str,
                      date: date,
                      price: float,
                      shares: float,
                      exit_rule: 'ExitRule',
                      signal_metadata: dict = None) -> Optional[RoundTrip]:
        shares = self._round_shares(shares)
        if shares <= 0:
            return None
        if not self.can_open_position():
            return None
        entry_cost = self.transaction_cost.calculate_entry_cost(shares, price)
        if entry_cost > self.cash:
            return None
        roundtrip_id = str(uuid4())

        transaction = Transaction(
            id=str(uuid4()),
            roundtrip_id=roundtrip_id,
            ticker=ticker,
            date=date,
            transaction_type="open",
            shares=shares,
            price=price,
            net_amount=-entry_cost,
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
        if roundtrip_id not in self.open_roundtrips:
            raise ValueError(f"RoundTrip {roundtrip_id} not found")
        
        roundtrip = self.open_roundtrips[roundtrip_id]
        shares = self._round_shares(shares)
        if shares <= 0:
            return False
        add_cost = self.transaction_cost.calculate_entry_cost(shares, price)
        if add_cost > self.cash:
            return False
        
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
        if roundtrip_id not in self.open_roundtrips:
            raise ValueError(f"RoundTrip {roundtrip_id} not found")
        roundtrip = self.open_roundtrips[roundtrip_id]

        if shares > roundtrip.remaining_shares:
            raise ValueError(
                f"Cannot exit {shares} shares, only {roundtrip.remaining_shares} available"
            )
        exit_value = self.transaction_cost.calculate_exit_value(shares, price)

        transaction = Transaction(
            id=str(uuid4()),
            roundtrip_id=roundtrip_id,
            ticker=roundtrip.ticker,
            date=date,
            transaction_type="reduce",
            shares=shares,
            price=price,
            net_amount=exit_value,
            reason=reason
        )
        cost_of_shares_sold = roundtrip.average_entry_price * shares
        realized_pnl = exit_value - cost_of_shares_sold
        roundtrip.add_transaction(transaction)
        self.cash += exit_value
        self.transaction_log.append(transaction)

        if roundtrip.remaining_shares == 0:
            self.closed_roundtrips.append(roundtrip)
            del self.open_roundtrips[roundtrip_id]
        return realized_pnl
    
    def close_position(self,
                       roundtrip_id: str,
                       date: date,
                       price: float,
                       reason: str) -> float:
        if roundtrip_id not in self.open_roundtrips:
            raise ValueError(f"RoundTrip {roundtrip_id} not found")
        roundtrip = self.open_roundtrips[roundtrip_id]
        return self.reduce_position(
            roundtrip_id, date, price, roundtrip.remaining_shares, reason)
    
    def get_total_value(self, date: date, current_prices: Dict[str, float]) -> float:
        total = self.cash
        for roundtrip in self.open_roundtrips.values():
            price = current_prices.get(roundtrip.ticker)
            if price is not None:
                total += roundtrip.remaining_shares * price
        return total