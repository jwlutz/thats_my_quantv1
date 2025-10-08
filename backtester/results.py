from datetime import date
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from backtester.portfolio import Portfolio
from backtester.strategy import Strategy


class Results:
    """
    Backtest performance metrics and analysis.

    Provides comprehensive analysis including:
    - Returns (total, annualized, per-trade)
    - Risk metrics (Sharpe, Sortino, max drawdown, volatility)
    - Trade statistics (win rate, profit factor, avg win/loss)
    - Data exports (transaction log, roundtrips, equity curve)

    Example:
        >>> results = backtester.run()
        >>>
        >>> print(f"Total Return: {results.total_return:.2%}")
        >>> print(f"Sharpe Ratio: {results.sharpe_ratio:.2f}")
        >>> print(f"Win Rate: {results.win_rate:.2%}")
        >>>
        >>> results.print_summary()
    """

    def __init__(self,
                 portfolio: Portfolio,
                 strategy: Strategy,
                 start_date: date,
                 end_date: date,
                 initial_capital: float):
        """
        Initialize Results from completed backtest.

        Args:
            portfolio: Portfolio instance after backtest
            strategy: Strategy that was backtested
            start_date: Backtest start date
            end_date: Backtest end date
            initial_capital: Starting capital
        """
        self.portfolio = portfolio
        self.strategy = strategy
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital

        # Build DataFrames for analysis
        self._equity_df = self._build_equity_df()
        self._trades_df = self._build_trades_df()

    def _build_equity_df(self) -> pd.DataFrame:
        """
        Build DataFrame from equity history.

        Returns:
            DataFrame with columns: date, equity
        """
        if not self.portfolio.equity_history:
            return pd.DataFrame(columns=['date', 'equity'])

        df = pd.DataFrame([
            {'date': pd.Timestamp(entry['date']), 'equity': entry['value']}
            for entry in self.portfolio.equity_history
        ])
        df = df.sort_values('date').reset_index(drop=True)
        return df

    def _build_trades_df(self) -> pd.DataFrame:
        """
        Build DataFrame of closed trades (realized P&L only).

        Returns:
            DataFrame with trade details
        """
        trades = []

        for roundtrip in self.portfolio.closed_roundtrips:
            if roundtrip.transactions:
                entry_txn = roundtrip.transactions[0]  # First transaction
                exit_txn = roundtrip.transactions[-1]  # Last transaction

                # Calculate holding period
                holding_days = (exit_txn.date - entry_txn.date).days

                trades.append({
                    'ticker': roundtrip.ticker,
                    'entry_date': entry_txn.date,
                    'exit_date': exit_txn.date,
                    'holding_days': holding_days,
                    'shares': roundtrip.total_shares,
                    'entry_price': roundtrip.average_entry_price,
                    'exit_price': exit_txn.price,
                    'pnl': roundtrip.realized_pnl,
                    'pnl_pct': roundtrip.realized_pnl / roundtrip._total_cost if roundtrip._total_cost > 0 else 0
                })

        if not trades:
            return pd.DataFrame()

        return pd.DataFrame(trades)

    # ========== RETURN METRICS ==========

    @property
    def total_return(self) -> float:
        """
        Total return over backtest period.

        Returns:
            float: (final_equity - initial_capital) / initial_capital
        """
        if self._equity_df.empty:
            return 0.0

        final_equity = self._equity_df.iloc[-1]['equity']
        return (final_equity - self.initial_capital) / self.initial_capital

    @property
    def annualized_return(self) -> float:
        """
        Annualized return (CAGR).

        Returns:
            float: Compound annual growth rate
        """
        if self._equity_df.empty or len(self._equity_df) < 2:
            return 0.0

        days = (self.end_date - self.start_date).days
        years = days / 365.25

        if years <= 0:
            return 0.0

        final_equity = self._equity_df.iloc[-1]['equity']
        cagr = (final_equity / self.initial_capital) ** (1 / years) - 1
        return cagr

    # ========== RISK METRICS ==========

    @property
    def volatility(self) -> float:
        """
        Annualized volatility of daily returns.

        Returns:
            float: Standard deviation of returns * sqrt(252)
        """
        if len(self._equity_df) < 2:
            return 0.0

        daily_returns = self._equity_df['equity'].pct_change().dropna()
        
        if len(daily_returns) == 0:
            return 0.0
            
        return daily_returns.std() * np.sqrt(252)

    @property
    def sharpe_ratio(self) -> float:
        """
        Sharpe ratio (annualized, risk-free rate = 0%).

        CRITICAL: Calculated from equity curve, NOT individual trades!

        Returns:
            float: (annualized_return - 0) / volatility
        """
        vol = self.volatility
        if vol == 0:
            return 0.0

        return self.annualized_return / vol

    def sharpe_ratio_with_rf(self, risk_free_rate: float = 0.02) -> float:
        """
        Sharpe ratio with custom risk-free rate.

        Args:
            risk_free_rate: Annual risk-free rate (0.02 = 2%)

        Returns:
            float: (annualized_return - rf) / volatility
        """
        vol = self.volatility
        if vol == 0:
            return 0.0

        return (self.annualized_return - risk_free_rate) / vol

    @property
    def sortino_ratio(self) -> float:
        """
        Sortino ratio (annualized, risk-free rate = 0%).

        Uses downside deviation instead of total volatility.

        Returns:
            float: annualized_return / downside_deviation
        """
        if len(self._equity_df) < 2:
            return 0.0

        daily_returns = self._equity_df['equity'].pct_change().dropna()
        
        if len(daily_returns) == 0:
            return 0.0

        # Only negative returns
        downside_returns = daily_returns[daily_returns < 0]
        
        if len(downside_returns) == 0:
            return float('inf') if self.annualized_return > 0 else 0.0

        downside_vol = downside_returns.std() * np.sqrt(252)

        if downside_vol == 0:
            return 0.0

        return self.annualized_return / downside_vol

    @property
    def max_drawdown(self) -> float:
        """
        Maximum peak-to-trough drawdown.

        Returns:
            float: Largest decline from peak as decimal (0.20 = 20% drawdown)
        """
        if self._equity_df.empty:
            return 0.0

        equity = self._equity_df['equity']
        cummax = equity.cummax()
        drawdown = (equity - cummax) / cummax
        return abs(drawdown.min())

    @property
    def max_drawdown_duration(self) -> int:
        """
        Longest drawdown period in days.

        Returns:
            int: Maximum days between peak and recovery
        """
        if self._equity_df.empty or len(self._equity_df) < 2:
            return 0

        equity = self._equity_df['equity'].values
        dates = self._equity_df['date'].values

        peak = equity[0]
        peak_date = dates[0]
        max_duration = 0

        for value, dt in zip(equity, dates):
            if value >= peak:
                # New peak - update
                peak = value
                peak_date = dt
            else:
                # In drawdown
                # Convert numpy.timedelta64 to int days
                duration_td = dt - peak_date
                if hasattr(duration_td, 'days'):
                    duration = duration_td.days
                else:
                    # numpy.timedelta64 case
                    duration = int(duration_td / pd.Timedelta(days=1))

                if duration > max_duration:
                    max_duration = duration

        return max_duration

    @property
    def calmar_ratio(self) -> float:
        """
        Calmar ratio: annualized_return / max_drawdown.

        Returns:
            float: Return / risk ratio
        """
        mdd = self.max_drawdown
        if mdd == 0:
            return 0.0
        return self.annualized_return / mdd

    # ========== TRADE STATISTICS ==========

    @property
    def total_trades(self) -> int:
        """Number of closed trades."""
        return len(self._trades_df)

    @property
    def win_rate(self) -> float:
        """
        Percentage of winning trades.

        Returns:
            float: Wins / total_trades (0.65 = 65% win rate)
        """
        if self.total_trades == 0:
            return 0.0

        wins = (self._trades_df['pnl'] > 0).sum()
        return wins / self.total_trades

    @property
    def avg_win(self) -> float:
        """Average P&L of winning trades ($)."""
        if self._trades_df.empty:
            return 0.0
            
        wins = self._trades_df[self._trades_df['pnl'] > 0]['pnl']
        return wins.mean() if len(wins) > 0 else 0.0

    @property
    def avg_loss(self) -> float:
        """Average P&L of losing trades ($ negative value)."""
        if self._trades_df.empty:
            return 0.0
            
        losses = self._trades_df[self._trades_df['pnl'] < 0]['pnl']
        return losses.mean() if len(losses) > 0 else 0.0

    @property
    def win_loss_ratio(self) -> float:
        """
        Ratio of average win to average loss.

        Returns:
            float: avg_win / abs(avg_loss)
        """
        avg_loss = self.avg_loss
        if avg_loss == 0:
            return 0.0
        return self.avg_win / abs(avg_loss)

    @property
    def profit_factor(self) -> float:
        """
        Ratio of gross profits to gross losses.

        Returns:
            float: total_wins / abs(total_losses)
        """
        if self._trades_df.empty:
            return 0.0

        gross_profit = self._trades_df[self._trades_df['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(self._trades_df[self._trades_df['pnl'] < 0]['pnl'].sum())

        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0

        return gross_profit / gross_loss

    # ========== DATA EXPORTS ==========

    def get_transaction_log_df(self) -> pd.DataFrame:
        """
        Export transaction log as DataFrame.

        Returns:
            DataFrame with all transactions
        """
        return self.portfolio.get_transaction_log_df()

    def get_trades_df(self) -> pd.DataFrame:
        """
        Export closed trades DataFrame.

        Returns:
            DataFrame with trade details
        """
        return self._trades_df.copy()

    def get_equity_curve(self) -> pd.DataFrame:
        """
        Export equity curve DataFrame.

        Returns:
            DataFrame with date and equity columns
        """
        return self._equity_df.copy()

    # ========== SUMMARY OUTPUT ==========

    def print_summary(self):
        """Print formatted summary of results."""
        print("=" * 70)
        print(f"BACKTEST RESULTS: {self.strategy.name}")
        print("=" * 70)
        print(f"\nPeriod: {self.start_date} to {self.end_date}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")

        if not self._equity_df.empty:
            final_equity = self._equity_df.iloc[-1]['equity']
            print(f"Final Equity: ${final_equity:,.2f}")

        print(f"\n--- Returns ---")
        print(f"Total Return: {self.total_return:.2%}")
        print(f"Annualized Return: {self.annualized_return:.2%}")

        print(f"\n--- Risk ---")
        print(f"Volatility: {self.volatility:.2%}")
        print(f"Sharpe Ratio: {self.sharpe_ratio:.2f}")
        print(f"Sortino Ratio: {self.sortino_ratio:.2f}")
        print(f"Max Drawdown: {self.max_drawdown:.2%}")
        print(f"Max DD Duration: {self.max_drawdown_duration} days")
        print(f"Calmar Ratio: {self.calmar_ratio:.2f}")

        print(f"\n--- Trades ---")
        print(f"Total Trades: {self.total_trades}")
        print(f"Win Rate: {self.win_rate:.2%}")
        print(f"Avg Win: ${self.avg_win:,.2f}")
        print(f"Avg Loss: ${self.avg_loss:,.2f}")
        print(f"Win/Loss Ratio: {self.win_loss_ratio:.2f}")
        print(f"Profit Factor: {self.profit_factor:.2f}")

        print("=" * 70)

    def to_dict(self) -> dict:
        """
        Export all metrics as dict.

        Returns:
            dict: All metrics for JSON export
        """
        return {
            'strategy_name': self.strategy.name,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'initial_capital': self.initial_capital,
            'total_return': self.total_return,
            'annualized_return': self.annualized_return,
            'volatility': self.volatility,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_duration': self.max_drawdown_duration,
            'calmar_ratio': self.calmar_ratio,
            'total_trades': self.total_trades,
            'win_rate': self.win_rate,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'win_loss_ratio': self.win_loss_ratio,
            'profit_factor': self.profit_factor
        }

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (f"Results(strategy='{self.strategy.name}', "
                f"return={self.total_return:.2%}, "
                f"trades={self.total_trades})")