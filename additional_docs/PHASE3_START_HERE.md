# Phase 3: Exit Rules System - Implementation Guide

## 🎯 Current Status: 50% Complete

**✅ Completed:**
- Phase 1: Position Management (Transaction, RoundTrip, Portfolio, TransactionCost)
- Phase 2: Data & Entry Rules (DataProvider, Calculation, Condition, EntryRule)
  - 110/110 tests passing
  - Composable Calculation + Condition architecture

**🔄 Next: Phase 3 - Exit Rules**

---

## 📋 What to Build

### 1. ExitRule Base Class
**File:** `backtester/exitrule.py`

**Abstract interface:**
```python
from abc import ABC, abstractmethod
from typing import Tuple

class ExitRule(ABC):
    @abstractmethod
    def should_exit(self, roundtrip, date, price) -> Tuple[bool, float, str]:
        """
        Check if should exit position.

        Args:
            roundtrip: RoundTrip object with position context
            date: Current date
            price: Current price

        Returns:
            (should_exit, exit_portion, reason)
            - should_exit: bool
            - exit_portion: 0.0-1.0 (1.0 = full exit, 0.5 = exit half)
            - reason: string like "stop_loss", "time_exit", "profit_target"
        """
        pass
```

### 2. Concrete Exit Rules (4 implementations)

**TimeBasedExit** - Exit after N days
```python
class TimeBasedExit(ExitRule):
    def __init__(self, holding_days: int):
        self.holding_days = holding_days

    def should_exit(self, roundtrip, date, price):
        if roundtrip.get_holding_days(date) >= self.holding_days:
            return (True, 1.0, "time_exit")
        return (False, 0, "")
```

**StopLossExit** - Exit if loss exceeds threshold
```python
class StopLossExit(ExitRule):
    def __init__(self, stop_pct: float):
        self.stop_pct = stop_pct  # 0.08 = 8% stop

    def should_exit(self, roundtrip, date, price):
        avg_entry = roundtrip.average_entry_price
        pnl_pct = (price - avg_entry) / avg_entry

        if pnl_pct <= -self.stop_pct:
            return (True, 1.0, "stop_loss")
        return (False, 0, "")
```

**TrailingStopExit** - Exit if price drops X% from peak
```python
class TrailingStopExit(ExitRule):
    def __init__(self, trailing_pct: float):
        self.trailing_pct = trailing_pct
        self._peak_prices = {}  # roundtrip_id -> peak_price (STATEFUL!)

    def should_exit(self, roundtrip, date, price):
        # Track peak price for this position
        if roundtrip.id not in self._peak_prices:
            self._peak_prices[roundtrip.id] = roundtrip.average_entry_price

        # Update peak
        if price > self._peak_prices[roundtrip.id]:
            self._peak_prices[roundtrip.id] = price

        # Check trailing stop
        peak = self._peak_prices[roundtrip.id]
        drawdown = (peak - price) / peak

        if drawdown >= self.trailing_pct:
            return (True, 1.0, "trailing_stop")
        return (False, 0, "")
```

**ProfitTargetExit** - Exit when profit target hit (supports partial exits)
```python
class ProfitTargetExit(ExitRule):
    def __init__(self, target_pct: float, exit_portion: float = 1.0):
        self.target_pct = target_pct  # 0.20 = 20% gain
        self.exit_portion = exit_portion  # 0.5 = exit half position

    def should_exit(self, roundtrip, date, price):
        avg_entry = roundtrip.average_entry_price
        pnl_pct = (price - avg_entry) / avg_entry

        if pnl_pct >= self.target_pct:
            return (True, self.exit_portion, "profit_target")
        return (False, 0, "")
```

### 3. CompositeExitRule (CRITICAL!)

**Priority-based exit evaluation:**
```python
class CompositeExitRule(ExitRule):
    """
    Evaluate multiple exit rules in priority order.
    First rule that triggers wins.
    """

    def __init__(self, rules: List[Tuple[ExitRule, float]]):
        """
        Args:
            rules: List of (ExitRule, exit_portion) tuples
                   Evaluated in order, first match wins
        """
        self.rules = rules

    def should_exit(self, roundtrip, date, price):
        # Try each rule in order
        for rule, portion in self.rules:
            should_exit, _, reason = rule.should_exit(roundtrip, date, price)

            if should_exit:
                # Use configured portion, not rule's portion
                return (True, portion, reason)

        return (False, 0, "")
```

**Example usage:**
```python
composite = CompositeExitRule(
    rules=[
        (StopLossExit(0.08), 1.0),      # 8% stop, full exit (checked first)
        (ProfitTargetExit(0.20), 0.5),  # 20% gain, exit half
        (TimeBasedExit(30), 1.0)        # 30 days, full exit (checked last)
    ]
)
```

