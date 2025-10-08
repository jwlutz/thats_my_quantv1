from abc import ABC, abstractmethod
from typing import Optional

class PositionSizer(ABC):
    """
    Abstract base class for position sizing algorithms.

    Determines how many shares to buy when opening a position.
    Implementations can use fixed dollar amounts, portfolio percentages,
    risk-based sizing, volatility-adjusted sizing, etc.
    """

    @abstractmethod
    def calculate_shares(self,
                        price: float,
                        available_cash: float,
                        portfolio_value: float,
                        portfolio: Optional['Portfolio'] = None,
                        ticker: Optional[str] = None) -> float:
        """
        Calculate number of shares to purchase.

        Args:
            price: Current price per share
            available_cash: Cash available for new positions
            portfolio_value: Total portfolio value (cash + positions)
            portfolio: Optional Portfolio instance for position-aware sizing
            ticker: Optional ticker for ticker-specific rules

        Returns:
            float: Number of shares (fractional allowed)

        Raises:
            ValueError: If price <= 0
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

    This is the simplest and most common sizing method.
    Good for equal weighting across positions regardless of price.
    """

    def __init__(self, dollar_amount: float):
        """
        Args:
            dollar_amount: Dollar amount to allocate per position

        Raises:
            ValueError: If dollar_amount <= 0
        """
        if dollar_amount <= 0:
            raise ValueError(f"dollar_amount must be positive, got {dollar_amount}")
        self.dollar_amount = dollar_amount

    def calculate_shares(self,
                        price: float,
                        available_cash: float,
                        portfolio_value: float,
                        portfolio: Optional['Portfolio'] = None,
                        ticker: Optional[str] = None) -> float:
        """Calculate shares based on fixed dollar amount."""
        if price <= 0:
            raise ValueError(f"price must be positive, got {price}")

        # Use the lesser of target amount or available cash
        target_amount = min(self.dollar_amount, available_cash)

        # Return 0 if insufficient cash
        if target_amount <= 0:
            return 0.0

        return target_amount / price

    def to_dict(self) -> dict:
        return {
            'type': 'FixedDollarAmount',
            'dollar_amount': self.dollar_amount
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'FixedDollarAmount':
        return cls(dollar_amount=data['dollar_amount'])


class PercentPortfolio(PositionSizer):
    """
    Allocate percentage of total portfolio value per position.

    Example: 10% of portfolio
    - Portfolio = $50k → $5k per position
    - Portfolio = $100k → $10k per position

    Position sizes scale with portfolio growth/decline.
    Good for keeping position sizes proportional to total capital.
    """

    def __init__(self, percent: float):
        """
        Args:
            percent: Percentage as decimal (0.10 = 10%)

        Raises:
            ValueError: If percent not in (0, 1.0]
        """
        if not 0 < percent <= 1.0:
            raise ValueError(f"percent must be between 0 and 1.0, got {percent}")
        self.percent = percent

    def calculate_shares(self,
                        price: float,
                        available_cash: float,
                        portfolio_value: float,
                        portfolio: Optional['Portfolio'] = None,
                        ticker: Optional[str] = None) -> float:
        """Calculate shares based on portfolio percentage."""
        if price <= 0:
            raise ValueError(f"price must be positive, got {price}")

        # Calculate target allocation
        target_amount = portfolio_value * self.percent

        # Don't exceed available cash
        actual_amount = min(target_amount, available_cash)

        if actual_amount <= 0:
            return 0.0

        return actual_amount / price

    def to_dict(self) -> dict:
        return {
            'type': 'PercentPortfolio',
            'percent': self.percent
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PercentPortfolio':
        return cls(percent=data['percent'])


class PercentAvailableCash(PositionSizer):
    """
    Allocate percentage of available cash per position.

    Example: 50% of available cash
    - Cash = $10k → $5k per position
    - After buying 1 position, cash = $5k → $2.5k next position

    Different from PercentPortfolio:
    - PercentPortfolio: size based on total value (cash + positions)
    - PercentAvailableCash: size based only on cash

    Good for conservative strategies that don't want to be fully invested.
    """

    def __init__(self, percent: float):
        """
        Args:
            percent: Percentage of cash as decimal (0.50 = 50%)

        Raises:
            ValueError: If percent not in (0, 1.0]
        """
        if not 0 < percent <= 1.0:
            raise ValueError(f"percent must be between 0 and 1.0, got {percent}")
        self.percent = percent

    def calculate_shares(self,
                        price: float,
                        available_cash: float,
                        portfolio_value: float,
                        portfolio: Optional['Portfolio'] = None,
                        ticker: Optional[str] = None) -> float:
        """Calculate shares based on available cash percentage."""
        if price <= 0:
            raise ValueError(f"price must be positive, got {price}")

        # Use percentage of available cash
        target_amount = available_cash * self.percent

        if target_amount <= 0:
            return 0.0

        return target_amount / price

    def to_dict(self) -> dict:
        return {
            'type': 'PercentAvailableCash',
            'percent': self.percent
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PercentAvailableCash':
        return cls(percent=data['percent'])


class EqualWeight(PositionSizer):
    """
    Divide available cash equally among max positions.

    Example: $100k cash, max_positions = 5
    - Each position gets $20k

    This is the "equal weight" method from the SPEC.
    Ensures all positions have equal portfolio weight at entry.

    Note: Requires max_positions from Portfolio. If portfolio not provided,
    defaults to dividing cash by a reasonable default (10 positions).
    """

    def __init__(self, default_max_positions: int = 10):
        """
        Args:
            default_max_positions: Default if portfolio not provided

        Raises:
            ValueError: If default_max_positions <= 0
        """
        if default_max_positions <= 0:
            raise ValueError(f"default_max_positions must be positive, got {default_max_positions}")
        self.default_max_positions = default_max_positions

    def calculate_shares(self,
                        price: float,
                        available_cash: float,
                        portfolio_value: float,
                        portfolio: Optional['Portfolio'] = None,
                        ticker: Optional[str] = None) -> float:
        """Calculate shares for equal weighting."""
        if price <= 0:
            raise ValueError(f"price must be positive, got {price}")

        # Get max_positions from portfolio if available
        if portfolio is not None:
            max_positions = portfolio.max_positions
        else:
            max_positions = self.default_max_positions

        # Divide available cash by max positions
        allocation = available_cash / max_positions

        if allocation <= 0:
            return 0.0

        return allocation / price

    def to_dict(self) -> dict:
        return {
            'type': 'EqualWeight',
            'default_max_positions': self.default_max_positions
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'EqualWeight':
        return cls(default_max_positions=data.get('default_max_positions', 10))


class FixedShares(PositionSizer):
    """
    Buy fixed number of shares per position.

    Example: 100 shares
    - At $50/share → $5,000 cost
    - At $200/share → $20,000 cost

    Good for testing or strategies focused on share count rather than dollar value.
    Warning: Can lead to highly unbalanced portfolios (one stock at $500/share
    takes much more capital than one at $50/share).
    """

    def __init__(self, shares: float):
        """
        Args:
            shares: Number of shares to buy

        Raises:
            ValueError: If shares <= 0
        """
        if shares <= 0:
            raise ValueError(f"shares must be positive, got {shares}")
        self.shares = shares

    def calculate_shares(self,
                        price: float,
                        available_cash: float,
                        portfolio_value: float,
                        portfolio: Optional['Portfolio'] = None,
                        ticker: Optional[str] = None) -> float:
        """Return fixed share count if enough cash available."""
        if price <= 0:
            raise ValueError(f"price must be positive, got {price}")

        # Calculate required cash
        required_cash = self.shares * price

        # Return 0 if insufficient cash
        if required_cash > available_cash:
            return 0.0

        return self.shares

    def to_dict(self) -> dict:
        return {
            'type': 'FixedShares',
            'shares': self.shares
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'FixedShares':
        return cls(shares=data['shares'])


class RiskParity(PositionSizer):
    """
    Size positions based on inverse volatility (risk parity).

    Lower volatility stocks get larger allocations, higher volatility stocks
    get smaller allocations. Target is equal risk contribution per position.

    Example:
    - Stock A: 15% volatility → $10k allocation
    - Stock B: 30% volatility → $5k allocation

    Requires volatility calculation. For V1, uses simple approach:
    - Calculate target dollar amount (like FixedDollarAmount)
    - Adjust by volatility factor if available from signal metadata

    Future enhancement: Calculate historical volatility from price data.
    """

    def __init__(self,
                 base_dollar_amount: float,
                 target_volatility: float = 0.20,
                 max_adjustment: float = 2.0):
        """
        Args:
            base_dollar_amount: Base allocation before volatility adjustment
            target_volatility: Target volatility as decimal (0.20 = 20%)
            max_adjustment: Maximum adjustment multiplier (2.0 = can go 2x base)

        Raises:
            ValueError: If parameters invalid
        """
        if base_dollar_amount <= 0:
            raise ValueError(f"base_dollar_amount must be positive, got {base_dollar_amount}")
        if target_volatility <= 0:
            raise ValueError(f"target_volatility must be positive, got {target_volatility}")
        if max_adjustment < 1.0:
            raise ValueError(f"max_adjustment must be >= 1.0, got {max_adjustment}")

        self.base_dollar_amount = base_dollar_amount
        self.target_volatility = target_volatility
        self.max_adjustment = max_adjustment

    def calculate_shares(self,
                        price: float,
                        available_cash: float,
                        portfolio_value: float,
                        portfolio: Optional['Portfolio'] = None,
                        ticker: Optional[str] = None) -> float:
        """Calculate shares with volatility adjustment."""
        if price <= 0:
            raise ValueError(f"price must be positive, got {price}")

        # Start with base allocation
        target_amount = self.base_dollar_amount

        # TODO: Phase 5 enhancement - calculate actual volatility from data_provider
        # For V1, use target_volatility as default (no adjustment)
        # Future: stock_volatility = data_provider.get_volatility(ticker, period=90)
        # adjustment = target_volatility / stock_volatility
        # adjustment = min(adjustment, max_adjustment)
        # target_amount *= adjustment

        # Don't exceed available cash
        actual_amount = min(target_amount, available_cash)

        if actual_amount <= 0:
            return 0.0

        return actual_amount / price

    def to_dict(self) -> dict:
        return {
            'type': 'RiskParity',
            'base_dollar_amount': self.base_dollar_amount,
            'target_volatility': self.target_volatility,
            'max_adjustment': self.max_adjustment
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'RiskParity':
        return cls(
            base_dollar_amount=data['base_dollar_amount'],
            target_volatility=data.get('target_volatility', 0.20),
            max_adjustment=data.get('max_adjustment', 2.0)
        )


# Factory function for deserialization
def create_position_sizer(data: dict) -> PositionSizer:
    """
    Create PositionSizer instance from config dict.

    Args:
        data: Dict with 'type' key

    Returns:
        PositionSizer instance

    Raises:
        ValueError: If unknown sizer type

    Example:
        >>> sizer_config = {'type': 'FixedDollarAmount', 'dollar_amount': 5000}
        >>> sizer = create_position_sizer(sizer_config)
    """
    sizer_type = data.get('type')

    if sizer_type == 'FixedDollarAmount':
        return FixedDollarAmount.from_dict(data)
    elif sizer_type == 'PercentPortfolio':
        return PercentPortfolio.from_dict(data)
    elif sizer_type == 'PercentAvailableCash':
        return PercentAvailableCash.from_dict(data)
    elif sizer_type == 'EqualWeight':
        return EqualWeight.from_dict(data)
    elif sizer_type == 'FixedShares':
        return FixedShares.from_dict(data)
    elif sizer_type == 'RiskParity':
        return RiskParity.from_dict(data)
    else:
        raise ValueError(f"Unknown position sizer type: {sizer_type}")
