import pytest
from datetime import date
from dataclasses import FrozenInstanceError
from backtester.transaction import Transaction


class TestTransactionCreation:
    """Test creating transactions with various field combinations."""

    def test_create_transaction_with_all_fields(self):
        """Create a transaction with all fields populated."""
        txn = Transaction(
            id="test-uuid-123",
            roundtrip_id="rt-456",
            ticker="AAPL",
            date=date(2024, 1, 15),
            transaction_type="open",
            shares=10.5,
            price=150.25,
            net_amount=-1577.63,
            reason="signal"
        )

        assert txn.id == "test-uuid-123"
        assert txn.roundtrip_id == "rt-456"
        assert txn.ticker == "AAPL"
        assert txn.date == date(2024, 1, 15)
        assert txn.transaction_type == "open"
        assert txn.shares == 10.5
        assert txn.price == 150.25
        assert txn.net_amount == -1577.63
        assert txn.reason == "signal"

    def test_create_transaction_with_defaults(self):
        """Create a transaction using default values."""
        txn = Transaction()

        # ID should be auto-generated
        assert txn.id != ""
        assert len(txn.id) > 0

        # Other fields should have defaults
        assert txn.roundtrip_id == ""
        assert txn.ticker == ""
        assert txn.date is None
        assert txn.transaction_type == ""
        assert txn.shares == 0.0
        assert txn.price == 0.0
        assert txn.net_amount == 0.0
        assert txn.reason == ""


class TestTransactionImmutability:
    """Test that transactions are immutable (frozen)."""

    def test_cannot_modify_after_creation(self):
        """Verify frozen dataclass behavior - cannot modify fields."""
        txn = Transaction(
            ticker="AAPL",
            shares=10.0,
            price=150.0
        )

        # Try to modify a field - should raise FrozenInstanceError
        with pytest.raises(FrozenInstanceError):
            txn.shares = 20.0

    def test_cannot_modify_string_field(self):
        """Verify cannot modify string fields."""
        txn = Transaction(ticker="AAPL")

        with pytest.raises(FrozenInstanceError):
            txn.ticker = "MSFT"

    def test_cannot_modify_id(self):
        """Verify cannot modify the auto-generated ID."""
        txn = Transaction()
        original_id = txn.id

        with pytest.raises(FrozenInstanceError):
            txn.id = "new-id"

        assert txn.id == original_id


class TestTransactionSerialization:
    """Test serializing transactions to dictionaries."""

    def test_to_dict_with_all_fields(self):
        """Serialize a complete transaction to dict."""
        txn = Transaction(
            id="test-123",
            roundtrip_id="rt-456",
            ticker="MSFT",
            date=date(2024, 3, 20),
            transaction_type="close",
            shares=5.0,
            price=420.50,
            net_amount=2102.50,
            reason="profit_target"
        )

        result = txn.to_dict()

        # Check all keys exist
        assert "id" in result
        assert "roundtrip_id" in result
        assert "ticker" in result
        assert "date" in result
        assert "transaction_type" in result
        assert "shares" in result
        assert "price" in result
        assert "net_amount" in result
        assert "reason" in result

        # Check values
        assert result["id"] == "test-123"
        assert result["roundtrip_id"] == "rt-456"
        assert result["ticker"] == "MSFT"
        assert result["date"] == "2024-03-20"  # ISO format
        assert result["transaction_type"] == "close"
        assert result["shares"] == 5.0
        assert result["price"] == 420.50
        assert result["net_amount"] == 2102.50
        assert result["reason"] == "profit_target"

    def test_to_dict_date_serialization(self):
        """Verify date is serialized as ISO format string."""
        txn = Transaction(date=date(2024, 12, 31))
        result = txn.to_dict()

        assert result["date"] == "2024-12-31"
        assert isinstance(result["date"], str)

    def test_to_dict_with_none_date(self):
        """Handle None date gracefully."""
        txn = Transaction(date=None)
        result = txn.to_dict()

        assert result["date"] is None


class TestUUIDGeneration:
    """Test automatic UUID generation."""

    def test_auto_generated_id_exists(self):
        """Verify ID is auto-generated when not provided."""
        txn = Transaction()

        assert txn.id is not None
        assert txn.id != ""
        assert len(txn.id) == 36  # Standard UUID string length

    def test_multiple_transactions_have_unique_ids(self):
        """Verify each transaction gets a unique UUID."""
        txn1 = Transaction()
        txn2 = Transaction()

        assert txn1.id != txn2.id
        assert len(txn1.id) > 0
        assert len(txn2.id) > 0

    def test_can_provide_custom_id(self):
        """Verify can override auto-generated ID with custom value."""
        custom_id = "my-custom-id-789"
        txn = Transaction(id=custom_id)

        assert txn.id == custom_id

    def test_uuid_format_is_valid(self):
        """Verify auto-generated ID looks like a valid UUID."""
        txn = Transaction()

        # Should have UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        assert len(txn.id) == 36
        assert txn.id.count('-') == 4


class TestTransactionTypes:
    """Test different transaction types (entry vs exit)."""

    def test_entry_transaction_negative_net_amount(self):
        """Entry transactions (buy) should have negative net_amount."""
        txn = Transaction(
            transaction_type="open",
            shares=10.0,
            price=100.0,
            net_amount=-1000.50  # Negative = cash out
        )

        assert txn.transaction_type == "open"
        assert txn.net_amount < 0

    def test_add_transaction_negative_net_amount(self):
        """Add transactions (DCA) should have negative net_amount."""
        txn = Transaction(
            transaction_type="add",
            shares=5.0,
            price=95.0,
            net_amount=-475.25
        )

        assert txn.transaction_type == "add"
        assert txn.net_amount < 0

    def test_exit_transaction_positive_net_amount(self):
        """Exit transactions (sell) should have positive net_amount."""
        txn = Transaction(
            transaction_type="close",
            shares=10.0,
            price=110.0,
            net_amount=1099.50  # Positive = cash in
        )

        assert txn.transaction_type == "close"
        assert txn.net_amount > 0

    def test_reduce_transaction_positive_net_amount(self):
        """Reduce transactions (partial sell) should have positive net_amount."""
        txn = Transaction(
            transaction_type="reduce",
            shares=5.0,
            price=105.0,
            net_amount=524.75
        )

        assert txn.transaction_type == "reduce"
        assert txn.net_amount > 0

    def test_fractional_shares_supported(self):
        """Verify fractional shares are supported."""
        txn = Transaction(
            shares=13.7,
            price=150.50
        )

        assert txn.shares == 13.7
        assert isinstance(txn.shares, float)


class TestTransactionReasons:
    """Test various transaction reasons."""

    def test_signal_reason(self):
        """Entry on signal."""
        txn = Transaction(reason="signal")
        assert txn.reason == "signal"

    def test_stop_loss_reason(self):
        """Exit on stop loss."""
        txn = Transaction(reason="stop_loss")
        assert txn.reason == "stop_loss"

    def test_time_exit_reason(self):
        """Exit on time-based rule."""
        txn = Transaction(reason="time_exit")
        assert txn.reason == "time_exit"

    def test_profit_target_reason(self):
        """Exit on profit target."""
        txn = Transaction(reason="profit_target")
        assert txn.reason == "profit_target"
