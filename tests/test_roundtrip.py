import pytest
from datetime import date
from backtester.transaction import Transaction
from backtester.roundtrip import RoundTrip


class TestRoundTripCreation:
    """Test creating RoundTrip instances."""

    def test_create_empty_roundtrip(self):
        """Create RoundTrip with defaults."""
        rt = RoundTrip()

        assert rt.id != ""
        assert len(rt.id) == 36  # UUID format
        assert rt.ticker == ""
        assert rt.transactions == []
        assert rt.exit_rule is None
        assert rt.entry_signal_metadata == {}
        assert rt._total_cost == 0.0
        assert rt._total_proceeds == 0.0

    def test_create_roundtrip_with_ticker(self):
        """Create RoundTrip with ticker specified."""
        rt = RoundTrip(ticker="AAPL")

        assert rt.ticker == "AAPL"
        assert rt.transactions == []

    def test_multiple_roundtrips_have_unique_ids(self):
        """Verify each RoundTrip gets unique UUID."""
        rt1 = RoundTrip()
        rt2 = RoundTrip()

        assert rt1.id != rt2.id


class TestAddTransaction:
    """Test adding transactions to RoundTrip."""

    def test_add_single_open_transaction(self):
        """Add opening transaction."""
        rt = RoundTrip(ticker="AAPL")

        txn = Transaction(
            roundtrip_id=rt.id,
            ticker="AAPL",
            date=date(2024, 1, 15),
            transaction_type="open",
            shares=10.0,
            price=150.0,
            net_amount=-1500.0,  # Negative = cash out
            reason="signal"
        )

        rt.add_transaction(txn)

        assert len(rt.transactions) == 1
        assert rt.transactions[0] == txn
        assert rt._total_cost == 1500.0  # abs(-1500)
        assert rt._total_proceeds == 0.0

    def test_add_entry_transaction_updates_cost(self):
        """Verify entry transaction increases total cost."""
        rt = RoundTrip(ticker="MSFT")

        txn = Transaction(
            transaction_type="add",
            shares=5.0,
            price=300.0,
            net_amount=-1505.50  # Includes costs
        )

        rt.add_transaction(txn)

        assert rt._total_cost == 1505.50

    def test_add_exit_transaction_updates_proceeds(self):
        """Verify exit transaction increases total proceeds."""
        rt = RoundTrip(ticker="GOOGL")

        # First, add entry
        entry = Transaction(
            transaction_type="open",
            shares=10.0,
            price=100.0,
            net_amount=-1000.0
        )
        rt.add_transaction(entry)

        # Now exit
        exit_txn = Transaction(
            transaction_type="close",
            shares=10.0,
            price=110.0,
            net_amount=1095.50  # Positive = cash in
        )
        rt.add_transaction(exit_txn)

        assert rt._total_proceeds == 1095.50
        assert rt._total_cost == 1000.0

    def test_add_multiple_transactions(self):
        """Add multiple transactions (DCA scenario)."""
        rt = RoundTrip(ticker="NVDA")

        txn1 = Transaction(
            transaction_type="open",
            shares=10.0,
            price=100.0,
            net_amount=-1000.0
        )
        txn2 = Transaction(
            transaction_type="add",
            shares=10.0,
            price=90.0,
            net_amount=-900.0
        )

        rt.add_transaction(txn1)
        rt.add_transaction(txn2)

        assert len(rt.transactions) == 2
        assert rt._total_cost == 1900.0


