# backtester/exitrule.py

from abc import ABC, abstractmethod
from typing import Tuple, List
from datetime import date


class ExitRule(ABC):
    """
    Base class for exit rules.

    Exit rules determine when to close positions based on various criteria
    (time, profit/loss, technical signals, etc.).
    """

    @abstractmethod
    def should_exit(self,
                   roundtrip,  # RoundTrip type hint causes circular import
                   date: date,
                   price: float) -> Tuple[bool, float, str]:
        """
        Check if should exit position.

        Args:
            roundtrip: RoundTrip object with position context
            date: Current date
            price: Current price

        Returns:
            Tuple of (should_exit, exit_portion, reason)
            - should_exit: bool - True if exit condition met
            - exit_portion: float - 0.0 to 1.0 (1.0 = full exit, 0.5 = exit half)
            - reason: str - Exit reason for transaction log ("stop_loss", "time_exit", etc.)
        """
        pass

    @abstractmethod
    def to_dict(self) -> dict:
        """Serialize for config."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> 'ExitRule':
        """Deserialize from config."""
        pass


class TimeBasedExit(ExitRule):
    """Exit after holding for N days."""

    def __init__(self, holding_days: int):
        """
        Args:
            holding_days: Number of days to hold before exiting
        """
        if holding_days <= 0:
            raise ValueError(f"holding_days must be positive, got {holding_days}")
        self.holding_days = holding_days

    def should_exit(self, roundtrip, date, price):
        """Exit if holding period exceeds threshold."""
        if roundtrip.get_holding_days(date) >= self.holding_days:
            return (True, 1.0, "time_exit")
        return (False, 0.0, "")

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
        """
        Args:
            stop_pct: Stop loss as decimal (0.08 = 8% loss triggers exit)
        """
        if stop_pct <= 0:
            raise ValueError(f"stop_pct must be positive, got {stop_pct}")
        self.stop_pct = stop_pct

    def should_exit(self, roundtrip, date, price):
        """Exit if P&L percentage drops below -stop_pct."""
        avg_entry = roundtrip.average_entry_price
        if avg_entry <= 0:
            return (False, 0.0, "")

        pnl_pct = (price - avg_entry) / avg_entry

        if pnl_pct <= -self.stop_pct:
            return (True, 1.0, "stop_loss")
        return (False, 0.0, "")

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
        """
        Args:
            trailing_pct: Trailing stop as decimal (0.10 = 10% drop from peak triggers exit)
        """
        if trailing_pct <= 0:
            raise ValueError(f"trailing_pct must be positive, got {trailing_pct}")
        self.trailing_pct = trailing_pct
        self._peak_prices = {}  # roundtrip_id -> peak_price

    def should_exit(self, roundtrip, date, price):
        """Exit if price drops trailing_pct% from peak."""
        # Track peak price for this position
        if roundtrip.id not in self._peak_prices:
            self._peak_prices[roundtrip.id] = roundtrip.average_entry_price

        # Update peak if current price is higher
        if price > self._peak_prices[roundtrip.id]:
            self._peak_prices[roundtrip.id] = price

        # Check trailing stop
        peak = self._peak_prices[roundtrip.id]
        if peak <= 0:
            return (False, 0.0, "")

        drawdown = (peak - price) / peak

        if drawdown >= self.trailing_pct:
            return (True, 1.0, "trailing_stop")
        return (False, 0.0, "")

    def to_dict(self):
        return {
            "type": "TrailingStopExit",
            "params": {"trailing_pct": self.trailing_pct}
        }

    @classmethod
    def from_dict(cls, data):
        return cls(trailing_pct=data["params"]["trailing_pct"])


class ProfitTargetExit(ExitRule):
    """Exit when profit target reached."""

    def __init__(self, target_pct: float, exit_portion: float = 1.0):
        """
        Args:
            target_pct: Profit target as decimal (0.20 = 20% gain triggers exit)
            exit_portion: Portion to exit (0.5 = exit half position, 1.0 = full exit)
        """
        if target_pct <= 0:
            raise ValueError(f"target_pct must be positive, got {target_pct}")
        if not 0.0 < exit_portion <= 1.0:
            raise ValueError(f"exit_portion must be in (0, 1], got {exit_portion}")
        self.target_pct = target_pct
        self.exit_portion = exit_portion

    def should_exit(self, roundtrip, date, price):
        """Exit if P&L percentage exceeds target_pct."""
        avg_entry = roundtrip.average_entry_price
        if avg_entry <= 0:
            return (False, 0.0, "")

        pnl_pct = (price - avg_entry) / avg_entry

        if pnl_pct >= self.target_pct:
            return (True, self.exit_portion, "profit_target")
        return (False, 0.0, "")

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


class CompositeExitRule(ExitRule):
    """
    Evaluate multiple exit rules in priority order.
    First rule that triggers wins.

    Useful for combining multiple exit conditions:
    - Stop loss (checked first for safety)
    - Profit target (checked second)
    - Time exit (checked last as fallback)
    """

    def __init__(self, rules: List[Tuple[ExitRule, float]]):
        """
        Args:
            rules: List of (ExitRule, exit_portion) tuples
                   Evaluated in order, first match wins
                   exit_portion overrides the rule's configured portion
        """
        if not rules:
            raise ValueError("CompositeExitRule requires at least one rule")
        self.rules = rules

    def should_exit(self, roundtrip, date, price):
        """Evaluate rules in order, return first match."""
        # Try each rule in order
        for rule, portion in self.rules:
            should_exit, _, reason = rule.should_exit(roundtrip, date, price)

            if should_exit:
                # Use configured portion, not rule's portion
                return (True, portion, reason)

        return (False, 0.0, "")

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
            rule = create_exit_rule(rule_data["rule"])
            portion = rule_data["portion"]
            rules.append((rule, portion))

        return cls(rules)


# Factory function for deserialization
def create_exit_rule(data: dict) -> ExitRule:
    """
    Create ExitRule instance from dict.

    Args:
        data: Dict with 'type' key

    Returns:
        ExitRule instance

    Raises:
        ValueError: If unknown rule type
    """
    rule_type = data.get("type")

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
