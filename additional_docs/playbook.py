"""
V1 Backtester - Complete Usage Playbook

This file demonstrates end-to-end usage of the backtesting framework.
Follow these examples to build and run your own strategies.

Organization:
1. Basic Components (Data, Rules, Sizers)
2. Building a Strategy
3. Running a Backtest
4. Analyzing Results
5. Saving/Loading for Jupyter Analysis
6. Advanced Patterns
"""

import logging
from datetime import date
import pickle

# ========== SETUP ==========

# Configure logging (optional - control verbosity)
logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for detailed output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# ========== 1. BASIC COMPONENTS ==========

print("=" * 70)
print("STEP 1: Import and Setup Data Provider")
print("=" * 70)

from backtester.yfinance_provider import YFinanceProvider

# Create data provider (works with any DataProvider implementation)
data_provider = YFinanceProvider()

print("[OK] Data provider ready\n")


print("=" * 70)
print("STEP 2: Define Entry Rules")
print("=" * 70)

from backtester.entryrule import EntryRule
from backtester.calculation import DayChange, EarningsSurprise
from backtester.condition import LessThan, GreaterThan

# Example 1: Red day rule (close < open)
red_day_rule = EntryRule(
    calculation=DayChange(),
    condition=LessThan(0),
    signal_type='red_day',
    priority=1.0  # Lower priority
)
print("[OK] Red day rule: Buy when close < open")

# Example 2: Earnings beat rule
earnings_rule = EntryRule(
    calculation=EarningsSurprise(),
    condition=GreaterThan(0.05),  # 5%+ beat
    signal_type='earnings_beat',
    priority=2.0  # Higher priority (checked first)
)
print("[OK] Earnings rule: Buy on 5%+ earnings beat")

# You can have multiple entry rules - they OR together
entry_rules = [red_day_rule, earnings_rule]
print(f"[OK] Total entry rules: {len(entry_rules)}\n")


print("=" * 70)
print("STEP 3: Define Exit Rules")
print("=" * 70)

from backtester.exitrule import (
    CompositeExitRule,
    StopLossExit,
    TimeBasedExit,
    TrailingStopExit,
    ProfitTargetExit
)

# Example 1: Simple time-based exit
simple_exit = TimeBasedExit(holding_days=30)
print("[OK] Simple exit: Close after 30 days")

# Example 2: Composite exit (multiple conditions, priority order)
composite_exit = CompositeExitRule(rules=[
    (StopLossExit(0.08), 1.0),           # 8% stop loss (full exit)
    (ProfitTargetExit(0.20, 0.5), 0.5),  # 20% gain, exit half
    (TimeBasedExit(30), 1.0)             # 30 days, exit remainder
])
print("[OK] Composite exit: Stop loss -> Profit target -> Time exit")

# Use composite for realistic strategies
exit_rules = composite_exit
print()


print("=" * 70)
print("STEP 4: Choose Position Sizer")
print("=" * 70)

from backtester.positionsizer import (
    FixedDollarAmount,
    PercentPortfolio,
    EqualWeight
)

# Example 1: Fixed dollar amount
fixed_sizer = FixedDollarAmount(dollar_amount=5000)
print("[OK] Fixed sizer: $5,000 per position")

# Example 2: Percentage of portfolio
percent_sizer = PercentPortfolio(percent=0.10)  # 10%
print("[OK] Percent sizer: 10% of portfolio per position")

# Example 3: Equal weight across max positions
equal_sizer = EqualWeight()
print("[OK] Equal weight: Divide capital equally")

# Choose one
position_sizer = equal_sizer
print()


print("=" * 70)
print("STEP 5: Define Universe")
print("=" * 70)

# Your stock universe
universe = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']
print(f"[OK] Universe: {len(universe)} tickers")
print(f"  {universe}\n")


# ========== 2. BUILD STRATEGY ==========

print("=" * 70)
print("STEP 6: Build Complete Strategy")
print("=" * 70)

from backtester.strategy import Strategy

strategy = Strategy(
    name="Mag7 DCA Strategy",
    entry_rules=entry_rules,
    exit_rules=exit_rules,
    position_sizer=position_sizer,
    universe=universe,
    description="Buy Mag7 on red days or earnings beats"
)

# Validate strategy
strategy.validate()
print(f"[OK] Strategy created: {strategy.name}")
print(f"  Entry rules: {len(strategy.entry_rules)}")
print(f"  Universe: {len(strategy.universe)} tickers")
print()


# ========== 3. RUN BACKTEST ==========

print("=" * 70)
print("STEP 7: Configure and Run Backtest")
print("=" * 70)

from backtester.backtester import Backtester

# Create backtester
backtester = Backtester(
    strategy=strategy,
    data_provider=data_provider,
    initial_capital=100000,
    start_date=date(2023, 1, 1),
    end_date=date(2023, 12, 31),
    commission=1.0,        # $1 per trade
    slippage=0.001,        # 0.1% slippage
    max_positions=5,       # Max 5 concurrent positions
    fractional_shares=True
)

print(f"[OK] Backtester configured")
print(f"  Capital: ${backtester.initial_capital:,.0f}")
print(f"  Period: {backtester.start_date} to {backtester.end_date}")
print(f"  Max positions: {backtester.portfolio.max_positions}")
print()

