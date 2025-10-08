from abc import ABC, abstractmethod
from typing import Optional


class Condition(ABC):
    """
    Base class for evaluating if a calculated value meets a condition.

    Pure logic, no data access. Separates "how to evaluate" from "what to measure".
    """

    @abstractmethod
    def check(self, value: Optional[float]) -> bool:
        """
        Check if value satisfies condition.

        Args:
            value: Calculated value to evaluate (None if data unavailable)

        Returns:
            bool: True if condition met, False otherwise
        """
        pass

    @abstractmethod
    def to_dict(self) -> dict:
        """Serialize for config."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> 'Condition':
        """Deserialize from config."""
        pass


class GreaterThan(Condition):
    """Value > threshold."""

    def __init__(self, threshold: float):
        self.threshold = threshold

    def check(self, value):
        return value is not None and value > self.threshold

    def to_dict(self):
        return {'type': 'GreaterThan', 'threshold': self.threshold}

    @classmethod
    def from_dict(cls, data):
        return cls(data['threshold'])


class LessThan(Condition):
    """Value < threshold."""

    def __init__(self, threshold: float):
        self.threshold = threshold

    def check(self, value):
        return value is not None and value < self.threshold

    def to_dict(self):
        return {'type': 'LessThan', 'threshold': self.threshold}

    @classmethod
    def from_dict(cls, data):
        return cls(data['threshold'])


class Between(Condition):
    """min_val <= value <= max_val."""

    def __init__(self, min_val: float, max_val: float):
        self.min_val = min_val
        self.max_val = max_val

    def check(self, value):
        return value is not None and self.min_val <= value <= self.max_val

    def to_dict(self):
        return {'type': 'Between', 'min': self.min_val, 'max': self.max_val}

    @classmethod
    def from_dict(cls, data):
        return cls(data['min'], data['max'])


# Factory function for deserialization
def create_condition(data: dict) -> Condition:
    """
    Create Condition instance from dict.

    Args:
        data: Dict with 'type' key

    Returns:
        Condition instance

    Raises:
        ValueError: If unknown condition type
    """
    cond_type = data.get('type')

    if cond_type == 'GreaterThan':
        return GreaterThan.from_dict(data)
    elif cond_type == 'LessThan':
        return LessThan.from_dict(data)
    elif cond_type == 'Between':
        return Between.from_dict(data)
    else:
        raise ValueError(f"Unknown condition type: {cond_type}")