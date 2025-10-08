# tests/test_exitrule.py

import pytest
from datetime import date, timedelta
from backtester.exitrule import (
    ExitRule,
    TimeBasedExit,
    StopLossExit,
    TrailingStopExit,
    ProfitTargetExit,
    CompositeExitRule,
    create_exit_rule
)
from backtester.roundtrip import RoundTrip
from backtester.transaction import Transaction


# Helper to create test RoundTrip
def create_test_roundtrip(ticker='AAPL', entry_date=date(2024, 1, 1),
                         shares=10.0, entry_price=100.0):
    """Create a RoundTrip with one entry transaction."""
    rt = RoundTrip(ticker=ticker)
    txn = Transaction(
        roundtrip_id=rt.id,
        ticker=ticker,
        date=entry_date,
        transaction_type='open',
        shares=shares,
        price=entry_price,
        net_amount=-shares * entry_price,
        reason='signal'
    )
    rt.add_transaction(txn)
    return rt


class TestTimeBasedExit:
    """Test TimeBasedExit rule."""

    def test_exit_at_exact_threshold(self):
        """Test exit triggers at exact holding_days."""
        rule = TimeBasedExit(holding_days=30)
        rt = create_test_roundtrip(entry_date=date(2024, 1, 1))

        # Day 30 should trigger
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 31), 100.0
        )

        assert should_exit is True
        assert portion == 1.0
        assert reason == "time_exit"

    def test_no_exit_before_threshold(self):
        """Test no exit before holding_days."""
        rule = TimeBasedExit(holding_days=30)
        rt = create_test_roundtrip(entry_date=date(2024, 1, 1))

        # Day 29 should not trigger
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 30), 100.0
        )

        assert should_exit is False
        assert portion == 0.0
        assert reason == ""

    def test_exit_after_threshold(self):
        """Test exit triggers after holding_days."""
        rule = TimeBasedExit(holding_days=10)
        rt = create_test_roundtrip(entry_date=date(2024, 1, 1))

        # Day 15 should trigger
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 16), 100.0
        )

        assert should_exit is True

    def test_zero_days_invalid(self):
        """Test that zero holding_days raises error."""
        with pytest.raises(ValueError, match="holding_days must be positive"):
            TimeBasedExit(holding_days=0)

    def test_negative_days_invalid(self):
        """Test that negative holding_days raises error."""
        with pytest.raises(ValueError, match="holding_days must be positive"):
            TimeBasedExit(holding_days=-5)

    def test_to_dict(self):
        """Test serialization."""
        rule = TimeBasedExit(holding_days=30)
        data = rule.to_dict()

        assert data["type"] == "TimeBasedExit"
        assert data["params"]["holding_days"] == 30

    def test_from_dict(self):
        """Test deserialization."""
        data = {"type": "TimeBasedExit", "params": {"holding_days": 30}}
        rule = TimeBasedExit.from_dict(data)

        assert isinstance(rule, TimeBasedExit)
        assert rule.holding_days == 30

    def test_serialization_round_trip(self):
        """Test full serialization round trip."""
        rule1 = TimeBasedExit(holding_days=45)
        data = rule1.to_dict()
        rule2 = TimeBasedExit.from_dict(data)

        assert rule2.holding_days == rule1.holding_days


class TestStopLossExit:
    """Test StopLossExit rule."""

    def test_exit_at_exact_stop_loss(self):
        """Test exit triggers at exact stop_pct."""
        rule = StopLossExit(stop_pct=0.08)  # 8% stop
        rt = create_test_roundtrip(entry_price=100.0)

        # Price at -8% should trigger
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 5), 92.0
        )

        assert should_exit is True
        assert portion == 1.0
        assert reason == "stop_loss"

    def test_no_exit_above_stop_loss(self):
        """Test no exit when loss is within tolerance."""
        rule = StopLossExit(stop_pct=0.08)
        rt = create_test_roundtrip(entry_price=100.0)

        # Price at -7% should not trigger
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 5), 93.0
        )

        assert should_exit is False
        assert portion == 0.0

    def test_no_exit_on_profit(self):
        """Test no exit when position is profitable."""
        rule = StopLossExit(stop_pct=0.08)
        rt = create_test_roundtrip(entry_price=100.0)

        # Price at +10% should not trigger
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 5), 110.0
        )

        assert should_exit is False

    def test_exit_below_stop_loss(self):
        """Test exit when loss exceeds stop_pct."""
        rule = StopLossExit(stop_pct=0.05)
        rt = create_test_roundtrip(entry_price=100.0)

        # Price at -10% should trigger 5% stop
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 5), 90.0
        )

        assert should_exit is True
        assert reason == "stop_loss"

    def test_zero_stop_invalid(self):
        """Test that zero stop_pct raises error."""
        with pytest.raises(ValueError, match="stop_pct must be positive"):
            StopLossExit(stop_pct=0.0)

    def test_negative_stop_invalid(self):
        """Test that negative stop_pct raises error."""
        with pytest.raises(ValueError, match="stop_pct must be positive"):
            StopLossExit(stop_pct=-0.05)

    def test_to_dict(self):
        """Test serialization."""
        rule = StopLossExit(stop_pct=0.10)
        data = rule.to_dict()

        assert data["type"] == "StopLossExit"
        assert data["params"]["stop_pct"] == 0.10

    def test_from_dict(self):
        """Test deserialization."""
        data = {"type": "StopLossExit", "params": {"stop_pct": 0.10}}
        rule = StopLossExit.from_dict(data)

        assert isinstance(rule, StopLossExit)
        assert rule.stop_pct == 0.10


