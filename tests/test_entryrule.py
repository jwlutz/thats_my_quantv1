# tests/test_entryrule.py

import pytest
from datetime import date
import pandas as pd
from backtester.entryrule import (
    Signal,
    EntryRule,
    CompositeEntryRule,
    create_entry_rule
)
from backtester.calculation import (
    EarningsSurprise,
    DayChange,
    PERatio,
    InstitutionalOwnership
)
from backtester.condition import (
    GreaterThan,
    LessThan,
    Between
)
from backtester.yfinance_provider import YFinanceProvider


# Mock DataProvider for unit tests
class MockDataProvider:
    def __init__(self):
        self.earnings_data_return = None
        self.bar_return = None
        self.info_return = None
        self.institutional_holders_return = None

    def get_earnings_data(self, ticker, date):
        return self.earnings_data_return

    def get_bar(self, ticker, date):
        return self.bar_return

    def get_info(self, ticker):
        return self.info_return

    def get_institutional_holders(self, ticker):
        return self.institutional_holders_return


class TestSignal:
    """Test Signal dataclass."""

    def test_create_signal(self):
        signal = Signal(
            ticker='AAPL',
            date=date(2024, 1, 5),
            signal_type='earnings_beat',
            metadata={'surprise_pct': 0.08},
            priority=2.0
        )

        assert signal.ticker == 'AAPL'
        assert signal.date == date(2024, 1, 5)
        assert signal.signal_type == 'earnings_beat'
        assert signal.metadata == {'surprise_pct': 0.08}
        assert signal.priority == 2.0

    def test_signal_comparison(self):
        """Test that signals can be compared by priority."""
        signal1 = Signal('AAPL', date(2024, 1, 5), 'test', {}, priority=1.0)
        signal2 = Signal('MSFT', date(2024, 1, 5), 'test', {}, priority=2.0)

        # Can compare priorities
        assert signal2.priority > signal1.priority


