import pytest
from backtester.positionsizer import (
    PositionSizer,
    FixedDollarAmount,
    PercentPortfolio,
    PercentAvailableCash,
    EqualWeight,
    FixedShares,
    RiskParity,
    create_position_sizer
)
from backtester.portfolio import Portfolio
from backtester.transactioncost import TransactionCost


class TestFixedDollarAmount:
    """Test FixedDollarAmount position sizer."""
    
    def test_basic_calculation(self):
        """Calculate shares for fixed dollar amount."""
        sizer = FixedDollarAmount(dollar_amount=5000)
        shares = sizer.calculate_shares(
            price=100.0,
            available_cash=10000,
            portfolio_value=50000
        )
        assert shares == 50.0  # $5000 / $100
    
    def test_respects_available_cash(self):
        """Don't exceed available cash."""
        sizer = FixedDollarAmount(dollar_amount=5000)
        shares = sizer.calculate_shares(
            price=100.0,
            available_cash=3000,  # Only $3k available
            portfolio_value=50000
        )
        assert shares == 30.0  # $3000 / $100 (not 50)
    
    def test_fractional_shares(self):
        """Support fractional shares."""
        sizer = FixedDollarAmount(dollar_amount=5000)
        shares = sizer.calculate_shares(
            price=333.33,
            available_cash=10000,
            portfolio_value=50000
        )
        assert abs(shares - 15.0) < 0.01  # $5000 / $333.33 ≈ 15.0
    
    def test_insufficient_cash_returns_zero(self):
        """Return 0 when no cash available."""
        sizer = FixedDollarAmount(dollar_amount=5000)
        shares = sizer.calculate_shares(
            price=100.0,
            available_cash=0,
            portfolio_value=50000
        )
        assert shares == 0.0
    
    def test_zero_price_raises_error(self):
        """Raise error for zero price."""
        sizer = FixedDollarAmount(dollar_amount=5000)
        with pytest.raises(ValueError, match="price must be positive"):
            sizer.calculate_shares(
                price=0,
                available_cash=10000,
                portfolio_value=50000
            )
    
    def test_negative_price_raises_error(self):
        """Raise error for negative price."""
        sizer = FixedDollarAmount(dollar_amount=5000)
        with pytest.raises(ValueError, match="price must be positive"):
            sizer.calculate_shares(
                price=-50,
                available_cash=10000,
                portfolio_value=50000
            )
    
    def test_zero_dollar_amount_raises_error(self):
        """Raise error for zero dollar amount."""
        with pytest.raises(ValueError, match="dollar_amount must be positive"):
            FixedDollarAmount(dollar_amount=0)
    
    def test_negative_dollar_amount_raises_error(self):
        """Raise error for negative dollar amount."""
        with pytest.raises(ValueError, match="dollar_amount must be positive"):
            FixedDollarAmount(dollar_amount=-1000)
    
    def test_serialization(self):
        """Test to_dict serialization."""
        sizer = FixedDollarAmount(dollar_amount=5000)
        data = sizer.to_dict()
        assert data == {
            'type': 'FixedDollarAmount',
            'dollar_amount': 5000
        }
    
    def test_deserialization(self):
        """Test from_dict deserialization."""
        data = {'dollar_amount': 5000}
        sizer = FixedDollarAmount.from_dict(data)
        assert sizer.dollar_amount == 5000
    
    def test_round_trip_serialization(self):
        """Test serialization round-trip."""
        sizer1 = FixedDollarAmount(dollar_amount=7500)
        data = sizer1.to_dict()
        sizer2 = FixedDollarAmount.from_dict(data)
        assert sizer2.dollar_amount == sizer1.dollar_amount


class TestPercentPortfolio:
    """Test PercentPortfolio position sizer."""
    
    def test_basic_calculation(self):
        """Calculate shares based on portfolio percentage."""
        sizer = PercentPortfolio(percent=0.10)  # 10%
        shares = sizer.calculate_shares(
            price=100.0,
            available_cash=50000,
            portfolio_value=50000
        )
        assert shares == 50.0  # 10% of $50k = $5k / $100
    
    def test_scales_with_portfolio_growth(self):
        """Position size grows with portfolio."""
        sizer = PercentPortfolio(percent=0.10)  # 10%
        
        # Small portfolio
        shares1 = sizer.calculate_shares(100.0, 50000, 50000)
        assert shares1 == 50.0  # $5k / $100
        
        # Larger portfolio
        shares2 = sizer.calculate_shares(100.0, 100000, 100000)
        assert shares2 == 100.0  # $10k / $100
    
    def test_respects_available_cash(self):
        """Don't exceed available cash."""
        sizer = PercentPortfolio(percent=0.20)  # 20%
        shares = sizer.calculate_shares(
            price=100.0,
            available_cash=5000,  # Only $5k cash
            portfolio_value=100000  # But 20% would be $20k
        )
        assert shares == 50.0  # Limited to $5k / $100
    
    def test_percent_validation_too_low(self):
        """Raise error for percent <= 0."""
        with pytest.raises(ValueError, match="percent must be between 0 and 1.0"):
            PercentPortfolio(percent=0)
    
    def test_percent_validation_too_high(self):
        """Raise error for percent > 1.0."""
        with pytest.raises(ValueError, match="percent must be between 0 and 1.0"):
            PercentPortfolio(percent=1.5)
    
    def test_100_percent_allowed(self):
        """Allow 100% (1.0)."""
        sizer = PercentPortfolio(percent=1.0)
        assert sizer.percent == 1.0
    
    def test_serialization(self):
        """Test to_dict serialization."""
        sizer = PercentPortfolio(percent=0.15)
        data = sizer.to_dict()
        assert data == {
            'type': 'PercentPortfolio',
            'percent': 0.15
        }
    
    def test_round_trip_serialization(self):
        """Test serialization round-trip."""
        sizer1 = PercentPortfolio(percent=0.25)
        data = sizer1.to_dict()
        sizer2 = PercentPortfolio.from_dict(data)
        assert sizer2.percent == sizer1.percent


