from typing import List
from dataclasses import dataclass, field
from uuid import uuid4
from backtester.transaction import Transaction

@dataclass
class RoundTrip:
    id: str = field(default_factory=lambda: str(uuid4()))
    ticker: str = ""
    transactions: List[Transaction] = field(default_factory=list)
    exit_rule: 'ExitRule' = None #will implement later
    entry_signal_metadata: dict = field(default_factory=dict)
    _total_cost: float = 0.0
    _total_proceeds: float = 0.0

    def add_transaction(self, txn: Transaction):
        self.transactions.append(txn)
        if txn.transaction_type in ["open", "add"]:
            self._total_cost += abs(txn.net_amount)
        else:
            self._total_proceeds += txn.net_amount

    @property
    def is_open(self) -> bool:
        return self.remaining_shares > 0

    @property
    def total_shares(self) -> float:
        return sum(t.shares for t in self.transactions if t.transaction_type in ["open", "add"])

    @property
    def remaining_shares(self) -> float:
        entries = sum(t.shares for t in self.transactions if t.transaction_type in ["open", "add"])
        exits = sum(t.shares for t in self.transactions if t.transaction_type in ["reduce", "close"])
        return entries - exits

    @property
    def average_entry_price(self) -> float:
        total_shares = self.total_shares
        if total_shares == 0:
            return 0.0
        return self._total_cost / total_shares

    @property
    def realized_pnl(self) -> float:
        return self._total_proceeds - self._total_cost

    def get_unrealized_pnl(self, current_price: float) -> float:
        if self.remaining_shares == 0:
            return 0.0
        current_value = self.remaining_shares * current_price
        cost_basis = self.remaining_shares * self.average_entry_price
        return current_value - cost_basis

    def get_holding_days(self, current_date):
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