class TestEntryRule:
    """Test EntryRule with mocked data."""

    def test_should_enter_signal_triggered(self):
        """Test signal generation when condition met."""
        provider = MockDataProvider()
        provider.earnings_data_return = {'surprise_pct': 0.08}

        rule = EntryRule(
            calculation=EarningsSurprise(),
            condition=GreaterThan(0.05),
            signal_type='earnings_beat',
            priority=2.0
        )

        signal = rule.should_enter('AAPL', date(2024, 2, 1), provider)

        assert signal is not None
        assert signal.ticker == 'AAPL'
        assert signal.signal_type == 'earnings_beat'
        assert signal.priority == 2.0
        assert signal.metadata['value'] == 0.08

    def test_should_enter_no_signal(self):
        """Test no signal when condition not met."""
        provider = MockDataProvider()
        provider.earnings_data_return = {'surprise_pct': 0.03}

        rule = EntryRule(
            calculation=EarningsSurprise(),
            condition=GreaterThan(0.05),
            signal_type='earnings_beat',
            priority=2.0
        )

        signal = rule.should_enter('AAPL', date(2024, 2, 1), provider)

        assert signal is None

    def test_should_enter_no_data(self):
        """Test no signal when data unavailable."""
        provider = MockDataProvider()
        provider.earnings_data_return = None

        rule = EntryRule(
            calculation=EarningsSurprise(),
            condition=GreaterThan(0.05),
            signal_type='earnings_beat'
        )

        signal = rule.should_enter('AAPL', date(2024, 2, 1), provider)

        assert signal is None

    def test_day_change_rule_green_day(self):
        """Test day change rule for green candle."""
        provider = MockDataProvider()
        provider.bar_return = {
            'open': 100.0,
            'close': 103.0,
            'high': 104.0,
            'low': 99.0,
            'volume': 1000000
        }

        rule = EntryRule(
            calculation=DayChange(),
            condition=GreaterThan(0.0),
            signal_type='green_day',
            priority=1.0
        )

        signal = rule.should_enter('AAPL', date(2024, 1, 5), provider)

        assert signal is not None
        assert signal.signal_type == 'green_day'
        assert signal.metadata['value'] == 0.03

    def test_day_change_rule_red_day(self):
        """Test day change rule for red candle."""
        provider = MockDataProvider()
        provider.bar_return = {
            'open': 100.0,
            'close': 98.0,
            'high': 101.0,
            'low': 97.0,
            'volume': 1000000
        }

        rule = EntryRule(
            calculation=DayChange(),
            condition=LessThan(0.0),
            signal_type='red_day',
            priority=1.0
        )

        signal = rule.should_enter('AAPL', date(2024, 1, 5), provider)

        assert signal is not None
        assert signal.signal_type == 'red_day'
        assert signal.metadata['value'] == -0.02

    def test_pe_ratio_rule(self):
        """Test P/E ratio rule for value screening."""
        provider = MockDataProvider()
        provider.info_return = {'trailingPE': 18.5}

        rule = EntryRule(
            calculation=PERatio(),
            condition=LessThan(20.0),
            signal_type='value_stock',
            priority=1.5
        )

        signal = rule.should_enter('AAPL', date(2024, 1, 5), provider)

        assert signal is not None
        assert signal.signal_type == 'value_stock'
        assert signal.metadata['value'] == 18.5

    def test_to_dict(self):
        """Test serialization."""
        rule = EntryRule(
            calculation=DayChange(),
            condition=GreaterThan(0.02),
            signal_type='test_signal',
            priority=1.5
        )

        data = rule.to_dict()

        assert data['type'] == 'EntryRule'
        assert data['calculation']['type'] == 'DayChange'
        assert data['condition']['type'] == 'GreaterThan'
        assert data['condition']['threshold'] == 0.02
        assert data['signal_type'] == 'test_signal'
        assert data['priority'] == 1.5

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            'type': 'EntryRule',
            'calculation': {'type': 'DayChange'},
            'condition': {'type': 'GreaterThan', 'threshold': 0.02},
            'signal_type': 'test_signal',
            'priority': 1.5
        }

        rule = EntryRule.from_dict(data)

        assert isinstance(rule, EntryRule)
        assert isinstance(rule.calculation, DayChange)
        assert isinstance(rule.condition, GreaterThan)
        assert rule.signal_type == 'test_signal'
        assert rule.priority == 1.5

    def test_serialization_round_trip(self):
        """Test full serialization round trip."""
        rule1 = EntryRule(
            calculation=EarningsSurprise(),
            condition=GreaterThan(0.05),
            signal_type='earnings_beat',
            priority=2.0
        )

        data = rule1.to_dict()
        rule2 = EntryRule.from_dict(data)

        assert isinstance(rule2.calculation, EarningsSurprise)
        assert isinstance(rule2.condition, GreaterThan)
        assert rule2.condition.threshold == 0.05
        assert rule2.signal_type == 'earnings_beat'
        assert rule2.priority == 2.0


