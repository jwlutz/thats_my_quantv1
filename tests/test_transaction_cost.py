import pytest
from backtester.transactioncost import TransactionCost


class TestTransactionCostInit:
    """Test TransactionCost initialization."""

    def test_default_initialization(self):
        """Initialize with default values."""
        tc = TransactionCost()

        assert tc.commission == 0.0
        assert tc.slippage_pct == 0.001

    def test_custom_commission(self):
        """Initialize with custom commission."""
        tc = TransactionCost(commission=5.0)

        assert tc.commission == 5.0
        assert tc.slippage_pct == 0.001

    def test_custom_slippage(self):
        """Initialize with custom slippage."""
        tc = TransactionCost(slippage_pct=0.002)

        assert tc.commission == 0.0
        assert tc.slippage_pct == 0.002

    def test_custom_both(self):
        """Initialize with custom commission and slippage."""
        tc = TransactionCost(commission=10.0, slippage_pct=0.005)

        assert tc.commission == 10.0
        assert tc.slippage_pct == 0.005

    def test_zero_costs(self):
        """Initialize with zero commission and slippage."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.0)

        assert tc.commission == 0.0
        assert tc.slippage_pct == 0.0


class TestCalculateEntryCost:
    """Test calculate_entry_cost method."""

    def test_entry_cost_basic(self):
        """Basic entry cost calculation."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.001)

        # 10 shares @ $100
        # Base: 10 * 100 = 1000
        # Slippage: 1000 * 0.001 = 1
        # Total: 1000 + 1 + 0 = 1001
        cost = tc.calculate_entry_cost(shares=10.0, price=100.0)

        assert cost == 1001.0

    def test_entry_cost_with_commission(self):
        """Entry cost with commission."""
        tc = TransactionCost(commission=5.0, slippage_pct=0.001)

        # 10 shares @ $100
        # Base: 1000
        # Slippage: 1
        # Commission: 5
        # Total: 1006
        cost = tc.calculate_entry_cost(shares=10.0, price=100.0)

        assert cost == 1006.0

    def test_entry_cost_fractional_shares(self):
        """Entry cost with fractional shares."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.001)

        # 13.7 shares @ $150.50
        # Base: 13.7 * 150.50 = 2061.85
        # Slippage: 2061.85 * 0.001 = 2.06185
        # Total: 2063.91185
        cost = tc.calculate_entry_cost(shares=13.7, price=150.50)

        assert cost == pytest.approx(2063.91185, rel=1e-5)

    def test_entry_cost_zero_slippage(self):
        """Entry cost with zero slippage."""
        tc = TransactionCost(commission=1.0, slippage_pct=0.0)

        # 10 shares @ $100
        # Base: 1000
        # Slippage: 0
        # Commission: 1
        # Total: 1001
        cost = tc.calculate_entry_cost(shares=10.0, price=100.0)

        assert cost == 1001.0

    def test_entry_cost_zero_commission(self):
        """Entry cost with zero commission (Robinhood-style)."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.002)

        # 10 shares @ $100
        # Base: 1000
        # Slippage: 1000 * 0.002 = 2
        # Commission: 0
        # Total: 1002
        cost = tc.calculate_entry_cost(shares=10.0, price=100.0)

        assert cost == 1002.0

    def test_entry_cost_high_slippage(self):
        """Entry cost with higher slippage."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.01)  # 1%

        # 100 shares @ $50
        # Base: 5000
        # Slippage: 5000 * 0.01 = 50
        # Total: 5050
        cost = tc.calculate_entry_cost(shares=100.0, price=50.0)

        assert cost == 5050.0

    def test_entry_cost_small_trade(self):
        """Entry cost for small trade."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.001)

        # 0.5 shares @ $200
        # Base: 100
        # Slippage: 0.1
        # Total: 100.1
        cost = tc.calculate_entry_cost(shares=0.5, price=200.0)

        assert cost == 100.1


