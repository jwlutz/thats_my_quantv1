import pytest
from datetime import date
from backtester.portfolio import Portfolio
from backtester.transaction import Transaction
from backtester.roundtrip import RoundTrip
from backtester.transactioncost import TransactionCost


class TestPortfolioInit:
    """Test Portfolio initialization."""

    def test_init_basic(self):
        """Initialize portfolio with basic parameters."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.001)
        portfolio = Portfolio(
            starting_capital=10000.0,
            max_positions=5,
            transaction_cost=tc,
            fractional_shares=True
        )

        assert portfolio.starting_capital == 10000.0
        assert portfolio.cash == 10000.0
        assert portfolio.max_positions == 5
        assert portfolio.transaction_cost == tc
        assert portfolio.fractional_shares is True
        assert portfolio.open_roundtrips == {}
        assert portfolio.closed_roundtrips == []
        assert portfolio.transaction_log == []
        assert portfolio.equity_history == []

    def test_init_fractional_shares_false(self):
        """Initialize with fractional_shares disabled."""
        tc = TransactionCost()
        portfolio = Portfolio(
            starting_capital=5000.0,
            max_positions=3,
            transaction_cost=tc,
            fractional_shares=False
        )

        assert portfolio.fractional_shares is False


class TestCanOpenPosition:
    """Test can_open_position method."""

    def test_can_open_when_empty(self):
        """Can open position when portfolio is empty."""
        tc = TransactionCost()
        portfolio = Portfolio(10000.0, 5, tc)

        assert portfolio.can_open_position() is True

    def test_can_open_when_not_full(self):
        """Can open position when not at max."""
        tc = TransactionCost()
        portfolio = Portfolio(10000.0, 3, tc)

        # Add 2 positions manually
        portfolio.open_roundtrips["id1"] = RoundTrip(ticker="AAPL")
        portfolio.open_roundtrips["id2"] = RoundTrip(ticker="MSFT")

        assert portfolio.can_open_position() is True

    def test_cannot_open_when_full(self):
        """Cannot open when at max positions."""
        tc = TransactionCost()
        portfolio = Portfolio(10000.0, 2, tc)

        # Fill to max
        portfolio.open_roundtrips["id1"] = RoundTrip(ticker="AAPL")
        portfolio.open_roundtrips["id2"] = RoundTrip(ticker="MSFT")

        assert portfolio.can_open_position() is False


class TestRoundShares:
    """Test _round_shares method."""

    def test_round_shares_fractional_enabled(self):
        """Don't round when fractional_shares=True."""
        tc = TransactionCost()
        portfolio = Portfolio(10000.0, 5, tc, fractional_shares=True)

        assert portfolio._round_shares(10.7) == 10.7
        assert portfolio._round_shares(0.5) == 0.5

    def test_round_shares_fractional_disabled(self):
        """Round down when fractional_shares=False."""
        tc = TransactionCost()
        portfolio = Portfolio(10000.0, 5, tc, fractional_shares=False)

        assert portfolio._round_shares(10.7) == 10.0
        assert portfolio._round_shares(0.5) == 0.0
        assert portfolio._round_shares(99.99) == 99.0