---

## 🧪 Tests to Write

**File:** `tests/test_exitrule.py`

### Test Categories:

**1. TimeBasedExit Tests**
- Exit triggers at exact holding_days threshold
- No exit before threshold
- Serialization round-trip

**2. StopLossExit Tests**
- Exit triggers at exact stop_pct threshold
- No exit when loss within tolerance
- Positive P&L doesn't trigger stop

**3. TrailingStopExit Tests**
- Peak price tracking (stateful!)
- Exit when drawdown from peak exceeds threshold
- Peak updates correctly as price rises
- Multiple positions tracked independently

**4. ProfitTargetExit Tests**
- Exit triggers at exact target_pct
- Partial exits work (exit_portion 0.0-1.0)
- No exit when profit below target

**5. CompositeExitRule Tests**
- Priority ordering (first match wins)
- Stop loss triggers before time exit
- Multiple rules evaluated correctly
- Partial exits from composite
- Serialization with nested rules

---

## 🔑 Key Implementation Details

### ExitRule Design Principles:
1. **Receives RoundTrip object** - has full position context (cost basis, holding period, etc.)
2. **Returns 3-tuple** - (should_exit: bool, exit_portion: float, reason: str)
3. **Partial exits supported** - exit_portion 0.0-1.0 (0.5 = sell half)
4. **Reason strings** - used in transaction logs for analysis
5. **Stateful tracking** - TrailingStopExit needs to remember peak prices

### Serialization Requirements:
- All rules need `to_dict()` and `from_dict()` for YAML config
- CompositeExitRule must recursively serialize nested rules
- Factory function `create_exit_rule()` for deserialization

### Important Edge Cases:
- TrailingStopExit: What if peak price never set? (initialize to entry price)
- ProfitTargetExit: Can exit_portion be 0.0 or negative? (validate in __init__)
- CompositeExitRule: What if rules list is empty? (return False, 0, "")
- All rules: Handle roundtrip with remaining_shares = 0? (should never happen, but validate)

---

## 📦 Files to Create

```
backtester/
  exitrule.py          (~250 lines)

tests/
  test_exitrule.py     (~500 lines)
```

---

## 🎯 Success Criteria

- [ ] ExitRule ABC implemented
- [ ] 4 concrete exit rules implemented
- [ ] CompositeExitRule with priority ordering
- [ ] Factory function for deserialization
- [ ] ~60-80 tests written
- [ ] All tests passing (100%)
- [ ] TrailingStopExit stateful tracking works
- [ ] Partial exits work correctly
- [ ] Serialization round-trips work

---

## 📚 Reference

**SPEC Location:** Lines 900-1121 in SPEC.md

**Related Files:**
- `backtester/roundtrip.py` - RoundTrip class (has get_holding_days(), average_entry_price)
- `backtester/entryrule.py` - Similar pattern (good reference for structure)
- `backtester/portfolio.py` - Will use exit rules in reduce_position() calls

**Existing Pattern:**
Entry rules use composable Calculation + Condition. Exit rules are simpler (direct evaluation), but CompositeExitRule allows composition.

---

## 💡 Tips for Implementation

1. **Start with TimeBasedExit** - simplest rule, good for testing infrastructure
2. **Then StopLossExit** - tests basic P&L calculation
3. **Then ProfitTargetExit** - tests partial exits
4. **Then TrailingStopExit** - tests stateful tracking
5. **Finally CompositeExitRule** - tests priority ordering

6. **Write tests as you go** - don't wait until the end
7. **Use descriptive test names** - `test_trailing_stop_updates_peak_price_correctly`
8. **Test edge cases** - zero shares, negative prices, empty rule lists
9. **Test serialization** - to_dict() → from_dict() round-trip for each rule

---

## 🚀 Next Phase After This

**Phase 4:** Backtester Engine + Results
- PositionSizer class
- Strategy class (bundles entry + exit + universe)
- Backtester main loop
- Results class with performance metrics

**Estimated Time:** 8-10 hours

---

## ✅ When Complete

Update these files:
- `CHANGELOG.md` - Add Phase 3 completion entry
- `to_do.md` - Update progress to 60%, mark Phase 3 complete
- `SPEC.md` - Add implementation note to section 7 (Exit Rules)

Run full test suite:
```bash
python -m pytest tests/ -v
```

Expected: ~170+ tests passing (110 existing + ~60 new)

---

**Good luck! The exit rule system is the last major component before backtesting!** 🎉
