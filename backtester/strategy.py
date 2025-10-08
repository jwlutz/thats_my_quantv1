from typing import List, Optional
from datetime import date
from backtester.entryrule import EntryRule, Signal, CompositeEntryRule
from backtester.exitrule import ExitRule
from backtester.positionsizer import PositionSizer
from backtester.dataprovider import DataProvider

class Strategy:
    """
    Complete trading strategy combining:
    - Entry rules (when to buy)
    - Exit rules (when to sell)
    - Universe (what to trade)
    - Position sizer (how much to buy)

    This is the top-level component that defines a complete trading strategy.
    The Backtester executes this strategy over historical data.

    Example:
        >>> from backtester.calculation import EarningsSurprise
        >>> from backtester.condition import GreaterThan
        >>> from backtester.entryrule import EntryRule
        >>> from backtester.exitrule import CompositeExitRule, StopLossExit, TimeBasedExit
        >>> from backtester.positionsizer import FixedDollarAmount
        >>>
        >>> strategy = Strategy(
        ...     name="Earnings Beat Value",
        ...     entry_rules=[
        ...         EntryRule(
        ...             calculation=EarningsSurprise(),
        ...             condition=GreaterThan(0.05),
        ...             signal_type='earnings_beat',
        ...             priority=2.0
        ...         )
        ...     ],
        ...     exit_rules=CompositeExitRule(rules=[
        ...         (StopLossExit(0.08), 1.0),
        ...         (TimeBasedExit(30), 1.0)
        ...     ]),
        ...     position_sizer=FixedDollarAmount(5000),
        ...     universe=['AAPL', 'MSFT', 'GOOGL']
        ... )
    """

    def __init__(self,
                 name: str,
                 entry_rules: List[EntryRule],
                 exit_rules: ExitRule,
                 position_sizer: PositionSizer,
                 universe: List[str],
                 description: str = ""):
        """
        Initialize strategy.

        Args:
            name: Strategy name (for identification and reporting)
            entry_rules: List of EntryRule instances (signals OR'd together)
            exit_rules: Single ExitRule (use CompositeExitRule for multiple)
            position_sizer: PositionSizer instance
            universe: List of tickers to trade
            description: Optional strategy description

        Raises:
            ValueError: If entry_rules empty or universe empty

        Design Note:
            - entry_rules is a list: Multiple rules can trigger signals
            - exit_rules is single: Use CompositeExitRule to combine multiple exit conditions
            - This design allows flexible entry logic while maintaining clear exit priority
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
                        current_date: date,
                        data_provider: DataProvider,
                        portfolio: Optional['Portfolio'] = None) -> List[Signal]:
        """
        Generate entry signals for all tickers in universe.

        This is called by the Backtester on each day to check for entry opportunities.

        Args:
            current_date: Current date
            data_provider: DataProvider instance for market data
            portfolio: Optional Portfolio for position-aware rules

        Returns:
            List[Signal]: All triggered signals, sorted by priority (high to low)

        Example:
            >>> signals = strategy.generate_signals(
            ...     current_date=date(2024, 2, 5),
            ...     data_provider=yf_provider
            ... )
            >>> # signals = [
            >>> #     Signal(ticker='AAPL', priority=0.083, ...),  # 8.3% beat
            >>> #     Signal(ticker='MSFT', priority=0.055, ...),  # 5.5% beat
            >>> # ]
        """
        signals = []

        # Check each ticker in universe
        for ticker in self.universe:
            # Check each entry rule
            for rule in self.entry_rules:
                # Get signal from rule (None if condition not met)
                signal = rule.should_enter(ticker, current_date, data_provider, portfolio)
                
                if signal:
                    signals.append(signal)
                    # Note: We don't break here - multiple rules can trigger for same ticker
                    # (e.g., earnings beat AND low P/E both trigger)

        # Sort by priority (highest first)
        # When we have more signals than capital, we take the best ones
        signals.sort(key=lambda s: s.priority, reverse=True)

        return signals

    def validate(self) -> bool:
        """
        Validate strategy configuration.

        Called before backtest starts to catch configuration errors early.

        Returns:
            bool: True if valid

        Raises:
            ValueError: If configuration invalid
        """
        if not self.universe:
            raise ValueError("Universe cannot be empty")
        if not self.entry_rules:
            raise ValueError("Entry rules cannot be empty")
        if self.exit_rules is None:
            raise ValueError("Exit rule required")
        if self.position_sizer is None:
            raise ValueError("Position sizer required")
        
        return True

    def to_dict(self) -> dict:
        """
        Serialize strategy to dict for YAML/JSON export.

        Returns:
            dict: Strategy configuration

        Example:
            >>> strategy.to_dict()
            {
                'name': 'Earnings Beat Value',
                'description': '',
                'entry_rules': [
                    {
                        'type': 'EntryRule',
                        'calculation': {...},
                        'condition': {...},
                        ...
                    }
                ],
                'exit_rules': {...},
                'position_sizer': {...},
                'universe': ['AAPL', 'MSFT', 'GOOGL']
            }
        """
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
        """
        Deserialize strategy from dict (YAML/JSON import).

        Args:
            data: Dict with strategy configuration

        Returns:
            Strategy: Reconstructed strategy instance

        Example:
            >>> with open('my_strategy.yaml', 'r') as f:
            ...     config = yaml.safe_load(f)
            >>> strategy = Strategy.from_dict(config)
        """
        from backtester.entryrule import create_entry_rule
        from backtester.exitrule import create_exit_rule
        from backtester.positionsizer import create_position_sizer

        # Construct entry rules (list)
        entry_rules = [create_entry_rule(r) for r in data['entry_rules']]

        # Construct exit rule (single, but could be CompositeExitRule)
        exit_rules = create_exit_rule(data['exit_rules'])

        # Construct position sizer
        position_sizer = create_position_sizer(data['position_sizer'])

        return cls(
            name=data['name'],
            entry_rules=entry_rules,
            exit_rules=exit_rules,
            position_sizer=position_sizer,
            universe=data['universe'],
            description=data.get('description', '')
        )

    def to_yaml(self, filepath: str):
        """
        Save strategy to YAML file.

        Args:
            filepath: Path to save YAML file

        Example:
            >>> strategy.to_yaml('strategies/earnings_beat.yaml')
        """
        import yaml
        
        with open(filepath, 'w') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml(cls, filepath: str) -> 'Strategy':
        """
        Load strategy from YAML file.

        Args:
            filepath: Path to YAML file

        Returns:
            Strategy: Loaded strategy instance

        Example:
            >>> strategy = Strategy.from_yaml('strategies/earnings_beat.yaml')
        """
        import yaml
        
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
        
        return cls.from_dict(data)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (f"Strategy(name='{self.name}', "
                f"entry_rules={len(self.entry_rules)}, "
                f"universe={len(self.universe)} tickers)")

    def __str__(self) -> str:
        """User-friendly string representation."""
        return f"{self.name} ({len(self.universe)} tickers, {len(self.entry_rules)} entry rules)"