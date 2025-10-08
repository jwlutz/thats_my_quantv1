refactor positions to round trips
- return transaction logs to do analysis on
- allows for DCA, profit-taking, etc.

fractional shares!

allow for multiple exit tiggers/open triggers in a strategy

return a trade log with results to allow for analysis

vectorize it maybe?

allow for different data inputs, and use more data to allow for different triggers.
- OHLCV
- SEC files?
- news?
- public sentiment?

data needs to be:
- survivorship bias-free
- corporate actions adjusted
- include delisted secturities
- point in time constituents

***keep using yfinance for now

- store data somewhere
    - allows for analysis playground when testing strategies; want to be able to backtest in a jupyter notebook
- ML strategies
- performance reporting
- strategy returns reporting
- strategy returns reporting by month (heatmap)

- make it easy to be integrated to MCP so that AI can use the tools, and test and propose strategies


Goals for eventual generation (NOT FOR V1 just to get an idea of trajectory):
- vectorized with numba
- custom DSL and IDE for strategy definition
- MCP integration to allow agents to connect and generate/test strategies in the sandbox

Signal Generation
- Linear factor model (dot product thing)
- scoring system: signal = weight * factor + weight2 * factor2 + ...
- AI generates factor combinations, backtester weights them

- parameter optimization uses AI to select which params matter most
- feature importance via regularization (Lasso/Ridge-style)
- pruning strategy

- use brownian motion simulation to model intraday bars as random walk

- frechet distribution for risk management to model worst case scenario
- account for transaction costs, slippage, and market impact

- cross validation and walk-forward testing