class TestTotalShares:
    """Test total_shares property."""

    def test_total_shares_single_entry(self):
        """Total shares with one entry."""
        rt = RoundTrip(ticker="AAPL")

        txn = Transaction(
            transaction_type="open",
            shares=10.5,
            price=150.0,
            net_amount=-1575.0
        )
        rt.add_transaction(txn)

        assert rt.total_shares == 10.5

    def test_total_shares_multiple_entries(self):
        """Total shares with multiple entries (DCA)."""
        rt = RoundTrip(ticker="MSFT")

        txn1 = Transaction(transaction_type="open", shares=10.0, price=100.0, net_amount=-1000.0)
        txn2 = Transaction(transaction_type="add", shares=5.0, price=90.0, net_amount=-450.0)
        txn3 = Transaction(transaction_type="add", shares=3.5, price=95.0, net_amount=-332.5)

        rt.add_transaction(txn1)
        rt.add_transaction(txn2)
        rt.add_transaction(txn3)

        assert rt.total_shares == 18.5

    def test_total_shares_ignores_exits(self):
        """Total shares should only count entries, not exits."""
        rt = RoundTrip(ticker="TSLA")

        # Entry
        entry = Transaction(transaction_type="open", shares=10.0, price=200.0, net_amount=-2000.0)
        rt.add_transaction(entry)

        # Exit
        exit_txn = Transaction(transaction_type="reduce", shares=5.0, price=220.0, net_amount=1100.0)
        rt.add_transaction(exit_txn)

        # Total shares should still be 10 (total ever entered)
        assert rt.total_shares == 10.0

    def test_total_shares_empty(self):
        """Total shares on empty RoundTrip."""
        rt = RoundTrip()
        assert rt.total_shares == 0.0


class TestRemainingShares:
    """Test remaining_shares property."""

    def test_remaining_shares_after_open(self):
        """Remaining shares after opening position."""
        rt = RoundTrip(ticker="AAPL")

        txn = Transaction(
            transaction_type="open",
            shares=10.0,
            price=150.0,
            net_amount=-1500.0
        )
        rt.add_transaction(txn)

        assert rt.remaining_shares == 10.0

    def test_remaining_shares_after_partial_exit(self):
        """Remaining shares after partial exit."""
        rt = RoundTrip(ticker="MSFT")

        # Open 10 shares
        open_txn = Transaction(transaction_type="open", shares=10.0, price=100.0, net_amount=-1000.0)
        rt.add_transaction(open_txn)

        # Reduce by 3 shares
        reduce_txn = Transaction(transaction_type="reduce", shares=3.0, price=110.0, net_amount=330.0)
        rt.add_transaction(reduce_txn)

        assert rt.remaining_shares == 7.0

    def test_remaining_shares_after_full_close(self):
        """Remaining shares after closing entire position."""
        rt = RoundTrip(ticker="GOOGL")

        # Open
        open_txn = Transaction(transaction_type="open", shares=10.0, price=100.0, net_amount=-1000.0)
        rt.add_transaction(open_txn)

        # Close all
        close_txn = Transaction(transaction_type="close", shares=10.0, price=110.0, net_amount=1100.0)
        rt.add_transaction(close_txn)

        assert rt.remaining_shares == 0.0

    def test_remaining_shares_with_dca_and_partial_exits(self):
        """Complex scenario: DCA entries + partial exits."""
        rt = RoundTrip(ticker="NVDA")

        # Entry 1: 10 shares
        rt.add_transaction(Transaction(transaction_type="open", shares=10.0, price=100.0, net_amount=-1000.0))

        # Entry 2: 5 shares (DCA)
        rt.add_transaction(Transaction(transaction_type="add", shares=5.0, price=90.0, net_amount=-450.0))

        # Total: 15 shares
        # Exit 1: 6 shares
        rt.add_transaction(Transaction(transaction_type="reduce", shares=6.0, price=105.0, net_amount=630.0))

        # Remaining: 15 - 6 = 9
        assert rt.remaining_shares == 9.0

    def test_remaining_shares_empty(self):
        """Remaining shares on empty RoundTrip."""
        rt = RoundTrip()
        assert rt.remaining_shares == 0.0


class TestIsOpen:
    """Test is_open property."""

    def test_is_open_with_shares(self):
        """Position is open if it has remaining shares."""
        rt = RoundTrip(ticker="AAPL")

        txn = Transaction(transaction_type="open", shares=10.0, price=150.0, net_amount=-1500.0)
        rt.add_transaction(txn)

        assert rt.is_open is True

    def test_is_not_open_when_closed(self):
        """Position is not open after full close."""
        rt = RoundTrip(ticker="MSFT")

        # Open
        rt.add_transaction(Transaction(transaction_type="open", shares=10.0, price=100.0, net_amount=-1000.0))

        # Close
        rt.add_transaction(Transaction(transaction_type="close", shares=10.0, price=110.0, net_amount=1100.0))

        assert rt.is_open is False

    def test_is_open_empty_roundtrip(self):
        """Empty RoundTrip is not open."""
        rt = RoundTrip()
        assert rt.is_open is False