class TestPercentAvailableCash:
    """Test PercentAvailableCash position sizer."""
    
    def test_basic_calculation(self):
        """Calculate shares based on cash percentage."""
        sizer = PercentAvailableCash(percent=0.50)  # 50%
        shares = sizer.calculate_shares(
            price=100.0,
            available_cash=10000,
            portfolio_value=50000
        )
        assert shares == 50.0  # 50% of $10k = $5k / $100
    
    def test_different_from_percent_portfolio(self):
        """PercentAvailableCash uses cash, not total value."""
        cash_sizer = PercentAvailableCash(percent=0.50)
        portfolio_sizer = PercentPortfolio(percent=0.50)
        
        # Same inputs
        price = 100.0
        available_cash = 20000
        portfolio_value = 100000  # Much larger than cash
        
        cash_shares = cash_sizer.calculate_shares(price, available_cash, portfolio_value)
        portfolio_shares = portfolio_sizer.calculate_shares(price, available_cash, portfolio_value)
        
        # Cash sizer: 50% of $20k = $10k
        assert cash_shares == 100.0
        
        # Portfolio sizer: 50% of $100k = $50k, but limited to $20k cash
        assert portfolio_shares == 200.0
        
        # Different results!
        assert cash_shares != portfolio_shares
    
    def test_serialization(self):
        """Test to_dict serialization."""
        sizer = PercentAvailableCash(percent=0.33)
        data = sizer.to_dict()
        assert data == {
            'type': 'PercentAvailableCash',
            'percent': 0.33
        }


class TestEqualWeight:
    """Test EqualWeight position sizer."""
    
    def test_basic_calculation_with_portfolio(self):
        """Calculate shares for equal weighting."""
        # Create portfolio with max_positions = 5
        portfolio = Portfolio(
            starting_capital=100000,
            max_positions=5,
            transaction_cost=TransactionCost(commission=0, slippage_pct=0)
        )
        
        sizer = EqualWeight()
        shares = sizer.calculate_shares(
            price=100.0,
            available_cash=100000,
            portfolio_value=100000,
            portfolio=portfolio
        )
        # $100k / 5 positions = $20k per position / $100 = 200 shares
        assert shares == 200.0
    
    def test_without_portfolio_uses_default(self):
        """Use default max_positions when portfolio not provided."""
        sizer = EqualWeight(default_max_positions=10)
        shares = sizer.calculate_shares(
            price=100.0,
            available_cash=100000,
            portfolio_value=100000,
            portfolio=None  # No portfolio
        )
        # $100k / 10 = $10k per position / $100 = 100 shares
        assert shares == 100.0
    
    def test_serialization(self):
        """Test to_dict serialization."""
        sizer = EqualWeight(default_max_positions=15)
        data = sizer.to_dict()
        assert data == {
            'type': 'EqualWeight',
            'default_max_positions': 15
        }
    
    def test_round_trip_serialization(self):
        """Test serialization round-trip."""
        sizer1 = EqualWeight(default_max_positions=7)
        data = sizer1.to_dict()
        sizer2 = EqualWeight.from_dict(data)
        assert sizer2.default_max_positions == sizer1.default_max_positions


class TestFixedShares:
    """Test FixedShares position sizer."""
    
    def test_basic_calculation(self):
        """Return fixed share count."""
        sizer = FixedShares(shares=100)
        result = sizer.calculate_shares(
            price=50.0,
            available_cash=10000,
            portfolio_value=50000
        )
        assert result == 100.0
    
    def test_insufficient_cash_returns_zero(self):
        """Return 0 when insufficient cash."""
        sizer = FixedShares(shares=100)
        result = sizer.calculate_shares(
            price=200.0,  # 100 shares * $200 = $20k needed
            available_cash=5000,  # Only $5k available
            portfolio_value=50000
        )
        assert result == 0.0
    
    def test_exact_cash_match(self):
        """Return shares when cash exactly matches."""
        sizer = FixedShares(shares=50)
        result = sizer.calculate_shares(
            price=100.0,  # 50 * $100 = $5k
            available_cash=5000,  # Exact match
            portfolio_value=50000
        )
        assert result == 50.0
    
    def test_fractional_shares(self):
        """Support fractional shares."""
        sizer = FixedShares(shares=50.5)
        assert sizer.shares == 50.5
    
    def test_serialization(self):
        """Test to_dict serialization."""
        sizer = FixedShares(shares=75)
        data = sizer.to_dict()
        assert data == {
            'type': 'FixedShares',
            'shares': 75
        }


