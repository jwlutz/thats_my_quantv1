# backtester/entryrule.py

from dataclasses import dataclass
from typing import Optional, List, Tuple
from datetime import date
from backtester.calculation import Calculation, create_calculation
from backtester.condition import Condition, create_condition


@dataclass
class Signal:
    """
    Entry signal with metadata.

    Generated when an EntryRule triggers, containing all context
    needed to open a position.
    """
    ticker: str
    date: date
    signal_type: str
    metadata: dict
    priority: float  # For ranking when multiple signals compete


class EntryRule:
    """
    Combines a Calculation with a Condition to generate entry signals.

    This composable design allows:
    - Testing calculations independently
    - Reusing calculations with different conditions
    - Easy analysis-to-strategy pipeline

    Example:
        rule = EntryRule(
            calculation=EarningsSurprise(),
            condition=GreaterThan(0.05),
            signal_type="earnings_beat",
            priority=2.0
        )
    """

    def __init__(self,
                 calculation: Calculation,
                 condition: Condition,
                 signal_type: str,
                 priority: float = 1.0):
        """
        Args:
            calculation: Calculation instance to extract metric
            condition: Condition instance to evaluate metric
            signal_type: Label for this signal type (e.g., "earnings_beat")
            priority: Base priority for ranking signals (higher = better)
        """
        self.calculation = calculation
        self.condition = condition
        self.signal_type = signal_type
        self.priority = priority

    def should_enter(self,
                    ticker: str,
                    date: date,
                    data_provider,
                    portfolio=None) -> Optional[Signal]:
        """
        Check if entry signal triggered.

        Args:
            ticker: Stock symbol
            date: Date to check
            data_provider: DataProvider instance
            portfolio: Optional Portfolio instance for position-aware rules

        Returns:
            Signal if condition met, None otherwise
        """
        # Calculate metric
        value = self.calculation.calculate(ticker, date, data_provider, portfolio)

        # Check condition
        if value is not None and self.condition.check(value):
            return Signal(
                ticker=ticker,
                date=date,
                signal_type=self.signal_type,
                metadata={
                    'calculation': self.calculation.__class__.__name__,
                    'condition': self.condition.to_dict(),
                    'value': value
                },
                priority=self.priority
            )
        return None

    def to_dict(self) -> dict:
        """Serialize for config."""
        return {
            'type': 'EntryRule',
            'calculation': self.calculation.to_dict(),
            'condition': self.condition.to_dict(),
            'signal_type': self.signal_type,
            'priority': self.priority
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'EntryRule':
        """Deserialize from config."""
        calculation = create_calculation(data['calculation'])
        condition = create_condition(data['condition'])
        return cls(
            calculation=calculation,
            condition=condition,
            signal_type=data['signal_type'],
            priority=data.get('priority', 1.0)
        )


class CompositeEntryRule:
    """
    Trigger signal only if ALL calculation+condition pairs pass (AND logic).

    Useful for multi-factor strategies like:
    - Earnings beat AND low P/E (value + quality)
    - Red day AND high volume (pullback confirmation)
    - Institutional ownership above 60% AND positive earnings surprise

    Example:
        rule = CompositeEntryRule(
            calc_condition_pairs=[
                (EarningsSurprise(), GreaterThan(0.05)),  # 5%+ beat
                (PERatio(), LessThan(20))                  # P/E < 20
            ],
            signal_type="value_earnings_beat",
            priority=3.0
        )
    """

    def __init__(self,
                 calc_condition_pairs: List[Tuple[Calculation, Condition]],
                 signal_type: str,
                 priority: float = 1.0):
        """
        Args:
            calc_condition_pairs: List of (Calculation, Condition) tuples
            signal_type: Label for this signal type
            priority: Base priority for ranking signals
        """
        self.pairs = calc_condition_pairs
        self.signal_type = signal_type
        self.priority = priority

    def should_enter(self,
                    ticker: str,
                    date: date,
                    data_provider,
                    portfolio=None) -> Optional[Signal]:
        """
        Check if all conditions pass.

        Returns:
            Signal if ALL conditions met, None if any fail
        """
        metadata = {}

        # All conditions must pass (AND logic)
        for calc, cond in self.pairs:
            value = calc.calculate(ticker, date, data_provider, portfolio)

            # Any failure = no signal
            if value is None or not cond.check(value):
                return None

            # Store value in metadata
            metadata[calc.__class__.__name__] = value

        # All passed - generate signal
        return Signal(
            ticker=ticker,
            date=date,
            signal_type=self.signal_type,
            metadata=metadata,
            priority=self.priority
        )

    def to_dict(self) -> dict:
        """Serialize for config."""
        return {
            'type': 'CompositeEntryRule',
            'pairs': [
                {
                    'calculation': calc.to_dict(),
                    'condition': cond.to_dict()
                }
                for calc, cond in self.pairs
            ],
            'signal_type': self.signal_type,
            'priority': self.priority
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CompositeEntryRule':
        """Deserialize from config."""
        pairs = []
        for pair_data in data['pairs']:
            calc = create_calculation(pair_data['calculation'])
            cond = create_condition(pair_data['condition'])
            pairs.append((calc, cond))

        return cls(
            calc_condition_pairs=pairs,
            signal_type=data['signal_type'],
            priority=data.get('priority', 1.0)
        )


# Factory function for deserialization
def create_entry_rule(data: dict):
    """
    Create EntryRule or CompositeEntryRule from dict.

    Args:
        data: Dict with 'type' key

    Returns:
        EntryRule or CompositeEntryRule instance

    Raises:
        ValueError: If unknown rule type
    """
    rule_type = data.get('type')

    if rule_type == 'EntryRule':
        return EntryRule.from_dict(data)
    elif rule_type == 'CompositeEntryRule':
        return CompositeEntryRule.from_dict(data)
    else:
        raise ValueError(f"Unknown entry rule type: {rule_type}")