class TestAverageEntryPrice:
    """Test average_entry_price property."""

    def test_average_entry_price_single_entry(self):
        """Average entry price with single entry."""
        rt = RoundTrip(ticker="AAPL")

        txn = Transaction(
            transaction_type="open",
            shares=10.0,
            price=150.0,
            net_amount=-1500.0  # Cost = $1500
        )
        rt.add_transaction(txn)

        # Average = 1500 / 10 = 150
        assert rt.average_entry_price == 150.0

    def test_average_entry_price_multiple_entries(self):
        """Average entry price with DCA (multiple entries at different prices)."""
        rt = RoundTrip(ticker="MSFT")

        # Entry 1: 10 shares @ $100 = $1000 cost
        rt.add_transaction(Transaction(
            transaction_type="open",
            shares=10.0,
            price=100.0,
            net_amount=-1000.0
        ))

        # Entry 2: 10 shares @ $90 = $900 cost
        rt.add_transaction(Transaction(
            transaction_type="add",
            shares=10.0,
            price=90.0,
            net_amount=-900.0
        ))

        # Total cost: $1900, Total shares: 20
        # Average: 1900 / 20 = 95
        assert rt.average_entry_price == 95.0

    def test_average_entry_price_with_transaction_costs(self):
        """Average entry price includes transaction costs."""
        rt = RoundTrip(ticker="GOOGL")

        # 10 shares @ $100 + $10 commission = $1010 total cost
        rt.add_transaction(Transaction(
            transaction_type="open",
            shares=10.0,
            price=100.0,
            net_amount=-1010.0  # Includes commission
        ))

        # Average = 1010 / 10 = 101
        assert rt.average_entry_price == 101.0

    def test_average_entry_price_ignores_exits(self):
        """Average entry price doesn't change when you exit."""
        rt = RoundTrip(ticker="NVDA")

        # Entry: 10 shares, $1000 cost
        rt.add_transaction(Transaction(transaction_type="open", shares=10.0, price=100.0, net_amount=-1000.0))

        avg_before = rt.average_entry_price

        # Exit 5 shares
        rt.add_transaction(Transaction(transaction_type="reduce", shares=5.0, price=120.0, net_amount=600.0))

        avg_after = rt.average_entry_price

        # Average entry price should remain the same
        assert avg_before == avg_after == 100.0

    def test_average_entry_price_empty(self):
        """Average entry price on empty RoundTrip returns 0."""
        rt = RoundTrip()
        assert rt.average_entry_price == 0.0