# Run backtest
print("Running backtest...")
results = backtester.run()
print("[OK] Backtest complete!\n")


# ========== 4. ANALYZE RESULTS ==========

print("=" * 70)
print("STEP 8: Analyze Results")
print("=" * 70)

# Print full summary
results.print_summary()

# Access individual metrics
print("\nQuick Metrics:")
print(f"  Total Return: {results.total_return:.2%}")
print(f"  Sharpe Ratio: {results.sharpe_ratio:.2f}")
print(f"  Max Drawdown: {results.max_drawdown:.2%}")
print(f"  Total Trades: {results.total_trades}")
print(f"  Win Rate: {results.win_rate:.2%}")
print()


# ========== 5. EXPORT DATA FOR ANALYSIS ==========

print("=" * 70)
print("STEP 9: Export Data for Jupyter Analysis")
print("=" * 70)

# Get DataFrames for analysis
equity_curve = results.get_equity_curve()
trades_df = results.get_trades_df()
transactions_df = results.get_transaction_log_df()

print(f"[OK] Equity curve: {len(equity_curve)} days")
print(f"[OK] Trades: {len(trades_df)} closed positions")
print(f"[OK] Transactions: {len(transactions_df)} total transactions")
print()

# Preview equity curve
print("Equity Curve Preview:")
print(equity_curve.head())
print()

# Preview trades
if not trades_df.empty:
    print("Trades Preview:")
    print(trades_df.head())
    print()

# Save results object for later analysis
with open('backtest_results.pkl', 'wb') as f:
    pickle.dump(results, f)
print("[OK] Saved results to 'backtest_results.pkl'\n")


print("=" * 70)
print("STEP 10: Use in Jupyter Notebook")
print("=" * 70)

print("""
To analyze in Jupyter:

```python
import pickle
import matplotlib.pyplot as plt

# Load results
with open('backtest_results.pkl', 'rb') as f:
    results = pickle.load(f)

# Get data
equity = results.get_equity_curve()
trades = results.get_trades_df()

# Plot equity curve
plt.figure(figsize=(12, 6))
plt.plot(equity['date'], equity['equity'])
plt.title('Equity Curve')
plt.xlabel('Date')
plt.ylabel('Portfolio Value ($)')
plt.grid(True)
plt.show()

# Analyze trades
print(trades.describe())
print(f"Win rate: {(trades['pnl'] > 0).mean():.2%}")

# Export to CSV
equity.to_csv('equity_curve.csv', index=False)
trades.to_csv('trades.csv', index=False)
```
""")


# ========== 6. ADVANCED PATTERNS ==========

print("=" * 70)
print("ADVANCED PATTERNS")
print("=" * 70)

print("""
1. SAVE/LOAD STRATEGY (YAML):

   # Save strategy
   strategy.to_yaml('strategies/mag7_dca.yaml')

   # Load strategy
   from backtester.strategy import Strategy
   strategy = Strategy.from_yaml('strategies/mag7_dca.yaml')


2. CUSTOM EXIT RULE PER SIGNAL:

   # In your custom EntryRule.should_enter():
   signal = Signal(
       ticker='AAPL',
       metadata={
           'exit_rule': TrailingStopExit(0.05)  # Custom exit!
       }
   )
   # Backtester will use this instead of strategy default


3. PARAMETER SWEEP (find best settings):

   results_list = []
   for stop_pct in [0.05, 0.08, 0.10]:
       for holding_days in [20, 30, 40]:
           exit_rule = CompositeExitRule([
               (StopLossExit(stop_pct), 1.0),
               (TimeBasedExit(holding_days), 1.0)
           ])

           strategy = Strategy(...)
           backtester = Backtester(...)
           results = backtester.run()

           results_list.append({
               'stop_pct': stop_pct,
               'holding_days': holding_days,
               'sharpe': results.sharpe_ratio,
               'return': results.total_return
           })

   # Find best parameters
   best = max(results_list, key=lambda x: x['sharpe'])


4. COMPARE STRATEGIES:

   strategies = [
       ('Red Day', red_day_strategy),
       ('Earnings', earnings_strategy),
       ('Combined', combined_strategy)
   ]

   for name, strat in strategies:
       bt = Backtester(strategy=strat, ...)
       res = bt.run()
       print(f"{name}: Return={res.total_return:.2%}, Sharpe={res.sharpe_ratio:.2f}")


5. ACCESS RAW PORTFOLIO DATA:

   # After backtest
   portfolio = backtester.portfolio

   # Get all closed roundtrips
   for rt in portfolio.closed_roundtrips:
       print(f"{rt.ticker}: {rt.realized_pnl:.2f}")

   # Get transaction log
   txns = portfolio.transaction_log
   for txn in txns:
       print(f"{txn.date}: {txn.transaction_type} {txn.ticker}")

   # Get equity history
   for entry in portfolio.equity_history:
       print(f"{entry['date']}: ${entry['value']:,.2f}")
""")

print("\n" + "=" * 70)
print("PLAYBOOK COMPLETE!")
print("=" * 70)
print("""
Next Steps:
1. Modify universe, rules, or parameters above
2. Run this file: python playbook.py
3. Open backtest_results.pkl in Jupyter for deep analysis
4. See tests/ directory for more examples
5. Read SPEC.md for full component documentation

Happy backtesting!
""")