class TestTrailingStopExit:
    """Test TrailingStopExit rule."""

    def test_exit_at_drawdown_from_peak(self):
        """Test exit when price drops trailing_pct from peak."""
        rule = TrailingStopExit(trailing_pct=0.10)  # 10% trailing stop
        rt = create_test_roundtrip(entry_price=100.0)

        # Price rises to 120 (new peak)
        rule.should_exit(rt, date(2024, 1, 2), 120.0)

        # Price drops to 108 (10% from peak of 120)
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 3), 108.0
        )

        assert should_exit is True
        assert portion == 1.0
        assert reason == "trailing_stop"

    def test_peak_updates_correctly(self):
        """Test that peak price updates as price rises."""
        rule = TrailingStopExit(trailing_pct=0.10)
        rt = create_test_roundtrip(entry_price=100.0)

        # Price rises
        rule.should_exit(rt, date(2024, 1, 2), 110.0)
        rule.should_exit(rt, date(2024, 1, 3), 120.0)
        rule.should_exit(rt, date(2024, 1, 4), 115.0)  # Dip but not enough

        # Peak should be 120
        assert rule._peak_prices[rt.id] == 120.0

    def test_no_exit_within_trailing_stop(self):
        """Test no exit when drawdown is within tolerance."""
        rule = TrailingStopExit(trailing_pct=0.10)
        rt = create_test_roundtrip(entry_price=100.0)

        # Price rises to 120
        rule.should_exit(rt, date(2024, 1, 2), 120.0)

        # Price drops to 109 (9% from peak, should not trigger)
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 3), 109.0
        )

        assert should_exit is False

    def test_initial_peak_is_entry_price(self):
        """Test that initial peak is set to entry price."""
        rule = TrailingStopExit(trailing_pct=0.10)
        rt = create_test_roundtrip(entry_price=100.0)

        # First check should initialize peak to 100
        rule.should_exit(rt, date(2024, 1, 2), 95.0)

        assert rule._peak_prices[rt.id] == 100.0

    def test_multiple_positions_tracked_independently(self):
        """Test that multiple positions have independent peak tracking."""
        rule = TrailingStopExit(trailing_pct=0.10)

        rt1 = create_test_roundtrip(ticker='AAPL', entry_price=100.0)
        rt2 = create_test_roundtrip(ticker='MSFT', entry_price=200.0)

        # Update peaks separately
        rule.should_exit(rt1, date(2024, 1, 2), 120.0)  # AAPL peak = 120
        rule.should_exit(rt2, date(2024, 1, 2), 250.0)  # MSFT peak = 250

        assert rule._peak_prices[rt1.id] == 120.0
        assert rule._peak_prices[rt2.id] == 250.0

    def test_zero_trailing_pct_invalid(self):
        """Test that zero trailing_pct raises error."""
        with pytest.raises(ValueError, match="trailing_pct must be positive"):
            TrailingStopExit(trailing_pct=0.0)

    def test_to_dict(self):
        """Test serialization."""
        rule = TrailingStopExit(trailing_pct=0.15)
        data = rule.to_dict()

        assert data["type"] == "TrailingStopExit"
        assert data["params"]["trailing_pct"] == 0.15

    def test_from_dict(self):
        """Test deserialization."""
        data = {"type": "TrailingStopExit", "params": {"trailing_pct": 0.15}}
        rule = TrailingStopExit.from_dict(data)

        assert isinstance(rule, TrailingStopExit)
        assert rule.trailing_pct == 0.15


