from dataclasses import dataclass, field
from datetime import date
from uuid import uuid4

@dataclass(frozen=True)
class Transaction:
    id: str = field(default_factory=lambda: str(uuid4()))
    roundtrip_id: str = ""
    ticker: str = ""
    date: date = None
    transaction_type: str = ""
    shares: float = 0.0
    price: float = 0.0
    net_amount: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "roundtrip_id": self.roundtrip_id,
            "ticker": self.ticker,
            "date": self.date.isoformat() if self.date else None,
            "transaction_type": self.transaction_type,
            "shares": self.shares,
            "price": self.price,
            "net_amount": self.net_amount,
            "reason": self.reason
        }