class TestRealizedPnL:
    """Test realized_pnl property."""

    def test_realized_pnl_no_exits(self):
        """Realized P&L is negative (cost) when no exits."""
        rt = RoundTrip(ticker="AAPL")

        rt.add_transaction(Transaction(transaction_type="open", shares=10.0, price=100.0, net_amount=-1000.0))

        # No proceeds yet, just cost
        assert rt.realized_pnl == -1000.0

    def test_realized_pnl_profitable_close(self):
        """Realized P&L after profitable close."""
        rt = RoundTrip(ticker="MSFT")

        # Entry: $1000 cost
        rt.add_transaction(Transaction(transaction_type="open", shares=10.0, price=100.0, net_amount=-1000.0))

        # Exit: $1200 proceeds
        rt.add_transaction(Transaction(transaction_type="close", shares=10.0, price=120.0, net_amount=1200.0))

        # P&L = 1200 - 1000 = 200
        assert rt.realized_pnl == 200.0

    def test_realized_pnl_losing_close(self):
        """Realized P&L after losing close."""
        rt = RoundTrip(ticker="TSLA")

        # Entry: $1000 cost
        rt.add_transaction(Transaction(transaction_type="open", shares=10.0, price=100.0, net_amount=-1000.0))

        # Exit: $800 proceeds (loss)
        rt.add_transaction(Transaction(transaction_type="close", shares=10.0, price=80.0, net_amount=800.0))

        # P&L = 800 - 1000 = -200
        assert rt.realized_pnl == -200.0

    def test_realized_pnl_partial_exit(self):
        """Realized P&L after partial exit."""
        rt = RoundTrip(ticker="NVDA")

        # Entry: 10 shares, $1000 cost
        rt.add_transaction(Transaction(transaction_type="open", shares=10.0, price=100.0, net_amount=-1000.0))

        # Partial exit: 5 shares, $600 proceeds
        rt.add_transaction(Transaction(transaction_type="reduce", shares=5.0, price=120.0, net_amount=600.0))

        # P&L = 600 - 1000 = -400 (still down because only exited half)
        assert rt.realized_pnl == -400.0

    def test_realized_pnl_dca_scenario(self):
        """Realized P&L with DCA entries."""
        rt = RoundTrip(ticker="AAPL")

        # Entry 1: $1000
        rt.add_transaction(Transaction(transaction_type="open", shares=10.0, price=100.0, net_amount=-1000.0))

        # Entry 2: $900 (DCA)
        rt.add_transaction(Transaction(transaction_type="add", shares=10.0, price=90.0, net_amount=-900.0))

        # Total cost: $1900

        # Close all: 20 shares @ $110 = $2200
        rt.add_transaction(Transaction(transaction_type="close", shares=20.0, price=110.0, net_amount=2200.0))

        # P&L = 2200 - 1900 = 300
        assert rt.realized_pnl == 300.0

    def test_realized_pnl_empty(self):
        """Realized P&L on empty RoundTrip."""
        rt = RoundTrip()
        assert rt.realized_pnl == 0.0


class TestUnrealizedPnL:
    """Test get_unrealized_pnl method."""

    def test_unrealized_pnl_with_open_position(self):
        """Unrealized P&L with open position."""
        rt = RoundTrip(ticker="AAPL")

        # Entry: 10 shares @ $100 (avg cost = $100)
        rt.add_transaction(Transaction(transaction_type="open", shares=10.0, price=100.0, net_amount=-1000.0))

        # Current price: $120
        unrealized = rt.get_unrealized_pnl(current_price=120.0)

        # Unrealized = (10 * 120) - (10 * 100) = 1200 - 1000 = 200
        assert unrealized == 200.0

    def test_unrealized_pnl_with_loss(self):
        """Unrealized P&L when position is down."""
        rt = RoundTrip(ticker="TSLA")

        # Entry: 10 shares @ $200
        rt.add_transaction(Transaction(transaction_type="open", shares=10.0, price=200.0, net_amount=-2000.0))

        # Current price: $180
        unrealized = rt.get_unrealized_pnl(current_price=180.0)

        # Unrealized = (10 * 180) - (10 * 200) = 1800 - 2000 = -200
        assert unrealized == -200.0

    def test_unrealized_pnl_after_partial_exit(self):
        """Unrealized P&L after partial exit."""
        rt = RoundTrip(ticker="MSFT")

        # Entry: 10 shares @ $100
        rt.add_transaction(Transaction(transaction_type="open", shares=10.0, price=100.0, net_amount=-1000.0))

        # Exit 4 shares
        rt.add_transaction(Transaction(transaction_type="reduce", shares=4.0, price=110.0, net_amount=440.0))

        # Remaining: 6 shares @ $100 avg
        # Current price: $120
        unrealized = rt.get_unrealized_pnl(current_price=120.0)

        # Unrealized = (6 * 120) - (6 * 100) = 720 - 600 = 120
        assert unrealized == 120.0

    def test_unrealized_pnl_closed_position(self):
        """Unrealized P&L is 0 when position fully closed."""
        rt = RoundTrip(ticker="GOOGL")

        # Entry
        rt.add_transaction(Transaction(transaction_type="open", shares=10.0, price=100.0, net_amount=-1000.0))

        # Full exit
        rt.add_transaction(Transaction(transaction_type="close", shares=10.0, price=110.0, net_amount=1100.0))

        # No shares left, unrealized = 0
        unrealized = rt.get_unrealized_pnl(current_price=150.0)
        assert unrealized == 0.0

    def test_unrealized_pnl_empty(self):
        """Unrealized P&L on empty RoundTrip."""
        rt = RoundTrip()
        unrealized = rt.get_unrealized_pnl(current_price=100.0)
        assert unrealized == 0.0