class TestOpenPosition:
    """Test open_position method."""

    def test_open_position_success(self):
        """Successfully open a position."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.001)
        portfolio = Portfolio(10000.0, 5, tc)

        # Mock exit rule
        exit_rule = None

        rt = portfolio.open_position(
            ticker="AAPL",
            date=date(2024, 1, 15),
            price=150.0,
            shares=10.0,
            exit_rule=exit_rule
        )

        assert rt is not None
        assert rt.ticker == "AAPL"
        assert rt.remaining_shares == 10.0
        assert len(portfolio.open_roundtrips) == 1
        assert len(portfolio.transaction_log) == 1

        # Check cash deducted (10 * 150 * 1.001 = 1501.5)
        assert portfolio.cash == pytest.approx(10000.0 - 1501.5, rel=1e-5)

    def test_open_position_insufficient_cash(self):
        """Cannot open position with insufficient cash."""
        tc = TransactionCost()
        portfolio = Portfolio(100.0, 5, tc)  # Only $100

        rt = portfolio.open_position(
            ticker="AAPL",
            date=date(2024, 1, 15),
            price=150.0,
            shares=10.0,  # Needs $1500+
            exit_rule=None
        )

        assert rt is None
        assert portfolio.cash == 100.0
        assert len(portfolio.open_roundtrips) == 0

    def test_open_position_no_room(self):
        """Cannot open when at max positions."""
        tc = TransactionCost()
        portfolio = Portfolio(100000.0, 2, tc)

        # Fill to max
        portfolio.open_position("AAPL", date(2024, 1, 1), 100.0, 10.0, None)
        portfolio.open_position("MSFT", date(2024, 1, 1), 200.0, 5.0, None)

        # Try to open third
        rt = portfolio.open_position("GOOGL", date(2024, 1, 1), 150.0, 10.0, None)

        assert rt is None

    def test_open_position_zero_shares(self):
        """Cannot open with zero shares."""
        tc = TransactionCost()
        portfolio = Portfolio(10000.0, 5, tc)

        rt = portfolio.open_position(
            ticker="AAPL",
            date=date(2024, 1, 15),
            price=150.0,
            shares=0.0,
            exit_rule=None
        )

        assert rt is None

    def test_open_position_rounds_shares(self):
        """Rounds shares when fractional disabled."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.0)
        portfolio = Portfolio(10000.0, 5, tc, fractional_shares=False)

        rt = portfolio.open_position(
            ticker="AAPL",
            date=date(2024, 1, 15),
            price=100.0,
            shares=10.7,  # Should round to 10
            exit_rule=None
        )

        assert rt is not None
        assert rt.remaining_shares == 10.0

    def test_open_position_with_metadata(self):
        """Open position with signal metadata."""
        tc = TransactionCost()
        portfolio = Portfolio(10000.0, 5, tc)

        metadata = {"signal_type": "earnings_beat", "surprise": 0.15}

        rt = portfolio.open_position(
            ticker="AAPL",
            date=date(2024, 1, 15),
            price=150.0,
            shares=10.0,
            exit_rule=None,
            signal_metadata=metadata
        )

        assert rt.entry_signal_metadata == metadata


class TestAddToPosition:
    """Test add_to_position method (DCA)."""

    def test_add_to_position_success(self):
        """Successfully add to existing position."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.001)
        portfolio = Portfolio(10000.0, 5, tc)

        # Open position
        rt = portfolio.open_position("AAPL", date(2024, 1, 1), 100.0, 10.0, None)
        initial_cash = portfolio.cash

        # Add to it
        success = portfolio.add_to_position(
            roundtrip_id=rt.id,
            date=date(2024, 1, 15),
            price=95.0,
            shares=5.0
        )

        assert success is True
        assert rt.total_shares == 15.0
        assert rt.remaining_shares == 15.0

        # Check cash (5 * 95 * 1.001 = 475.475)
        assert portfolio.cash == pytest.approx(initial_cash - 475.475, rel=1e-5)

    def test_add_to_position_insufficient_cash(self):
        """Cannot add when insufficient cash."""
        tc = TransactionCost()
        portfolio = Portfolio(2000.0, 5, tc)

        # Open position (uses most of cash)
        rt = portfolio.open_position("AAPL", date(2024, 1, 1), 100.0, 10.0, None)

        # Try to add more (not enough cash left)
        success = portfolio.add_to_position(
            roundtrip_id=rt.id,
            date=date(2024, 1, 15),
            price=100.0,
            shares=50.0
        )

        assert success is False
        assert rt.remaining_shares == 10.0

    def test_add_to_position_roundtrip_not_found(self):
        """Raises error when roundtrip doesn't exist."""
        tc = TransactionCost()
        portfolio = Portfolio(10000.0, 5, tc)

        with pytest.raises(ValueError, match="RoundTrip .* not found"):
            portfolio.add_to_position(
                roundtrip_id="fake-id",
                date=date(2024, 1, 1),
                price=100.0,
                shares=10.0
            )

    def test_add_to_position_zero_shares(self):
        """Cannot add zero shares."""
        tc = TransactionCost()
        portfolio = Portfolio(10000.0, 5, tc)

        rt = portfolio.open_position("AAPL", date(2024, 1, 1), 100.0, 10.0, None)

        success = portfolio.add_to_position(
            roundtrip_id=rt.id,
            date=date(2024, 1, 15),
            price=100.0,
            shares=0.0
        )

        assert success is False


