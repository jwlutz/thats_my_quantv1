# tests/test_condition.py

import pytest
from backtester.condition import (
    Condition,
    GreaterThan,
    LessThan,
    Between,
    create_condition
)


class TestGreaterThan:
    """Test GreaterThan condition."""

    def test_check_greater(self):
        cond = GreaterThan(10.0)
        assert cond.check(15.0) is True

    def test_check_equal(self):
        cond = GreaterThan(10.0)
        assert cond.check(10.0) is False  # Not strictly greater

    def test_check_less(self):
        cond = GreaterThan(10.0)
        assert cond.check(5.0) is False

    def test_check_none(self):
        cond = GreaterThan(10.0)
        assert cond.check(None) is False

    def test_check_zero_threshold(self):
        cond = GreaterThan(0.0)
        assert cond.check(0.1) is True
        assert cond.check(0.0) is False
        assert cond.check(-0.1) is False

    def test_check_negative_threshold(self):
        cond = GreaterThan(-5.0)
        assert cond.check(-4.0) is True
        assert cond.check(-5.0) is False
        assert cond.check(-6.0) is False

    def test_check_small_difference(self):
        cond = GreaterThan(0.05)
        assert cond.check(0.051) is True
        assert cond.check(0.05) is False

    def test_to_dict(self):
        cond = GreaterThan(10.5)
        assert cond.to_dict() == {'type': 'GreaterThan', 'threshold': 10.5}

    def test_from_dict(self):
        data = {'type': 'GreaterThan', 'threshold': 10.5}
        cond = GreaterThan.from_dict(data)
        assert isinstance(cond, GreaterThan)
        assert cond.threshold == 10.5

    def test_serialization_round_trip(self):
        cond = GreaterThan(42.7)
        data = cond.to_dict()
        cond2 = GreaterThan.from_dict(data)
        assert cond2.threshold == cond.threshold
        assert cond2.check(50.0) == cond.check(50.0)


class TestLessThan:
    """Test LessThan condition."""

    def test_check_less(self):
        cond = LessThan(10.0)
        assert cond.check(5.0) is True

    def test_check_equal(self):
        cond = LessThan(10.0)
        assert cond.check(10.0) is False  # Not strictly less

    def test_check_greater(self):
        cond = LessThan(10.0)
        assert cond.check(15.0) is False

    def test_check_none(self):
        cond = LessThan(10.0)
        assert cond.check(None) is False

    def test_check_zero_threshold(self):
        cond = LessThan(0.0)
        assert cond.check(-0.1) is True
        assert cond.check(0.0) is False
        assert cond.check(0.1) is False

    def test_check_negative_threshold(self):
        cond = LessThan(-5.0)
        assert cond.check(-6.0) is True
        assert cond.check(-5.0) is False
        assert cond.check(-4.0) is False

    def test_check_small_difference(self):
        cond = LessThan(0.05)
        assert cond.check(0.049) is True
        assert cond.check(0.05) is False

    def test_to_dict(self):
        cond = LessThan(10.5)
        assert cond.to_dict() == {'type': 'LessThan', 'threshold': 10.5}

    def test_from_dict(self):
        data = {'type': 'LessThan', 'threshold': 10.5}
        cond = LessThan.from_dict(data)
        assert isinstance(cond, LessThan)
        assert cond.threshold == 10.5

    def test_serialization_round_trip(self):
        cond = LessThan(20.3)
        data = cond.to_dict()
        cond2 = LessThan.from_dict(data)
        assert cond2.threshold == cond.threshold
        assert cond2.check(15.0) == cond.check(15.0)