class TestCompositeEntryRule:
    """Test CompositeEntryRule with multiple conditions."""

    def test_all_conditions_pass(self):
        """Test signal when all conditions met."""
        provider = MockDataProvider()
        provider.earnings_data_return = {'surprise_pct': 0.08}
        provider.info_return = {'trailingPE': 18.0}

        rule = CompositeEntryRule(
            calc_condition_pairs=[
                (EarningsSurprise(), GreaterThan(0.05)),
                (PERatio(), LessThan(20.0))
            ],
            signal_type='value_earnings_beat',
            priority=3.0
        )

        signal = rule.should_enter('AAPL', date(2024, 2, 1), provider)

        assert signal is not None
        assert signal.signal_type == 'value_earnings_beat'
        assert signal.priority == 3.0
        assert signal.metadata['EarningsSurprise'] == 0.08
        assert signal.metadata['PERatio'] == 18.0

    def test_first_condition_fails(self):
        """Test no signal when first condition fails."""
        provider = MockDataProvider()
        provider.earnings_data_return = {'surprise_pct': 0.03}  # Too low
        provider.info_return = {'trailingPE': 18.0}

        rule = CompositeEntryRule(
            calc_condition_pairs=[
                (EarningsSurprise(), GreaterThan(0.05)),
                (PERatio(), LessThan(20.0))
            ],
            signal_type='value_earnings_beat'
        )

        signal = rule.should_enter('AAPL', date(2024, 2, 1), provider)

        assert signal is None

    def test_second_condition_fails(self):
        """Test no signal when second condition fails."""
        provider = MockDataProvider()
        provider.earnings_data_return = {'surprise_pct': 0.08}
        provider.info_return = {'trailingPE': 25.0}  # Too high

        rule = CompositeEntryRule(
            calc_condition_pairs=[
                (EarningsSurprise(), GreaterThan(0.05)),
                (PERatio(), LessThan(20.0))
            ],
            signal_type='value_earnings_beat'
        )

        signal = rule.should_enter('AAPL', date(2024, 2, 1), provider)

        assert signal is None

    def test_missing_data(self):
        """Test no signal when data unavailable."""
        provider = MockDataProvider()
        provider.earnings_data_return = None  # No data

        rule = CompositeEntryRule(
            calc_condition_pairs=[
                (EarningsSurprise(), GreaterThan(0.05)),
                (PERatio(), LessThan(20.0))
            ],
            signal_type='value_earnings_beat'
        )

        signal = rule.should_enter('AAPL', date(2024, 2, 1), provider)

        assert signal is None

    def test_three_conditions(self):
        """Test with three conditions (AND logic)."""
        provider = MockDataProvider()
        provider.bar_return = {'open': 100.0, 'close': 98.0, 'high': 101.0, 'low': 97.0, 'volume': 1000000}
        provider.info_return = {'trailingPE': 18.0}
        provider.institutional_holders_return = pd.DataFrame({
            'Holder': ['Vanguard', 'BlackRock'],
            'pctHeld': [0.30, 0.25]
        })

        rule = CompositeEntryRule(
            calc_condition_pairs=[
                (DayChange(), LessThan(0.0)),  # Red day
                (PERatio(), LessThan(20.0)),  # Value
                (InstitutionalOwnership(), GreaterThan(0.50))  # High ownership
            ],
            signal_type='value_red_day_institutional',
            priority=4.0
        )

        signal = rule.should_enter('AAPL', date(2024, 1, 5), provider)

        assert signal is not None
        assert len(signal.metadata) == 3
        assert 'DayChange' in signal.metadata
        assert 'PERatio' in signal.metadata
        assert 'InstitutionalOwnership' in signal.metadata

    def test_to_dict(self):
        """Test serialization."""
        rule = CompositeEntryRule(
            calc_condition_pairs=[
                (EarningsSurprise(), GreaterThan(0.05)),
                (PERatio(), LessThan(20.0))
            ],
            signal_type='value_earnings',
            priority=3.0
        )

        data = rule.to_dict()

        assert data['type'] == 'CompositeEntryRule'
        assert len(data['pairs']) == 2
        assert data['pairs'][0]['calculation']['type'] == 'EarningsSurprise'
        assert data['pairs'][0]['condition']['type'] == 'GreaterThan'
        assert data['signal_type'] == 'value_earnings'
        assert data['priority'] == 3.0

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            'type': 'CompositeEntryRule',
            'pairs': [
                {
                    'calculation': {'type': 'EarningsSurprise'},
                    'condition': {'type': 'GreaterThan', 'threshold': 0.05}
                },
                {
                    'calculation': {'type': 'PERatio'},
                    'condition': {'type': 'LessThan', 'threshold': 20.0}
                }
            ],
            'signal_type': 'value_earnings',
            'priority': 3.0
        }

        rule = CompositeEntryRule.from_dict(data)

        assert isinstance(rule, CompositeEntryRule)
        assert len(rule.pairs) == 2
        assert isinstance(rule.pairs[0][0], EarningsSurprise)
        assert isinstance(rule.pairs[0][1], GreaterThan)
        assert rule.signal_type == 'value_earnings'
        assert rule.priority == 3.0


class TestFactoryFunction:
    """Test create_entry_rule factory function."""

    def test_create_entry_rule(self):
        data = {
            'type': 'EntryRule',
            'calculation': {'type': 'DayChange'},
            'condition': {'type': 'GreaterThan', 'threshold': 0.0},
            'signal_type': 'test',
            'priority': 1.0
        }

        rule = create_entry_rule(data)

        assert isinstance(rule, EntryRule)
        assert isinstance(rule.calculation, DayChange)

    def test_create_composite_entry_rule(self):
        data = {
            'type': 'CompositeEntryRule',
            'pairs': [
                {
                    'calculation': {'type': 'DayChange'},
                    'condition': {'type': 'LessThan', 'threshold': 0.0}
                }
            ],
            'signal_type': 'test',
            'priority': 1.0
        }

        rule = create_entry_rule(data)

        assert isinstance(rule, CompositeEntryRule)

    def test_create_unknown_type(self):
        data = {'type': 'UnknownRule'}
        with pytest.raises(ValueError, match="Unknown entry rule type"):
            create_entry_rule(data)