class TestReducePosition:
    """Test reduce_position method (partial exit)."""

    def test_reduce_position_success(self):
        """Successfully reduce position."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.001)
        portfolio = Portfolio(10000.0, 5, tc)

        # Open position: 10 shares @ $100
        rt = portfolio.open_position("AAPL", date(2024, 1, 1), 100.0, 10.0, None)
        cash_after_open = portfolio.cash

        # Reduce: sell 4 shares @ $110
        pnl = portfolio.reduce_position(
            roundtrip_id=rt.id,
            date=date(2024, 1, 15),
            price=110.0,
            shares=4.0,
            reason="partial_exit"
        )

        # Check shares
        assert rt.remaining_shares == 6.0

        # Check cash (4 * 110 * 0.999 = 439.56)
        assert portfolio.cash == pytest.approx(cash_after_open + 439.56, rel=1e-5)

        # Check P&L
        # Entry cost: 10 * 100 * 1.001 = 1001, avg entry price = 100.1
        # Cost of 4 shares: 4 * 100.1 = 400.4
        # Proceeds: 439.56
        # P&L: 39.16
        assert pnl == pytest.approx(39.16, rel=1e-2)

        # Position should still be open
        assert rt.id in portfolio.open_roundtrips

    def test_reduce_position_full_close(self):
        """Reduce all shares closes position."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.0)
        portfolio = Portfolio(10000.0, 5, tc)

        # Open
        rt = portfolio.open_position("AAPL", date(2024, 1, 1), 100.0, 10.0, None)
        rt_id = rt.id

        # Reduce all
        pnl = portfolio.reduce_position(
            roundtrip_id=rt.id,
            date=date(2024, 1, 15),
            price=110.0,
            shares=10.0,
            reason="full_exit"
        )

        # Position should be closed
        assert rt.remaining_shares == 0.0
        assert rt_id not in portfolio.open_roundtrips
        assert rt in portfolio.closed_roundtrips

    def test_reduce_position_too_many_shares(self):
        """Cannot reduce more shares than available."""
        tc = TransactionCost()
        portfolio = Portfolio(10000.0, 5, tc)

        rt = portfolio.open_position("AAPL", date(2024, 1, 1), 100.0, 10.0, None)

        with pytest.raises(ValueError, match="Cannot exit .* shares"):
            portfolio.reduce_position(
                roundtrip_id=rt.id,
                date=date(2024, 1, 15),
                price=110.0,
                shares=20.0,  # More than 10!
                reason="invalid"
            )

    def test_reduce_position_roundtrip_not_found(self):
        """Raises error when roundtrip doesn't exist."""
        tc = TransactionCost()
        portfolio = Portfolio(10000.0, 5, tc)

        with pytest.raises(ValueError, match="RoundTrip .* not found"):
            portfolio.reduce_position(
                roundtrip_id="fake-id",
                date=date(2024, 1, 1),
                price=100.0,
                shares=10.0,
                reason="test"
            )


class TestClosePosition:
    """Test close_position method (full exit)."""

    def test_close_position_success(self):
        """Successfully close entire position."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.001)
        portfolio = Portfolio(10000.0, 5, tc)

        # Open: 10 shares @ $100
        rt = portfolio.open_position("AAPL", date(2024, 1, 1), 100.0, 10.0, None)
        rt_id = rt.id
        cash_after_open = portfolio.cash

        # Close @ $120
        pnl = portfolio.close_position(
            roundtrip_id=rt.id,
            date=date(2024, 1, 30),
            price=120.0,
            reason="time_exit"
        )

        # Check closed
        assert rt.remaining_shares == 0.0
        assert rt_id not in portfolio.open_roundtrips
        assert rt in portfolio.closed_roundtrips

        # Check cash (10 * 120 * 0.999 = 1198.8)
        assert portfolio.cash == pytest.approx(cash_after_open + 1198.8, rel=1e-5)

        # Check P&L
        # Entry cost: 10 * 100 * 1.001 = 1001, avg entry = 100.1
        # Cost: 10 * 100.1 = 1001
        # Proceeds: 1198.8
        # P&L: 197.8
        assert pnl == pytest.approx(197.8, rel=1e-2)

    def test_close_position_after_dca(self):
        """Close position after multiple adds."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.0)
        portfolio = Portfolio(10000.0, 5, tc)

        # Open: 10 @ $100
        rt = portfolio.open_position("AAPL", date(2024, 1, 1), 100.0, 10.0, None)

        # Add: 5 @ $90
        portfolio.add_to_position(rt.id, date(2024, 1, 15), 90.0, 5.0)

        # Close all @ $110
        pnl = portfolio.close_position(rt.id, date(2024, 1, 30), 110.0, "exit")

        # Avg entry: (10*100 + 5*90) / 15 = 1450/15 = 96.67
        # Proceeds: 15 * 110 = 1650
        # Cost: 1450
        # P&L: 200
        assert pnl == pytest.approx(200.0, rel=1e-5)


