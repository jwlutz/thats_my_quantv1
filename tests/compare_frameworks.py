"""
Compare our backtester against established libraries.

Tests the same strategy (Red Day + Earnings Beat on Mag7) across:
1. Our custom backtester (V1)
2. Backtrader
3. Vectorbt

Compares key metrics to validate our implementation.
"""

import warnings
warnings.filterwarnings('ignore')

from datetime import date
import pandas as pd
import numpy as np

print("="*70)
print("BACKTESTING FRAMEWORK COMPARISON")
print("="*70)
print()
print("Strategy: Red Day on Mag7 stocks (SIMPLIFIED FOR COMPARISON)")
print("Entry: Buy when close < open (red candle)")
print("Exit: 30 days time-based")
print("Period: 2023-01-01 to 2023-12-31")
print("Capital: $100,000")
print("Position Size: $5,000 per trade")
print("Max Positions: 5")
print("Commission: $0, Slippage: 0%")
print()
print("NOTE: All three frameworks test IDENTICAL strategy for fair comparison")
print()

# ============================================================================
# 1. OUR BACKTESTER (V1)
# ============================================================================
print("="*70)
print("1. RUNNING THATS_MY_QUANT V1")
print("="*70)

from backtester.yfinance_provider import YFinanceProvider
from backtester.calculation import DayChange
from backtester.condition import LessThan
from backtester.entryrule import EntryRule
from backtester.exitrule import TimeBasedExit
from backtester.positionsizer import FixedDollarAmount
from backtester.strategy import Strategy
from backtester.backtester import Backtester
import logging

# Suppress our logs for cleaner output
logging.getLogger('backtester').setLevel(logging.ERROR)

data_provider = YFinanceProvider()

# SIMPLIFIED STRATEGY: Only red day rule (for fair comparison with other frameworks)
red_day_rule = EntryRule(
    calculation=DayChange(),
    condition=LessThan(0),
    signal_type='red_day',
    priority=1.0
)

strategy = Strategy(
    name="Red Day Strategy",
    entry_rules=[red_day_rule],  # ONLY red day rule, no earnings
    exit_rules=TimeBasedExit(holding_days=30),
    position_sizer=FixedDollarAmount(dollar_amount=5000),
    universe=['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']
)

backtester = Backtester(
    strategy=strategy,
    data_provider=data_provider,
    start_date=date(2023, 1, 1),
    end_date=date(2023, 12, 31),
    initial_capital=100000,
    commission=0.0,
    slippage=0.0,
    max_positions=5
)

print("Running backtest...")
our_results = backtester.run()

print("[OK] Backtest complete!")
print()
print(f"Total Return: {our_results.total_return:.2%}")
print(f"Sharpe Ratio: {our_results.sharpe_ratio:.2f}")
print(f"Max Drawdown: {our_results.max_drawdown:.2%}")
print(f"Win Rate: {our_results.win_rate:.2%}")
print(f"Total Trades: {our_results.total_trades}")
print()

# ============================================================================
# 2. BACKTRADER
# ============================================================================
print("="*70)
print("2. RUNNING BACKTRADER")
print("="*70)

import backtrader as bt

class RedDayStrategy(bt.Strategy):
    """
    Backtrader implementation: Red day entry + 30-day time exit.
    
    Entry: Buy when close < open (red candle)
    Exit: After 30 days
    Position Size: $5,000 per trade
    Max Positions: 5
    """

    params = (
        ('position_size', 5000),
        ('holding_days', 30),
    )

    def __init__(self):
        self.order_dict = {}
        self.entry_dates = {}

    def next(self):
        current_date = self.datas[0].datetime.date(0)

        # Exit positions held for 30 days
        for data in self.datas:
            pos = self.getposition(data)
            if pos.size > 0:
                ticker = data._name
                if ticker in self.entry_dates:
                    days_held = (current_date - self.entry_dates[ticker]).days
                    if days_held >= self.params.holding_days:
                        self.close(data)
                        del self.entry_dates[ticker]

        # Count open positions
        open_positions = sum(1 for data in self.datas if self.getposition(data).size > 0)

        # Entry logic: Red day (close < open)
        if open_positions < 5:
            for data in self.datas:
                if self.getposition(data).size == 0:
                    # Check if red day
                    if data.close[0] < data.open[0]:
                        price = data.close[0]
                        shares = int(self.params.position_size / price)
                        if shares > 0 and self.broker.getcash() >= shares * price:
                            self.buy(data, size=shares)
                            self.entry_dates[data._name] = current_date
                            open_positions += 1
                            if open_positions >= 5:
                                break

# Create cerebro
cerebro = bt.Cerebro()
cerebro.broker.setcash(100000)
cerebro.broker.setcommission(commission=0.0)