class TestHoldingDays:
    """Test get_holding_days method."""

    def test_holding_days_single_transaction(self):
        """Holding days from single entry."""
        rt = RoundTrip(ticker="AAPL")

        rt.add_transaction(Transaction(
            transaction_type="open",
            date=date(2024, 1, 1),
            shares=10.0,
            price=100.0,
            net_amount=-1000.0
        ))

        current = date(2024, 1, 11)
        days = rt.get_holding_days(current)

        assert days == 10

    def test_holding_days_multiple_entries(self):
        """Holding days uses first entry date."""
        rt = RoundTrip(ticker="MSFT")

        # First entry
        rt.add_transaction(Transaction(
            transaction_type="open",
            date=date(2024, 1, 1),
            shares=10.0,
            price=100.0,
            net_amount=-1000.0
        ))

        # Second entry (DCA)
        rt.add_transaction(Transaction(
            transaction_type="add",
            date=date(2024, 1, 15),
            shares=5.0,
            price=95.0,
            net_amount=-475.0
        ))

        current = date(2024, 2, 1)
        days = rt.get_holding_days(current)

        # Should use first date (Jan 1)
        assert days == 31

    def test_holding_days_same_day(self):
        """Holding days on same day as entry."""
        rt = RoundTrip(ticker="NVDA")

        entry_date = date(2024, 3, 15)
        rt.add_transaction(Transaction(
            transaction_type="open",
            date=entry_date,
            shares=10.0,
            price=100.0,
            net_amount=-1000.0
        ))

        days = rt.get_holding_days(entry_date)
        assert days == 0

    def test_holding_days_empty(self):
        """Holding days on empty RoundTrip."""
        rt = RoundTrip()
        days = rt.get_holding_days(date(2024, 1, 1))
        assert days == 0


class TestToDict:
    """Test to_dict serialization."""

    def test_to_dict_empty(self):
        """Serialize empty RoundTrip."""
        rt = RoundTrip(ticker="AAPL")
        data = rt.to_dict()

        assert data["id"] == rt.id
        assert data["ticker"] == "AAPL"
        assert data["is_open"] is False
        assert data["remaining_shares"] == 0.0
        assert data["average_entry_price"] == 0.0
        assert data["realized_pnl"] == 0.0
        assert data["total_cost"] == 0.0
        assert data["total_proceeds"] == 0.0
        assert data["transactions"] == []

    def test_to_dict_with_transactions(self):
        """Serialize RoundTrip with transactions."""
        rt = RoundTrip(ticker="MSFT")

        txn = Transaction(
            id="txn-1",
            roundtrip_id=rt.id,
            ticker="MSFT",
            date=date(2024, 1, 15),
            transaction_type="open",
            shares=10.0,
            price=100.0,
            net_amount=-1000.0,
            reason="signal"
        )
        rt.add_transaction(txn)

        data = rt.to_dict()

        assert data["ticker"] == "MSFT"
        assert data["is_open"] is True
        assert data["remaining_shares"] == 10.0
        assert data["average_entry_price"] == 100.0
        assert data["realized_pnl"] == -1000.0
        assert len(data["transactions"]) == 1
        assert data["transactions"][0]["id"] == "txn-1"

    def test_to_dict_complete_roundtrip(self):
        """Serialize complete roundtrip (opened and closed)."""
        rt = RoundTrip(ticker="GOOGL")

        # Entry
        rt.add_transaction(Transaction(
            transaction_type="open",
            date=date(2024, 1, 1),
            shares=10.0,
            price=100.0,
            net_amount=-1000.0
        ))

        # Exit
        rt.add_transaction(Transaction(
            transaction_type="close",
            date=date(2024, 1, 15),
            shares=10.0,
            price=120.0,
            net_amount=1200.0
        ))

        data = rt.to_dict()

        assert data["is_open"] is False
        assert data["remaining_shares"] == 0.0
        assert data["realized_pnl"] == 200.0
        assert len(data["transactions"]) == 2