class TestCalculateExitValue:
    """Test calculate_exit_value method."""

    def test_exit_value_basic(self):
        """Basic exit value calculation."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.001)

        # 10 shares @ $110
        # Gross: 10 * 110 = 1100
        # Slippage: 1100 * 0.001 = 1.1
        # Net: 1100 - 1.1 - 0 = 1098.9
        proceeds = tc.calculate_exit_value(shares=10.0, price=110.0)

        assert proceeds == 1098.9

    def test_exit_value_with_commission(self):
        """Exit value with commission."""
        tc = TransactionCost(commission=5.0, slippage_pct=0.001)

        # 10 shares @ $110
        # Gross: 1100
        # Slippage: 1.1
        # Commission: 5
        # Net: 1100 - 1.1 - 5 = 1093.9
        proceeds = tc.calculate_exit_value(shares=10.0, price=110.0)

        assert proceeds == 1093.9

    def test_exit_value_fractional_shares(self):
        """Exit value with fractional shares."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.001)

        # 13.7 shares @ $165.25
        # Gross: 13.7 * 165.25 = 2263.925
        # Slippage: 2263.925 * 0.001 = 2.263925
        # Net: 2261.661075
        proceeds = tc.calculate_exit_value(shares=13.7, price=165.25)

        assert proceeds == pytest.approx(2261.661075, rel=1e-5)

    def test_exit_value_zero_slippage(self):
        """Exit value with zero slippage."""
        tc = TransactionCost(commission=1.0, slippage_pct=0.0)

        # 10 shares @ $110
        # Gross: 1100
        # Slippage: 0
        # Commission: 1
        # Net: 1099
        proceeds = tc.calculate_exit_value(shares=10.0, price=110.0)

        assert proceeds == 1099.0

    def test_exit_value_zero_commission(self):
        """Exit value with zero commission."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.002)

        # 10 shares @ $110
        # Gross: 1100
        # Slippage: 1100 * 0.002 = 2.2
        # Net: 1097.8
        proceeds = tc.calculate_exit_value(shares=10.0, price=110.0)

        assert proceeds == 1097.8

    def test_exit_value_high_slippage(self):
        """Exit value with higher slippage."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.01)  # 1%

        # 100 shares @ $55
        # Gross: 5500
        # Slippage: 5500 * 0.01 = 55
        # Net: 5445
        proceeds = tc.calculate_exit_value(shares=100.0, price=55.0)

        assert proceeds == 5445.0

    def test_exit_value_small_trade(self):
        """Exit value for small trade."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.001)

        # 0.5 shares @ $220
        # Gross: 110
        # Slippage: 0.11
        # Net: 109.89
        proceeds = tc.calculate_exit_value(shares=0.5, price=220.0)

        assert proceeds == 109.89


class TestRoundTripCost:
    """Test round trip costs (entry + exit)."""

    def test_round_trip_profitable(self):
        """Round trip with profit."""
        tc = TransactionCost(commission=1.0, slippage_pct=0.001)

        # Entry: 10 shares @ $100
        entry_cost = tc.calculate_entry_cost(shares=10.0, price=100.0)
        # Entry: (10 * 100 * 1.001) + 1 = 1001 + 1 = 1002

        # Exit: 10 shares @ $110
        exit_proceeds = tc.calculate_exit_value(shares=10.0, price=110.0)
        # Exit: (10 * 110 * 0.999) - 1 = 1098.9 - 1 = 1097.9

        # P&L: 1097.9 - 1002 = 95.9
        pnl = exit_proceeds - entry_cost

        assert entry_cost == 1002.0
        assert exit_proceeds == 1097.9
        assert pnl == pytest.approx(95.9, rel=1e-5)

    def test_round_trip_loss(self):
        """Round trip with loss."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.001)

        # Entry: 10 shares @ $100
        entry_cost = tc.calculate_entry_cost(shares=10.0, price=100.0)
        # 1001

        # Exit: 10 shares @ $95
        exit_proceeds = tc.calculate_exit_value(shares=10.0, price=95.0)
        # (10 * 95 * 0.999) = 949.05

        # P&L: 949.05 - 1001 = -51.95
        pnl = exit_proceeds - entry_cost

        assert entry_cost == 1001.0
        assert exit_proceeds == 949.05
        assert pnl == pytest.approx(-51.95, rel=1e-5)

    def test_round_trip_zero_costs(self):
        """Round trip with no commission or slippage."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.0)

        # Entry: 10 shares @ $100
        entry_cost = tc.calculate_entry_cost(shares=10.0, price=100.0)
        # Exactly 1000

        # Exit: 10 shares @ $110
        exit_proceeds = tc.calculate_exit_value(shares=10.0, price=110.0)
        # Exactly 1100

        # P&L: 100
        pnl = exit_proceeds - entry_cost

        assert entry_cost == 1000.0
        assert exit_proceeds == 1100.0
        assert pnl == 100.0

    def test_round_trip_total_cost(self):
        """Calculate total round trip cost (2x slippage + 2x commission)."""
        tc = TransactionCost(commission=5.0, slippage_pct=0.001)

        # Entry and exit at same price to isolate costs
        entry_cost = tc.calculate_entry_cost(shares=100.0, price=100.0)
        exit_proceeds = tc.calculate_exit_value(shares=100.0, price=100.0)

        # Entry: (100 * 100 * 1.001) + 5 = 10010 + 5 = 10015
        # Exit: (100 * 100 * 0.999) - 5 = 9990 - 5 = 9985
        # Total cost: 10015 - 9985 = 30

        total_cost = entry_cost - exit_proceeds

        assert entry_cost == 10015.0
        assert exit_proceeds == 9985.0
        assert total_cost == 30.0


class TestErrorHandling:
    """Test error handling for invalid inputs."""

    def test_entry_negative_shares(self):
        """Entry cost with negative shares raises ValueError."""
        tc = TransactionCost()

        with pytest.raises(ValueError, match="Shares must be positive"):
            tc.calculate_entry_cost(shares=-10.0, price=100.0)

    def test_entry_zero_shares(self):
        """Entry cost with zero shares raises ValueError."""
        tc = TransactionCost()

        with pytest.raises(ValueError, match="Shares must be positive"):
            tc.calculate_entry_cost(shares=0.0, price=100.0)

    def test_entry_negative_price(self):
        """Entry cost with negative price raises ValueError."""
        tc = TransactionCost()

        with pytest.raises(ValueError, match="Price must be positive"):
            tc.calculate_entry_cost(shares=10.0, price=-100.0)

    def test_entry_zero_price(self):
        """Entry cost with zero price raises ValueError."""
        tc = TransactionCost()

        with pytest.raises(ValueError, match="Price must be positive"):
            tc.calculate_entry_cost(shares=10.0, price=0.0)

    def test_exit_negative_shares(self):
        """Exit value with negative shares raises ValueError."""
        tc = TransactionCost()

        with pytest.raises(ValueError, match="Shares must be positive"):
            tc.calculate_exit_value(shares=-10.0, price=100.0)

    def test_exit_zero_shares(self):
        """Exit value with zero shares raises ValueError."""
        tc = TransactionCost()

        with pytest.raises(ValueError, match="Shares must be positive"):
            tc.calculate_exit_value(shares=0.0, price=100.0)

    def test_exit_negative_price(self):
        """Exit value with negative price raises ValueError."""
        tc = TransactionCost()

        with pytest.raises(ValueError, match="Price must be positive"):
            tc.calculate_exit_value(shares=10.0, price=-100.0)

    def test_exit_zero_price(self):
        """Exit value with zero price raises ValueError."""
        tc = TransactionCost()

        with pytest.raises(ValueError, match="Price must be positive"):
            tc.calculate_exit_value(shares=10.0, price=0.0)


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_very_small_shares(self):
        """Test with very small fractional shares."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.001)

        # 0.001 shares @ $1000
        cost = tc.calculate_entry_cost(shares=0.001, price=1000.0)

        # Base: 1.0
        # Slippage: 0.001
        # Total: 1.001
        assert cost == pytest.approx(1.001, rel=1e-5)

    def test_very_high_price(self):
        """Test with very high price per share."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.001)

        # 1 share @ $10,000
        cost = tc.calculate_entry_cost(shares=1.0, price=10000.0)

        # Base: 10000
        # Slippage: 10
        # Total: 10010
        assert cost == 10010.0

    def test_large_trade(self):
        """Test with large number of shares."""
        tc = TransactionCost(commission=10.0, slippage_pct=0.001)

        # 10,000 shares @ $50
        cost = tc.calculate_entry_cost(shares=10000.0, price=50.0)

        # Base: 500,000
        # Slippage: 500
        # Commission: 10
        # Total: 500,510
        assert cost == 500510.0

    def test_commission_larger_than_trade(self):
        """Test when commission is larger than trade value."""
        tc = TransactionCost(commission=100.0, slippage_pct=0.0)

        # 1 share @ $10
        cost = tc.calculate_entry_cost(shares=1.0, price=10.0)

        # Base: 10
        # Commission: 100
        # Total: 110
        assert cost == 110.0

    def test_exit_proceeds_can_be_negative(self):
        """Exit proceeds can theoretically be negative with high commission."""
        tc = TransactionCost(commission=200.0, slippage_pct=0.0)

        # 1 share @ $100
        proceeds = tc.calculate_exit_value(shares=1.0, price=100.0)

        # Gross: 100
        # Commission: 200
        # Net: -100
        assert proceeds == -100.0