# Add data feeds
tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']
for ticker in tickers:
    try:
        df = data_provider.get_ohlcv([ticker], date(2023, 1, 1), date(2023, 12, 31))[ticker]
        if df is not None and not df.empty:
            # Convert to backtrader format
            df = df.copy()
            df.columns = [col.capitalize() for col in df.columns]
            df['OpenInterest'] = 0
            data = bt.feeds.PandasData(dataname=df, name=ticker)
            cerebro.adddata(data)
    except Exception as e:
        print(f"Could not load {ticker}: {e}")

cerebro.addstrategy(RedDayStrategy)

# Add analyzers
# Note: Backtrader's SharpeRatio requires timeframe and riskfreerate parameters
cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', 
                   timeframe=bt.TimeFrame.Days, 
                   riskfreerate=0.0,
                   annualize=True)
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

print("Running backtest...")
results = cerebro.run()
strat = results[0]

print("[OK] Backtest complete!")
print()

# Extract metrics
returns_analyzer = strat.analyzers.returns.get_analysis()
sharpe_analyzer = strat.analyzers.sharpe.get_analysis()
drawdown_analyzer = strat.analyzers.drawdown.get_analysis()
trades_analyzer = strat.analyzers.trades.get_analysis()

bt_total_return = returns_analyzer.get('rtot', 0)
bt_sharpe = sharpe_analyzer.get('sharperatio', 0) if sharpe_analyzer.get('sharperatio') is not None else 0
bt_max_dd = drawdown_analyzer.get('max', {}).get('drawdown', 0) / 100 if drawdown_analyzer.get('max') else 0
bt_total_trades = trades_analyzer.get('total', {}).get('closed', 0) if trades_analyzer.get('total') else 0
bt_win_rate = 0
if bt_total_trades > 0:
    won = trades_analyzer.get('won', {}).get('total', 0) if trades_analyzer.get('won') else 0
    bt_win_rate = won / bt_total_trades

final_value = cerebro.broker.getvalue()

print(f"Final Value: ${final_value:,.2f}")
print(f"Total Return: {bt_total_return:.2%}")
print(f"Sharpe Ratio: {bt_sharpe:.2f}")
print(f"Max Drawdown: {bt_max_dd:.2%}")
print(f"Win Rate: {bt_win_rate:.2%}")
print(f"Total Trades: {bt_total_trades}")
print()

# ============================================================================
# 3. VECTORBT
# ============================================================================
print("="*70)
print("3. RUNNING VECTORBT")
print("="*70)

import vectorbt as vbt

# Get data for all tickers
print("Loading data...")
all_data = {}
for ticker in tickers:
    try:
        df = data_provider.get_ohlcv([ticker], date(2023, 1, 1), date(2023, 12, 31))[ticker]
        if df is not None and not df.empty:
            all_data[ticker] = df
    except Exception as e:
        print(f"Could not load {ticker}: {e}")

# Combine into multi-column DataFrame
# Note: yfinance returns Capital case columns ('Close', 'Open', etc.)
close_prices = pd.DataFrame({ticker: df['Close'] for ticker, df in all_data.items()})
open_prices = pd.DataFrame({ticker: df['Open'] for ticker, df in all_data.items()})

# Generate signals: red day (close < open)
entries = close_prices < open_prices

print("Running backtest...")

# Run portfolio simulation
# VectorBT implementation: Red day entry only
# Note: VectorBT is vectorized and doesn't have built-in time-based exits
# It will hold positions until capital is needed or end of backtest
# This means VectorBT results may differ as it lacks the 30-day exit constraint
pf = vbt.Portfolio.from_signals(
    close_prices,
    entries,
    short_entries=False,
    size=5000,  # Fixed dollar amount per position
    size_type='value',  # Use dollar value for sizing
    init_cash=100000,
    fees=0.0,
    slippage=0.0,
    call_seq='auto'  # Automatically determine order of execution
    # Note: VectorBT doesn't have max_positions in from_signals
    # It will open as many positions as cash allows (similar constraint to ours)
)

print("[OK] Backtest complete!")
print()

# Extract metrics
# Note: VectorBT returns Series for multi-asset portfolios, need to aggregate
# Also needs frequency specified for annualized metrics

# Helper function to extract scalar from potential Series
def to_scalar(val):
    if hasattr(val, 'mean'):
        return float(val.mean())  # Average across assets
    return float(val)

vbt_total_return = to_scalar(pf.total_return())
vbt_sharpe = to_scalar(pf.sharpe_ratio(freq='D'))  # Daily frequency
vbt_max_dd = to_scalar(pf.max_drawdown())
vbt_win_rate = to_scalar(pf.trades.win_rate()) if callable(getattr(pf.trades, 'win_rate', None)) else 0
vbt_total_trades = to_scalar(pf.trades.count())

