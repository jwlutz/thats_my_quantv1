from abc import ABC, abstractmethod
from typing import Optional
from datetime import date


class Calculation(ABC):
    """
    Base class for extracting or calculating metrics from market data.

    Separates data extraction from decision logic, enabling:
    - Independent testing of calculations
    - Reusable calculations across multiple rules
    - Easy analysis-to-strategy pipeline
    """

    @abstractmethod
    def calculate(self,
                  ticker: str,
                  date: date,
                  data_provider,
                  portfolio=None) -> Optional[float]:
        """
        Calculate metric for a ticker on a given date.

        Args:
            ticker: Stock symbol
            date: Date to calculate for
            data_provider: DataProvider instance for market data
            portfolio: Optional Portfolio instance for position-aware calculations

        Returns:
            float: Calculated value, or None if data unavailable
        """
        pass

    @abstractmethod
    def to_dict(self) -> dict:
        """Serialize for config."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> 'Calculation':
        """Deserialize from config."""
        pass


class EarningsSurprise(Calculation):
    """Calculate earnings surprise percentage."""

    def calculate(self, ticker, date, data_provider, portfolio=None):
        """
        Get most recent earnings surprise.

        Returns:
            Surprise percentage (0.05 = 5% beat), or None if no data
        """
        earnings_data = data_provider.get_earnings_data(ticker, date)
        if earnings_data:
            return earnings_data.get('surprise_pct')
        return None

    def to_dict(self):
        return {'type': 'EarningsSurprise'}

    @classmethod
    def from_dict(cls, data):
        return cls()


class DayChange(Calculation):
    """Calculate single-day price change percentage."""

    def calculate(self, ticker, date, data_provider, portfolio=None):
        """
        Calculate (close - open) / open for a single day.

        Returns:
            Day change as decimal (0.02 = 2% gain), or None if no data
        """
        bar = data_provider.get_bar(ticker, date)
        if bar and bar['open'] > 0:
            return (bar['close'] - bar['open']) / bar['open']
        return None

    def to_dict(self):
        return {'type': 'DayChange'}

    @classmethod
    def from_dict(cls, data):
        return cls()


class PERatio(Calculation):
    """Get trailing P/E ratio."""
    
    def calculate(self, ticker, date, data_provider, portfolio=None):
        """
        Get trailing P/E ratio from stock info.
        
        Returns:
            P/E ratio, or None if not available
        """
        info = data_provider.get_info(ticker)
        if info:
            return info.get('trailingPE')
        return None
    
    def to_dict(self):
        return {'type': 'PERatio'}
    
    @classmethod
    def from_dict(cls, data):
        return cls()


class InstitutionalOwnership(Calculation):
    """Calculate total institutional ownership percentage."""
    
    def calculate(self, ticker, date, data_provider, portfolio=None):
        """
        Sum institutional holder percentages.
        
        Returns:
            Total institutional ownership as decimal (0.65 = 65%), or None
        """
        holders = data_provider.get_institutional_holders(ticker)
        if holders is not None and not holders.empty:
            return holders['pctHeld'].sum()
        return None
    
    def to_dict(self):
        return {'type': 'InstitutionalOwnership'}
    
    @classmethod
    def from_dict(cls, data):
        return cls()


# Factory function for deserialization
def create_calculation(data: dict) -> Calculation:
    """
    Create Calculation instance from dict.
    
    Args:
        data: Dict with 'type' key
    
    Returns:
        Calculation instance
    
    Raises:
        ValueError: If unknown calculation type
    """
    calc_type = data.get('type')
    
    if calc_type == 'EarningsSurprise':
        return EarningsSurprise.from_dict(data)
    elif calc_type == 'DayChange':
        return DayChange.from_dict(data)
    elif calc_type == 'PERatio':
        return PERatio.from_dict(data)
    elif calc_type == 'InstitutionalOwnership':
        return InstitutionalOwnership.from_dict(data)
    else:
        raise ValueError(f"Unknown calculation type: {calc_type}")