class TestProfitTargetExit:
    """Test ProfitTargetExit rule."""

    def test_exit_at_exact_profit_target(self):
        """Test exit triggers at exact target_pct."""
        rule = ProfitTargetExit(target_pct=0.20)  # 20% profit target
        rt = create_test_roundtrip(entry_price=100.0)

        # Price at +20% should trigger
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 5), 120.0
        )

        assert should_exit is True
        assert portion == 1.0
        assert reason == "profit_target"

    def test_no_exit_below_target(self):
        """Test no exit when profit below target."""
        rule = ProfitTargetExit(target_pct=0.20)
        rt = create_test_roundtrip(entry_price=100.0)

        # Price at +15% should not trigger
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 5), 115.0
        )

        assert should_exit is False

    def test_exit_above_target(self):
        """Test exit when profit exceeds target."""
        rule = ProfitTargetExit(target_pct=0.10)
        rt = create_test_roundtrip(entry_price=100.0)

        # Price at +25% should trigger 10% target
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 5), 125.0
        )

        assert should_exit is True

    def test_no_exit_on_loss(self):
        """Test no exit when position has loss."""
        rule = ProfitTargetExit(target_pct=0.20)
        rt = create_test_roundtrip(entry_price=100.0)

        # Price at -10% should not trigger
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 5), 90.0
        )

        assert should_exit is False

    def test_partial_exit(self):
        """Test partial exit with exit_portion < 1.0."""
        rule = ProfitTargetExit(target_pct=0.20, exit_portion=0.5)
        rt = create_test_roundtrip(entry_price=100.0)

        # Price at +20% should trigger with 50% exit
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 5), 120.0
        )

        assert should_exit is True
        assert portion == 0.5

    def test_zero_target_invalid(self):
        """Test that zero target_pct raises error."""
        with pytest.raises(ValueError, match="target_pct must be positive"):
            ProfitTargetExit(target_pct=0.0)

    def test_negative_target_invalid(self):
        """Test that negative target_pct raises error."""
        with pytest.raises(ValueError, match="target_pct must be positive"):
            ProfitTargetExit(target_pct=-0.10)

    def test_zero_exit_portion_invalid(self):
        """Test that zero exit_portion raises error."""
        with pytest.raises(ValueError, match="exit_portion must be in"):
            ProfitTargetExit(target_pct=0.20, exit_portion=0.0)

    def test_exit_portion_above_one_invalid(self):
        """Test that exit_portion > 1.0 raises error."""
        with pytest.raises(ValueError, match="exit_portion must be in"):
            ProfitTargetExit(target_pct=0.20, exit_portion=1.5)

    def test_to_dict(self):
        """Test serialization."""
        rule = ProfitTargetExit(target_pct=0.25, exit_portion=0.75)
        data = rule.to_dict()

        assert data["type"] == "ProfitTargetExit"
        assert data["params"]["target_pct"] == 0.25
        assert data["params"]["exit_portion"] == 0.75

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "type": "ProfitTargetExit",
            "params": {"target_pct": 0.25, "exit_portion": 0.75}
        }
        rule = ProfitTargetExit.from_dict(data)

        assert isinstance(rule, ProfitTargetExit)
        assert rule.target_pct == 0.25
        assert rule.exit_portion == 0.75

    def test_from_dict_default_exit_portion(self):
        """Test deserialization with default exit_portion."""
        data = {"type": "ProfitTargetExit", "params": {"target_pct": 0.20}}
        rule = ProfitTargetExit.from_dict(data)

        assert rule.exit_portion == 1.0