class TestRiskParity:
    """Test RiskParity position sizer."""
    
    def test_basic_calculation_v1(self):
        """V1: Acts like FixedDollarAmount (no volatility adjustment yet)."""
        sizer = RiskParity(
            base_dollar_amount=5000,
            target_volatility=0.20,
            max_adjustment=2.0
        )
        shares = sizer.calculate_shares(
            price=100.0,
            available_cash=10000,
            portfolio_value=50000
        )
        # V1: No adjustment, just base amount
        assert shares == 50.0  # $5000 / $100
    
    def test_respects_available_cash(self):
        """Don't exceed available cash."""
        sizer = RiskParity(base_dollar_amount=10000)
        shares = sizer.calculate_shares(
            price=100.0,
            available_cash=3000,
            portfolio_value=50000
        )
        assert shares == 30.0  # Limited to $3k
    
    def test_parameter_validation(self):
        """Validate all parameters."""
        # base_dollar_amount must be positive
        with pytest.raises(ValueError, match="base_dollar_amount must be positive"):
            RiskParity(base_dollar_amount=0)
        
        # target_volatility must be positive
        with pytest.raises(ValueError, match="target_volatility must be positive"):
            RiskParity(base_dollar_amount=5000, target_volatility=0)
        
        # max_adjustment must be >= 1.0
        with pytest.raises(ValueError, match="max_adjustment must be >= 1.0"):
            RiskParity(base_dollar_amount=5000, max_adjustment=0.5)
    
    def test_serialization(self):
        """Test to_dict serialization."""
        sizer = RiskParity(
            base_dollar_amount=5000,
            target_volatility=0.15,
            max_adjustment=3.0
        )
        data = sizer.to_dict()
        assert data == {
            'type': 'RiskParity',
            'base_dollar_amount': 5000,
            'target_volatility': 0.15,
            'max_adjustment': 3.0
        }
    
    def test_round_trip_serialization(self):
        """Test serialization round-trip."""
        sizer1 = RiskParity(
            base_dollar_amount=7500,
            target_volatility=0.25,
            max_adjustment=1.5
        )
        data = sizer1.to_dict()
        sizer2 = RiskParity.from_dict(data)
        assert sizer2.base_dollar_amount == sizer1.base_dollar_amount
        assert sizer2.target_volatility == sizer1.target_volatility
        assert sizer2.max_adjustment == sizer1.max_adjustment


class TestCreatePositionSizer:
    """Test factory function."""
    
    def test_create_fixed_dollar_amount(self):
        """Create FixedDollarAmount from dict."""
        data = {'type': 'FixedDollarAmount', 'dollar_amount': 5000}
        sizer = create_position_sizer(data)
        assert isinstance(sizer, FixedDollarAmount)
        assert sizer.dollar_amount == 5000
    
    def test_create_percent_portfolio(self):
        """Create PercentPortfolio from dict."""
        data = {'type': 'PercentPortfolio', 'percent': 0.10}
        sizer = create_position_sizer(data)
        assert isinstance(sizer, PercentPortfolio)
        assert sizer.percent == 0.10
    
    def test_create_percent_available_cash(self):
        """Create PercentAvailableCash from dict."""
        data = {'type': 'PercentAvailableCash', 'percent': 0.50}
        sizer = create_position_sizer(data)
        assert isinstance(sizer, PercentAvailableCash)
        assert sizer.percent == 0.50
    
    def test_create_equal_weight(self):
        """Create EqualWeight from dict."""
        data = {'type': 'EqualWeight', 'default_max_positions': 15}
        sizer = create_position_sizer(data)
        assert isinstance(sizer, EqualWeight)
        assert sizer.default_max_positions == 15
    
    def test_create_fixed_shares(self):
        """Create FixedShares from dict."""
        data = {'type': 'FixedShares', 'shares': 100}
        sizer = create_position_sizer(data)
        assert isinstance(sizer, FixedShares)
        assert sizer.shares == 100
    
    def test_create_risk_parity(self):
        """Create RiskParity from dict."""
        data = {
            'type': 'RiskParity',
            'base_dollar_amount': 5000,
            'target_volatility': 0.20,
            'max_adjustment': 2.0
        }
        sizer = create_position_sizer(data)
        assert isinstance(sizer, RiskParity)
        assert sizer.base_dollar_amount == 5000
    
    def test_unknown_type_raises_error(self):
        """Raise error for unknown sizer type."""
        data = {'type': 'UnknownSizer'}
        with pytest.raises(ValueError, match="Unknown position sizer type: UnknownSizer"):
            create_position_sizer(data)