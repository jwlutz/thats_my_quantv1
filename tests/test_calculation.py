# tests/test_calculation.py

import pytest
from datetime import date
import pandas as pd
from backtester.calculation import (
    Calculation,
    EarningsSurprise,
    DayChange,
    PERatio,
    InstitutionalOwnership,
    create_calculation
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


class TestEarningsSurprise:
    """Test EarningsSurprise calculation with mocked data."""

    def test_calculate_with_valid_data(self):
        provider = MockDataProvider()
        provider.earnings_data_return = {'surprise_pct': 0.08}

        calc = EarningsSurprise()
        result = calc.calculate('AAPL', date(2024, 2, 1), provider)

        assert result == 0.08

    def test_calculate_with_no_data(self):
        provider = MockDataProvider()
        provider.earnings_data_return = None

        calc = EarningsSurprise()
        result = calc.calculate('AAPL', date(2024, 2, 1), provider)

        assert result is None

    def test_calculate_with_missing_surprise_pct(self):
        provider = MockDataProvider()
        provider.earnings_data_return = {'reported': 1.5, 'estimate': 1.4}  # No surprise_pct

        calc = EarningsSurprise()
        result = calc.calculate('AAPL', date(2024, 2, 1), provider)

        assert result is None

    def test_to_dict(self):
        calc = EarningsSurprise()
        assert calc.to_dict() == {'type': 'EarningsSurprise'}

    def test_from_dict(self):
        data = {'type': 'EarningsSurprise'}
        calc = EarningsSurprise.from_dict(data)
        assert isinstance(calc, EarningsSurprise)

    def test_serialization_round_trip(self):
        calc = EarningsSurprise()
        data = calc.to_dict()
        calc2 = EarningsSurprise.from_dict(data)
        assert isinstance(calc2, EarningsSurprise)
        assert calc2.to_dict() == data


class TestDayChange:
    """Test DayChange calculation with mocked data."""

    def test_calculate_green_day(self):
        provider = MockDataProvider()
        provider.bar_return = {
            'open': 100.0,
            'close': 105.0,
            'high': 106.0,
            'low': 99.0,
            'volume': 1000000
        }

        calc = DayChange()
        result = calc.calculate('AAPL', date(2024, 2, 1), provider)

        assert result == 0.05  # 5% gain

    def test_calculate_red_day(self):
        provider = MockDataProvider()
        provider.bar_return = {
            'open': 100.0,
            'close': 98.0,
            'high': 101.0,
            'low': 97.0,
            'volume': 1000000
        }

        calc = DayChange()
        result = calc.calculate('AAPL', date(2024, 2, 1), provider)

        assert result == -0.02  # 2% loss

    def test_calculate_flat_day(self):
        provider = MockDataProvider()
        provider.bar_return = {
            'open': 100.0,
            'close': 100.0,
            'high': 101.0,
            'low': 99.0,
            'volume': 1000000
        }

        calc = DayChange()
        result = calc.calculate('AAPL', date(2024, 2, 1), provider)

        assert result == 0.0

    def test_calculate_with_zero_open(self):
        provider = MockDataProvider()
        provider.bar_return = {
            'open': 0.0,
            'close': 100.0,
            'high': 100.0,
            'low': 0.0,
            'volume': 1000000
        }

        calc = DayChange()
        result = calc.calculate('AAPL', date(2024, 2, 1), provider)

        assert result is None  # Avoid division by zero

    def test_calculate_with_no_bar(self):
        provider = MockDataProvider()
        provider.bar_return = None

        calc = DayChange()
        result = calc.calculate('AAPL', date(2024, 2, 1), provider)

        assert result is None

    def test_to_dict(self):
        calc = DayChange()
        assert calc.to_dict() == {'type': 'DayChange'}

    def test_from_dict(self):
        data = {'type': 'DayChange'}
        calc = DayChange.from_dict(data)
        assert isinstance(calc, DayChange)


class TestPERatio:
    """Test PERatio calculation with mocked data."""

    def test_calculate_with_valid_pe(self):
        provider = MockDataProvider()
        provider.info_return = {'trailingPE': 25.5}

        calc = PERatio()
        result = calc.calculate('AAPL', date(2024, 2, 1), provider)

        assert result == 25.5

    def test_calculate_with_high_pe(self):
        provider = MockDataProvider()
        provider.info_return = {'trailingPE': 150.0}

        calc = PERatio()
        result = calc.calculate('TSLA', date(2024, 2, 1), provider)

        assert result == 150.0

    def test_calculate_with_no_info(self):
        provider = MockDataProvider()
        provider.info_return = None

        calc = PERatio()
        result = calc.calculate('AAPL', date(2024, 2, 1), provider)

        assert result is None

    def test_calculate_with_missing_pe(self):
        provider = MockDataProvider()
        provider.info_return = {'marketCap': 3000000000000}  # No trailingPE

        calc = PERatio()
        result = calc.calculate('AAPL', date(2024, 2, 1), provider)

        assert result is None

    def test_to_dict(self):
        calc = PERatio()
        assert calc.to_dict() == {'type': 'PERatio'}

    def test_from_dict(self):
        data = {'type': 'PERatio'}
        calc = PERatio.from_dict(data)
        assert isinstance(calc, PERatio)


class TestInstitutionalOwnership:
    """Test InstitutionalOwnership calculation with mocked data."""

    def test_calculate_with_holders(self):
        provider = MockDataProvider()
        provider.institutional_holders_return = pd.DataFrame({
            'Holder': ['Vanguard', 'BlackRock', 'StateStreet'],
            'pctHeld': [0.25, 0.20, 0.15]
        })

        calc = InstitutionalOwnership()
        result = calc.calculate('AAPL', date(2024, 2, 1), provider)

        assert result == 0.60  # 60% total

    def test_calculate_with_single_holder(self):
        provider = MockDataProvider()
        provider.institutional_holders_return = pd.DataFrame({
            'Holder': ['Vanguard'],
            'pctHeld': [0.30]
        })

        calc = InstitutionalOwnership()
        result = calc.calculate('AAPL', date(2024, 2, 1), provider)

        assert result == 0.30

    def test_calculate_with_empty_holders(self):
        provider = MockDataProvider()
        provider.institutional_holders_return = pd.DataFrame()

        calc = InstitutionalOwnership()
        result = calc.calculate('AAPL', date(2024, 2, 1), provider)

        assert result is None

    def test_calculate_with_no_holders(self):
        provider = MockDataProvider()
        provider.institutional_holders_return = None

        calc = InstitutionalOwnership()
        result = calc.calculate('AAPL', date(2024, 2, 1), provider)

        assert result is None

    def test_to_dict(self):
        calc = InstitutionalOwnership()
        assert calc.to_dict() == {'type': 'InstitutionalOwnership'}

    def test_from_dict(self):
        data = {'type': 'InstitutionalOwnership'}
        calc = InstitutionalOwnership.from_dict(data)
        assert isinstance(calc, InstitutionalOwnership)


class TestFactoryFunction:
    """Test create_calculation factory function."""

    def test_create_earnings_surprise(self):
        data = {'type': 'EarningsSurprise'}
        calc = create_calculation(data)
        assert isinstance(calc, EarningsSurprise)

    def test_create_day_change(self):
        data = {'type': 'DayChange'}
        calc = create_calculation(data)
        assert isinstance(calc, DayChange)

    def test_create_pe_ratio(self):
        data = {'type': 'PERatio'}
        calc = create_calculation(data)
        assert isinstance(calc, PERatio)

    def test_create_institutional_ownership(self):
        data = {'type': 'InstitutionalOwnership'}
        calc = create_calculation(data)
        assert isinstance(calc, InstitutionalOwnership)

    def test_create_unknown_type(self):
        data = {'type': 'UnknownCalculation'}
        with pytest.raises(ValueError, match="Unknown calculation type"):
            create_calculation(data)

    def test_create_missing_type(self):
        data = {}
        with pytest.raises(ValueError, match="Unknown calculation type"):
            create_calculation(data)


# Integration tests with real YFinanceProvider
class TestRealDataIntegration:
    """Integration tests using real market data from yfinance."""

    @pytest.fixture
    def provider(self):
        """Real YFinanceProvider instance."""
        return YFinanceProvider()

    def test_day_change_real_data(self, provider):
        """Test DayChange with real AAPL data."""
        calc = DayChange()
        # Use a known trading day
        result = calc.calculate('AAPL', date(2024, 1, 5), provider)

        # Should return a value (positive or negative change)
        assert result is not None
        assert isinstance(result, float)
        # Sanity check: daily change typically within ±20%
        assert -0.20 < result < 0.20

    def test_pe_ratio_real_data(self, provider):
        """Test PERatio with real AAPL data."""
        calc = PERatio()
        result = calc.calculate('AAPL', date(2024, 1, 5), provider)

        # AAPL should have a P/E ratio
        assert result is not None
        assert isinstance(result, float)
        # Sanity check: AAPL P/E typically 15-35
        assert 10 < result < 50

    def test_institutional_ownership_real_data(self, provider):
        """Test InstitutionalOwnership with real AAPL data."""
        calc = InstitutionalOwnership()
        result = calc.calculate('AAPL', date(2024, 1, 5), provider)

        # AAPL should have institutional ownership data
        if result is not None:  # May not always be available
            assert isinstance(result, float)
            # Sanity check: institutional ownership 0-100%
            assert 0.0 <= result <= 1.0

    def test_earnings_surprise_real_data(self, provider):
        """Test EarningsSurprise with real AAPL data."""
        calc = EarningsSurprise()
        # Use date after known earnings report (Feb 2024)
        result = calc.calculate('AAPL', date(2024, 2, 5), provider)

        # May or may not have earnings data depending on timing
        if result is not None:
            assert isinstance(result, float)
            # Sanity check: earnings surprise typically ±50%
            assert -0.50 < result < 0.50

    def test_invalid_ticker(self, provider):
        """Test calculations with invalid ticker."""
        calc = DayChange()
        result = calc.calculate('INVALIDTICKER123', date(2024, 1, 5), provider)

        # Should return None for invalid ticker
        assert result is None

    def test_future_date(self, provider):
        """Test calculations with future date."""
        calc = DayChange()
        result = calc.calculate('AAPL', date(2030, 1, 1), provider)

        # Should return None for future date
        assert result is None

    def test_weekend_date(self, provider):
        """Test calculations with weekend date."""
        calc = DayChange()
        # January 6, 2024 was a Saturday
        result = calc.calculate('AAPL', date(2024, 1, 6), provider)

        # Should return None for non-trading day
        assert result is None

    def test_multiple_calculations_same_provider(self, provider):
        """Test multiple calculations reusing same provider (caching)."""
        calc1 = DayChange()
        calc2 = PERatio()

        test_date = date(2024, 1, 5)

        result1 = calc1.calculate('AAPL', test_date, provider)
        result2 = calc2.calculate('AAPL', test_date, provider)

        assert result1 is not None
        assert result2 is not None
        assert isinstance(result1, float)
        assert isinstance(result2, float)