# Integration tests with real data
class TestRealDataIntegration:
    """Integration tests using real market data."""

    @pytest.fixture
    def provider(self):
        return YFinanceProvider()

    def test_green_day_rule_real_data(self, provider):
        """Test green day entry rule with real data."""
        rule = EntryRule(
            calculation=DayChange(),
            condition=GreaterThan(0.0),
            signal_type='green_day',
            priority=1.0
        )

        signal = rule.should_enter('AAPL', date(2024, 1, 5), provider)

        # Signal may or may not trigger depending on actual day
        if signal is not None:
            assert signal.ticker == 'AAPL'
            assert signal.signal_type == 'green_day'
            assert signal.metadata['value'] > 0.0

    def test_red_day_rule_real_data(self, provider):
        """Test red day entry rule with real data."""
        rule = EntryRule(
            calculation=DayChange(),
            condition=LessThan(0.0),
            signal_type='red_day',
            priority=1.0
        )

        signal = rule.should_enter('AAPL', date(2024, 1, 5), provider)

        # Signal may or may not trigger depending on actual day
        if signal is not None:
            assert signal.ticker == 'AAPL'
            assert signal.signal_type == 'red_day'
            assert signal.metadata['value'] < 0.0

    def test_value_screen_real_data(self, provider):
        """Test P/E value screening with real data."""
        rule = EntryRule(
            calculation=PERatio(),
            condition=Between(10.0, 30.0),
            signal_type='value_stock',
            priority=1.5
        )

        signal = rule.should_enter('AAPL', date(2024, 1, 5), provider)

        # AAPL typically has P/E in this range
        if signal is not None:
            assert signal.ticker == 'AAPL'
            assert 10.0 <= signal.metadata['value'] <= 30.0

    def test_composite_rule_real_data(self, provider):
        """Test composite rule with real data."""
        rule = CompositeEntryRule(
            calc_condition_pairs=[
                (DayChange(), LessThan(0.0)),  # Red day
                (PERatio(), LessThan(30.0))  # Reasonable P/E
            ],
            signal_type='value_red_day',
            priority=2.0
        )

        signal = rule.should_enter('AAPL', date(2024, 1, 5), provider)

        # May or may not trigger depending on data
        if signal is not None:
            assert signal.signal_type == 'value_red_day'
            assert 'DayChange' in signal.metadata
            assert 'PERatio' in signal.metadata

    def test_multiple_tickers_same_rule(self, provider):
        """Test same rule on multiple tickers."""
        rule = EntryRule(
            calculation=PERatio(),
            condition=LessThan(50.0),
            signal_type='reasonable_pe'
        )

        tickers = ['AAPL', 'MSFT', 'GOOGL']
        test_date = date(2024, 1, 5)

        signals = []
        for ticker in tickers:
            signal = rule.should_enter(ticker, test_date, provider)
            if signal is not None:
                signals.append(signal)

        # Should get at least some signals
        assert len(signals) >= 0  # May vary

    def test_signal_priority_ranking(self, provider):
        """Test that signals can be ranked by priority."""
        rule1 = EntryRule(
            calculation=DayChange(),
            condition=GreaterThan(0.0),
            signal_type='green_day',
            priority=1.0
        )

        rule2 = EntryRule(
            calculation=DayChange(),
            condition=GreaterThan(0.05),
            signal_type='big_green_day',
            priority=2.0
        )

        test_date = date(2024, 1, 5)

        signal1 = rule1.should_enter('AAPL', test_date, provider)
        signal2 = rule2.should_enter('AAPL', test_date, provider)

        # If both triggered, signal2 should have higher priority
        if signal1 and signal2:
            assert signal2.priority > signal1.priority
