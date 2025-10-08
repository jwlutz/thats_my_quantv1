# Backtester V1 - Changelog

## Phase 3 Complete: Exit Rules System (2024)
- **Status**: ✅ 57/57 tests passing (100%)
- **File Added**: exitrule.py (280 lines)
- **Exit Rules**: TimeBasedExit, StopLossExit, TrailingStopExit, ProfitTargetExit
- **CompositeExitRule**: Priority-based exit evaluation (first match wins)
- **Features**: Stateful tracking (TrailingStopExit peak prices), partial exits (0.0-1.0 portion), serialization
- **Tests**: 57 comprehensive tests including edge cases and real-world scenarios
- **Total Tests**: 336/336 passing (100%)

## Phase 2B Complete: Entry Rules System (2024)
- **Status**: ✅ 110/110 tests passing (100%)
- **Files Added**: calculation.py, condition.py, entryrule.py
- **Architecture**: Composable Calculation + Condition pattern for maximum flexibility
- **Calculations**: EarningsSurprise, DayChange, PERatio, InstitutionalOwnership
- **Conditions**: GreaterThan, LessThan, Between
- **Entry Rules**: EntryRule, CompositeEntryRule (AND logic), Signal dataclass
- **Tests**: 110 tests including real yfinance integration
- **Key Feature**: Separates data extraction from decision logic for easy analysis-to-strategy pipeline

## Phase 2A Complete: DataProvider System (2024)
- **Status**: ✅ 37/37 tests passing (100%)
- **Files Added**: dataprovider.py (abstract interface), yfinance_provider.py (implementation)
- **Methods**: 11 data access methods (OHLCV, earnings, fundamentals, ownership, financials)
- **Features**: Retry logic, caching, timezone handling, point-in-time accuracy
- **Lines**: ~2,120 lines (implementation + tests)

## Phase 1 Complete: Position Management System (2024)
- **Status**: ✅ 127/127 tests passing (100%)
- **Classes**: Transaction, RoundTrip, TransactionCost, Portfolio
- **Features**: DCA support, partial exits, fractional shares, cost tracking, P&L calculations
- **Lines**: ~2,020 lines (implementation + tests)