class TestGetTotalValue:
    """Test get_total_value method."""

    def test_total_value_cash_only(self):
        """Total value with no positions."""
        tc = TransactionCost()
        portfolio = Portfolio(10000.0, 5, tc)

        value = portfolio.get_total_value(
            date=date(2024, 1, 1),
            current_prices={}
        )

        assert value == 10000.0

    def test_total_value_with_positions(self):
        """Total value with open positions."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.0)
        portfolio = Portfolio(10000.0, 5, tc)

        # Open 2 positions
        portfolio.open_position("AAPL", date(2024, 1, 1), 100.0, 10.0, None)
        portfolio.open_position("MSFT", date(2024, 1, 1), 200.0, 5.0, None)

        # Cash: 10000 - 1000 - 1000 = 8000
        # Positions: (10 * 120) + (5 * 250) = 1200 + 1250 = 2450
        # Total: 10450

        value = portfolio.get_total_value(
            date=date(2024, 1, 15),
            current_prices={"AAPL": 120.0, "MSFT": 250.0}
        )

        assert value == 10450.0

    def test_total_value_missing_price(self):
        """Total value when price is missing (delisted)."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.0)
        portfolio = Portfolio(10000.0, 5, tc)

        # Open position
        portfolio.open_position("AAPL", date(2024, 1, 1), 100.0, 10.0, None)

        # No price for AAPL - value should be just cash
        value = portfolio.get_total_value(
            date=date(2024, 1, 15),
            current_prices={}  # No prices
        )

        assert value == 9000.0  # Just cash (10000 - 1000)

    def test_total_value_after_partial_exit(self):
        """Total value after reducing position."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.0)
        portfolio = Portfolio(10000.0, 5, tc)

        # Open: 10 @ $100
        rt = portfolio.open_position("AAPL", date(2024, 1, 1), 100.0, 10.0, None)

        # Reduce: sell 4 @ $110
        portfolio.reduce_position(rt.id, date(2024, 1, 15), 110.0, 4.0, "exit")

        # Cash: 10000 - 1000 + 440 = 9440
        # Position: 6 * 115 = 690
        # Total: 10130

        value = portfolio.get_total_value(
            date=date(2024, 1, 20),
            current_prices={"AAPL": 115.0}
        )

        assert value == 10130.0


class TestRecordEquity:
    """Test record_equity method."""

    def test_record_equity(self):
        """Record equity history."""
        tc = TransactionCost()
        portfolio = Portfolio(10000.0, 5, tc)

        portfolio.record_equity(date(2024, 1, 1), 10000.0)
        portfolio.record_equity(date(2024, 1, 2), 10500.0)
        portfolio.record_equity(date(2024, 1, 3), 10200.0)

        assert len(portfolio.equity_history) == 3
        assert portfolio.equity_history[0] == {'date': date(2024, 1, 1), 'value': 10000.0}
        assert portfolio.equity_history[1] == {'date': date(2024, 1, 2), 'value': 10500.0}
        assert portfolio.equity_history[2] == {'date': date(2024, 1, 3), 'value': 10200.0}


class TestTransactionLog:
    """Test transaction logging."""

    def test_transaction_log_captures_all(self):
        """Transaction log captures all transactions."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.0)
        portfolio = Portfolio(10000.0, 5, tc)

        # Open
        rt = portfolio.open_position("AAPL", date(2024, 1, 1), 100.0, 10.0, None)

        # Add
        portfolio.add_to_position(rt.id, date(2024, 1, 15), 95.0, 5.0)

        # Reduce
        portfolio.reduce_position(rt.id, date(2024, 1, 20), 110.0, 3.0, "partial")

        # Close
        portfolio.close_position(rt.id, date(2024, 1, 30), 115.0, "exit")

        assert len(portfolio.transaction_log) == 4

        # Check transaction types
        assert portfolio.transaction_log[0].transaction_type == "open"
        assert portfolio.transaction_log[1].transaction_type == "add"
        assert portfolio.transaction_log[2].transaction_type == "reduce"
        assert portfolio.transaction_log[3].transaction_type == "reduce"  # close_position uses reduce

    def test_get_transaction_log_df(self):
        """Export transaction log as DataFrame."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.0)
        portfolio = Portfolio(10000.0, 5, tc)

        # Open position
        portfolio.open_position("AAPL", date(2024, 1, 1), 100.0, 10.0, None)

        # Get DataFrame
        df = portfolio.get_transaction_log_df()

        assert len(df) == 1
        assert "ticker" in df.columns
        assert "transaction_type" in df.columns
        assert df.iloc[0]["ticker"] == "AAPL"
        assert df.iloc[0]["transaction_type"] == "open"


class TestMultiplePositions:
    """Test managing multiple positions."""

    def test_multiple_positions_same_ticker(self):
        """Can hold multiple roundtrips for same ticker."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.0)
        portfolio = Portfolio(100000.0, 5, tc)

        # Open 2 AAPL positions
        rt1 = portfolio.open_position("AAPL", date(2024, 1, 1), 100.0, 10.0, None)
        rt2 = portfolio.open_position("AAPL", date(2024, 1, 15), 110.0, 5.0, None)

        assert len(portfolio.open_roundtrips) == 2
        assert rt1.id != rt2.id
        assert rt1.ticker == "AAPL"
        assert rt2.ticker == "AAPL"

    def test_multiple_positions_different_tickers(self):
        """Hold multiple positions in different tickers."""
        tc = TransactionCost(commission=0.0, slippage_pct=0.0)
        portfolio = Portfolio(100000.0, 5, tc)

        rt1 = portfolio.open_position("AAPL", date(2024, 1, 1), 100.0, 10.0, None)
        rt2 = portfolio.open_position("MSFT", date(2024, 1, 1), 200.0, 5.0, None)
        rt3 = portfolio.open_position("GOOGL", date(2024, 1, 1), 150.0, 7.0, None)

        assert len(portfolio.open_roundtrips) == 3

        # Get total value
        value = portfolio.get_total_value(
            date=date(2024, 1, 15),
            current_prices={"AAPL": 110.0, "MSFT": 210.0, "GOOGL": 160.0}
        )

        # Cash: 100000 - 1000 - 1000 - 1050 = 96950
        # Positions: (10*110) + (5*210) + (7*160) = 1100 + 1050 + 1120 = 3270
        # Total: 100220
        assert value == 100220.0


class TestIntegration:
    """Integration tests combining multiple operations."""

    def test_full_lifecycle(self):
        """Test complete lifecycle: open, add, reduce, close."""
        tc = TransactionCost(commission=1.0, slippage_pct=0.001)
        portfolio = Portfolio(10000.0, 5, tc)

        # Open
        rt = portfolio.open_position("AAPL", date(2024, 1, 1), 100.0, 10.0, None)
        assert rt is not None

        # Add (DCA)
        success = portfolio.add_to_position(rt.id, date(2024, 1, 15), 95.0, 5.0)
        assert success is True
        assert rt.total_shares == 15.0

        # Partial exit
        pnl1 = portfolio.reduce_position(rt.id, date(2024, 1, 20), 110.0, 5.0, "partial")
        assert rt.remaining_shares == 10.0

        # Close remaining
        pnl2 = portfolio.close_position(rt.id, date(2024, 1, 30), 115.0, "exit")

        # Verify closed
        assert rt.id not in portfolio.open_roundtrips
        assert rt in portfolio.closed_roundtrips
        assert len(portfolio.transaction_log) == 4