class TestBetween:
    """Test Between condition."""

    def test_check_within_range(self):
        cond = Between(10.0, 20.0)
        assert cond.check(15.0) is True

    def test_check_at_min(self):
        cond = Between(10.0, 20.0)
        assert cond.check(10.0) is True  # Inclusive

    def test_check_at_max(self):
        cond = Between(10.0, 20.0)
        assert cond.check(20.0) is True  # Inclusive

    def test_check_below_range(self):
        cond = Between(10.0, 20.0)
        assert cond.check(5.0) is False

    def test_check_above_range(self):
        cond = Between(10.0, 20.0)
        assert cond.check(25.0) is False

    def test_check_none(self):
        cond = Between(10.0, 20.0)
        assert cond.check(None) is False

    def test_check_negative_range(self):
        cond = Between(-20.0, -10.0)
        assert cond.check(-15.0) is True
        assert cond.check(-20.0) is True
        assert cond.check(-10.0) is True
        assert cond.check(-25.0) is False
        assert cond.check(-5.0) is False

    def test_check_crossing_zero(self):
        cond = Between(-5.0, 5.0)
        assert cond.check(-3.0) is True
        assert cond.check(0.0) is True
        assert cond.check(3.0) is True
        assert cond.check(-6.0) is False
        assert cond.check(6.0) is False

    def test_check_narrow_range(self):
        cond = Between(0.04, 0.06)
        assert cond.check(0.05) is True
        assert cond.check(0.04) is True
        assert cond.check(0.06) is True
        assert cond.check(0.03) is False
        assert cond.check(0.07) is False

    def test_check_single_point_range(self):
        """Test when min == max."""
        cond = Between(10.0, 10.0)
        assert cond.check(10.0) is True
        assert cond.check(9.9) is False
        assert cond.check(10.1) is False

    def test_to_dict(self):
        cond = Between(5.5, 15.5)
        assert cond.to_dict() == {'type': 'Between', 'min': 5.5, 'max': 15.5}

    def test_from_dict(self):
        data = {'type': 'Between', 'min': 5.5, 'max': 15.5}
        cond = Between.from_dict(data)
        assert isinstance(cond, Between)
        assert cond.min_val == 5.5
        assert cond.max_val == 15.5

    def test_serialization_round_trip(self):
        cond = Between(-10.0, 50.0)
        data = cond.to_dict()
        cond2 = Between.from_dict(data)
        assert cond2.min_val == cond.min_val
        assert cond2.max_val == cond.max_val
        assert cond2.check(25.0) == cond.check(25.0)


class TestFactoryFunction:
    """Test create_condition factory function."""

    def test_create_greater_than(self):
        data = {'type': 'GreaterThan', 'threshold': 10.0}
        cond = create_condition(data)
        assert isinstance(cond, GreaterThan)
        assert cond.threshold == 10.0

    def test_create_less_than(self):
        data = {'type': 'LessThan', 'threshold': 20.0}
        cond = create_condition(data)
        assert isinstance(cond, LessThan)
        assert cond.threshold == 20.0

    def test_create_between(self):
        data = {'type': 'Between', 'min': 5.0, 'max': 15.0}
        cond = create_condition(data)
        assert isinstance(cond, Between)
        assert cond.min_val == 5.0
        assert cond.max_val == 15.0

    def test_create_unknown_type(self):
        data = {'type': 'UnknownCondition', 'threshold': 10.0}
        with pytest.raises(ValueError, match="Unknown condition type"):
            create_condition(data)

    def test_create_missing_type(self):
        data = {'threshold': 10.0}
        with pytest.raises(ValueError, match="Unknown condition type"):
            create_condition(data)


class TestConditionCombinations:
    """Test realistic condition combinations."""

    def test_earnings_surprise_threshold(self):
        """Typical use: earnings beat by >5%."""
        cond = GreaterThan(0.05)
        assert cond.check(0.08) is True  # 8% beat
        assert cond.check(0.05) is False  # Exactly 5%
        assert cond.check(0.03) is False  # 3% beat (not enough)

    def test_pe_ratio_value_screen(self):
        """Typical use: P/E ratio < 20 for value stocks."""
        cond = LessThan(20.0)
        assert cond.check(15.0) is True  # Value stock
        assert cond.check(25.0) is False  # Growth stock

    def test_day_change_red_day(self):
        """Typical use: red day (negative change)."""
        cond = LessThan(0.0)
        assert cond.check(-0.02) is True  # Down 2%
        assert cond.check(0.01) is False  # Up 1%

    def test_day_change_green_day(self):
        """Typical use: green day (positive change)."""
        cond = GreaterThan(0.0)
        assert cond.check(0.03) is True  # Up 3%
        assert cond.check(-0.01) is False  # Down 1%

    def test_institutional_ownership_range(self):
        """Typical use: institutional ownership between 40-70%."""
        cond = Between(0.40, 0.70)
        assert cond.check(0.55) is True  # 55%
        assert cond.check(0.30) is False  # Too low
        assert cond.check(0.80) is False  # Too high

    def test_large_price_move(self):
        """Typical use: day change > ±5%."""
        cond_big_green = GreaterThan(0.05)
        cond_big_red = LessThan(-0.05)

        assert cond_big_green.check(0.07) is True
        assert cond_big_green.check(0.02) is False

        assert cond_big_red.check(-0.08) is True
        assert cond_big_red.check(-0.02) is False