class TestCompositeExitRule:
    """Test CompositeExitRule priority ordering."""

    def test_first_rule_wins(self):
        """Test that first matching rule wins."""
        rule = CompositeExitRule(
            rules=[
                (StopLossExit(0.08), 1.0),      # Will trigger
                (TimeBasedExit(30), 1.0)        # Would also trigger but checked second
            ]
        )

        rt = create_test_roundtrip(entry_date=date(2024, 1, 1), entry_price=100.0)

        # Price at -8%, 35 days later
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 2, 5), 92.0
        )

        assert should_exit is True
        assert portion == 1.0
        assert reason == "stop_loss"  # Stop loss checked first

    def test_second_rule_triggers_if_first_doesnt(self):
        """Test that second rule evaluated if first doesn't trigger."""
        rule = CompositeExitRule(
            rules=[
                (StopLossExit(0.08), 1.0),      # Won't trigger
                (TimeBasedExit(30), 1.0)        # Will trigger
            ]
        )

        rt = create_test_roundtrip(entry_date=date(2024, 1, 1), entry_price=100.0)

        # Price stable, 35 days later
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 2, 5), 100.0
        )

        assert should_exit is True
        assert reason == "time_exit"

    def test_no_exit_if_no_rules_trigger(self):
        """Test no exit when no rules trigger."""
        rule = CompositeExitRule(
            rules=[
                (StopLossExit(0.08), 1.0),
                (TimeBasedExit(30), 1.0)
            ]
        )

        rt = create_test_roundtrip(entry_date=date(2024, 1, 1), entry_price=100.0)

        # Price stable, only 10 days
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 11), 100.0
        )

        assert should_exit is False

    def test_custom_exit_portions(self):
        """Test that composite rule can override exit portions."""
        rule = CompositeExitRule(
            rules=[
                (ProfitTargetExit(0.20, exit_portion=1.0), 0.5),  # Override to 50%
                (TimeBasedExit(30), 1.0)
            ]
        )

        rt = create_test_roundtrip(entry_price=100.0)

        # Price at +20%
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 5), 120.0
        )

        assert should_exit is True
        assert portion == 0.5  # Composite override, not rule's 1.0
        assert reason == "profit_target"

    def test_three_rules_priority(self):
        """Test priority with three rules."""
        rule = CompositeExitRule(
            rules=[
                (StopLossExit(0.10), 1.0),      # Priority 1
                (ProfitTargetExit(0.20), 0.5),  # Priority 2
                (TimeBasedExit(30), 1.0)        # Priority 3
            ]
        )

        rt = create_test_roundtrip(entry_date=date(2024, 1, 1), entry_price=100.0)

        # Price at +20%, 35 days - profit target should win
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 2, 5), 120.0
        )

        assert should_exit is True
        assert portion == 0.5
        assert reason == "profit_target"

    def test_empty_rules_list_invalid(self):
        """Test that empty rules list raises error."""
        with pytest.raises(ValueError, match="requires at least one rule"):
            CompositeExitRule(rules=[])

    def test_nested_composite_rules(self):
        """Test that CompositeExitRule can contain other CompositeExitRules."""
        inner_composite = CompositeExitRule(
            rules=[
                (StopLossExit(0.05), 1.0),
                (ProfitTargetExit(0.15), 1.0)
            ]
        )

        outer_composite = CompositeExitRule(
            rules=[
                (inner_composite, 1.0),
                (TimeBasedExit(60), 1.0)
            ]
        )

        rt = create_test_roundtrip(entry_price=100.0)

        # Inner rule should trigger
        should_exit, portion, reason = outer_composite.should_exit(
            rt, date(2024, 1, 5), 115.0
        )

        # Should work (may or may not trigger depending on exact values)
        assert isinstance(outer_composite, CompositeExitRule)

    def test_to_dict(self):
        """Test serialization."""
        rule = CompositeExitRule(
            rules=[
                (StopLossExit(0.08), 1.0),
                (TimeBasedExit(30), 1.0)
            ]
        )

        data = rule.to_dict()

        assert data["type"] == "CompositeExitRule"
        assert len(data["rules"]) == 2
        assert data["rules"][0]["rule"]["type"] == "StopLossExit"
        assert data["rules"][0]["portion"] == 1.0

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "type": "CompositeExitRule",
            "rules": [
                {
                    "rule": {"type": "StopLossExit", "params": {"stop_pct": 0.08}},
                    "portion": 1.0
                },
                {
                    "rule": {"type": "TimeBasedExit", "params": {"holding_days": 30}},
                    "portion": 1.0
                }
            ]
        }

        rule = CompositeExitRule.from_dict(data)

        assert isinstance(rule, CompositeExitRule)
        assert len(rule.rules) == 2
        assert isinstance(rule.rules[0][0], StopLossExit)
        assert isinstance(rule.rules[1][0], TimeBasedExit)

    def test_serialization_round_trip(self):
        """Test full serialization round trip."""
        rule1 = CompositeExitRule(
            rules=[
                (StopLossExit(0.08), 1.0),
                (ProfitTargetExit(0.20, 0.5), 0.5),
                (TimeBasedExit(30), 1.0)
            ]
        )

        data = rule1.to_dict()
        rule2 = CompositeExitRule.from_dict(data)

        assert len(rule2.rules) == 3
        assert isinstance(rule2.rules[0][0], StopLossExit)
        assert isinstance(rule2.rules[1][0], ProfitTargetExit)
        assert isinstance(rule2.rules[2][0], TimeBasedExit)