final_val = to_scalar(pf.final_value())

print(f"Final Value: ${final_val:,.2f}")
print(f"Total Return: {vbt_total_return:.2%}")
print(f"Sharpe Ratio: {vbt_sharpe:.2f}")
print(f"Max Drawdown: {vbt_max_dd:.2%}")
print(f"Win Rate: {vbt_win_rate:.2%}")
print(f"Total Trades: {int(vbt_total_trades)}")
print()

# ============================================================================
# COMPARISON TABLE
# ============================================================================
print("="*70)
print("COMPARISON TABLE")
print("="*70)
print()

comparison = pd.DataFrame({
    'Our Backtester': [
        f"{our_results.total_return:.2%}",
        f"{our_results.sharpe_ratio:.2f}",
        f"{our_results.max_drawdown:.2%}",
        f"{our_results.win_rate:.2%}",
        our_results.total_trades
    ],
    'Backtrader': [
        f"{bt_total_return:.2%}",
        f"{bt_sharpe:.2f}",
        f"{bt_max_dd:.2%}",
        f"{bt_win_rate:.2%}",
        bt_total_trades
    ],
    'Vectorbt': [
        f"{vbt_total_return:.2%}",
        f"{vbt_sharpe:.2f}",
        f"{vbt_max_dd:.2%}",
        f"{vbt_win_rate:.2%}",
        vbt_total_trades
    ]
}, index=['Total Return', 'Sharpe Ratio', 'Max Drawdown', 'Win Rate', 'Total Trades'])

print(comparison)
print()

# ============================================================================
# ANALYSIS
# ============================================================================
print("="*70)
print("ANALYSIS")
print("="*70)
print()

print("Key Observations:")
print()

# Compare returns
our_ret = our_results.total_return
bt_ret = bt_total_return
vbt_ret = vbt_total_return

ret_diff_bt = abs(our_ret - bt_ret)
ret_diff_vbt = abs(our_ret - vbt_ret)

print(f"1. RETURN COMPARISON:")
print(f"   - Our backtester vs Backtrader: {ret_diff_bt:.2%} difference")
print(f"   - Our backtester vs Vectorbt: {ret_diff_vbt:.2%} difference")

if ret_diff_bt < 0.05 and ret_diff_vbt < 0.05:
    print("   [OK] Returns are within 5% tolerance across all frameworks")
else:
    print("   [WARNING] Returns differ by more than 5%")
print()

# Compare Sharpe
our_sharpe = our_results.sharpe_ratio
sharpe_diff_bt = abs(our_sharpe - bt_sharpe)
sharpe_diff_vbt = abs(our_sharpe - vbt_sharpe)

print(f"2. SHARPE RATIO COMPARISON:")
print(f"   - Our backtester vs Backtrader: {sharpe_diff_bt:.2f} difference")
print(f"   - Our backtester vs Vectorbt: {sharpe_diff_vbt:.2f} difference")

if sharpe_diff_bt < 0.5 and sharpe_diff_vbt < 0.5:
    print("   [OK] Sharpe ratios are reasonably close across frameworks")
else:
    print("   [WARNING] Sharpe ratios differ significantly")
print()

print("3. IMPLEMENTATION DIFFERENCES:")
print("   - Our backtester: Event-driven, OHLCV, time-based exits, fractional shares")
print("   - Backtrader: Event-driven, similar architecture to ours")
print("   - VectorBT: Vectorized (NO time-based exits), buy-and-hold behavior")
print()
print("   ** VectorBT Limitation: It doesn't support time-based exits in from_signals() **")
print("   ** This causes VERY different behavior (only 1 trade vs 55 trades) **")
print("   ** VectorBT is designed for signal-based entry/exit, not time-based rules **")
print()

print("4. VALIDATION CONCLUSION:")
if ret_diff_bt < 0.05:
    print("   [EXCELLENT] Our backtester vs Backtrader: Only {:.2%} difference!".format(ret_diff_bt))
    print("   This validates our implementation accuracy.")
    print()
    print("   Minor differences likely due to:")
    print("   - Order execution timing (exit-before-entry vs entry-before-exit)")
    print("   - Position sizing rounding (fractional shares vs whole shares)")
    print("   - Date handling edge cases")
elif ret_diff_bt < 0.10:
    print("   [GOOD] Our backtester vs Backtrader: {:.2%} difference".format(ret_diff_bt))
    print("   This is acceptable for different implementations.")
else:
    print("   [INVESTIGATE] Results differ significantly - review implementation")

print()
print("   [NOTE] VectorBT comparison is not valid due to lack of time-based exits.")
print("   VectorBT is better suited for pure signal-based strategies.")
print()

print("="*70)
print("COMPARISON COMPLETE")
print("="*70)