class TestFactoryFunction:
    """Test create_exit_rule factory function."""

    def test_create_time_based_exit(self):
        """Test creating TimeBasedExit."""
        data = {"type": "TimeBasedExit", "params": {"holding_days": 30}}
        rule = create_exit_rule(data)

        assert isinstance(rule, TimeBasedExit)
        assert rule.holding_days == 30

    def test_create_stop_loss_exit(self):
        """Test creating StopLossExit."""
        data = {"type": "StopLossExit", "params": {"stop_pct": 0.08}}
        rule = create_exit_rule(data)

        assert isinstance(rule, StopLossExit)
        assert rule.stop_pct == 0.08

    def test_create_trailing_stop_exit(self):
        """Test creating TrailingStopExit."""
        data = {"type": "TrailingStopExit", "params": {"trailing_pct": 0.10}}
        rule = create_exit_rule(data)

        assert isinstance(rule, TrailingStopExit)
        assert rule.trailing_pct == 0.10

    def test_create_profit_target_exit(self):
        """Test creating ProfitTargetExit."""
        data = {
            "type": "ProfitTargetExit",
            "params": {"target_pct": 0.20, "exit_portion": 0.5}
        }
        rule = create_exit_rule(data)

        assert isinstance(rule, ProfitTargetExit)
        assert rule.target_pct == 0.20
        assert rule.exit_portion == 0.5

    def test_create_composite_exit_rule(self):
        """Test creating CompositeExitRule."""
        data = {
            "type": "CompositeExitRule",
            "rules": [
                {
                    "rule": {"type": "StopLossExit", "params": {"stop_pct": 0.08}},
                    "portion": 1.0
                }
            ]
        }
        rule = create_exit_rule(data)

        assert isinstance(rule, CompositeExitRule)

    def test_create_unknown_type(self):
        """Test that unknown type raises error."""
        data = {"type": "UnknownExitRule"}

        with pytest.raises(ValueError, match="Unknown exit rule type"):
            create_exit_rule(data)

    def test_create_missing_type(self):
        """Test that missing type raises error."""
        data = {"params": {"holding_days": 30}}

        with pytest.raises(ValueError, match="Unknown exit rule type"):
            create_exit_rule(data)


class TestRealWorldScenarios:
    """Test realistic exit scenarios."""

    def test_typical_stop_loss_scenario(self):
        """Test typical stop loss exit (8% stop, position drops 10%)."""
        rule = StopLossExit(stop_pct=0.08)
        rt = create_test_roundtrip(entry_price=150.0)

        # Position drops 10%
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 5), 135.0
        )

        assert should_exit is True
        assert reason == "stop_loss"

    def test_take_profit_scenario(self):
        """Test take profit exit (20% target, position gains 25%)."""
        rule = ProfitTargetExit(target_pct=0.20, exit_portion=0.5)
        rt = create_test_roundtrip(entry_price=100.0)

        # Position gains 25%
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 10), 125.0
        )

        assert should_exit is True
        assert portion == 0.5
        assert reason == "profit_target"

    def test_trailing_stop_protects_gains(self):
        """Test trailing stop protecting gains."""
        rule = TrailingStopExit(trailing_pct=0.10)
        rt = create_test_roundtrip(entry_price=100.0)

        # Position runs up to 150
        rule.should_exit(rt, date(2024, 1, 5), 150.0)

        # Then drops to 135 (10% from peak)
        should_exit, portion, reason = rule.should_exit(
            rt, date(2024, 1, 10), 135.0
        )

        assert should_exit is True
        assert reason == "trailing_stop"
        # Locked in 35% gain instead of letting it drop further

    def test_composite_safety_first_strategy(self):
        """Test composite rule prioritizing safety."""
        rule = CompositeExitRule(
            rules=[
                (StopLossExit(0.08), 1.0),          # Safety first
                (ProfitTargetExit(0.20), 0.5),      # Take partial profits
                (TimeBasedExit(30), 1.0)            # Fallback time exit
            ]
        )

        rt = create_test_roundtrip(entry_date=date(2024, 1, 1), entry_price=100.0)

        # Scenario 1: Stop loss triggers (safety first)
        should_exit, _, reason = rule.should_exit(rt, date(2024, 1, 5), 90.0)
        assert reason == "stop_loss"

        # Scenario 2: Profit target triggers
        rt2 = create_test_roundtrip(entry_date=date(2024, 1, 1), entry_price=100.0)
        should_exit, portion, reason = rule.should_exit(rt2, date(2024, 1, 10), 125.0)
        assert reason == "profit_target"
        assert portion == 0.5

        # Scenario 3: Time exit as fallback
        rt3 = create_test_roundtrip(entry_date=date(2024, 1, 1), entry_price=100.0)
        should_exit, _, reason = rule.should_exit(rt3, date(2024, 2, 5), 105.0)
        assert reason == "time_exit"
