from pydantic import BaseModel


class Holding(BaseModel):
    ticker: str
    shares: float


class CorrelationResponse(BaseModel):
    # Nested dict so the UI can look up any cell by matrix[row_ticker][col_ticker].
    # Example: matrix["AAPL"]["MSFT"] → 0.62
    matrix: dict[str, dict[str, float]]
    # Explicit ordered list of tickers — dict key order in JSON is not
    # guaranteed to be consistent, so the frontend uses this to render
    # columns in a fixed, predictable order.
    tickers: list[str]


class OptimizeRequest(BaseModel):
    holdings: list[Holding]
    period: str = "5y"
    # Used only to compute the informative Sharpe ratio — NOT an optimization target.
    risk_free_rate: float = 0.04


class OptimizeResponse(BaseModel):
    optimized_weights: dict[str, float]
    # All return/Sharpe fields are historical — descriptive, not predictive.
    historical_annual_return: float
    annual_volatility: float
    historical_sharpe: float
    current_weights: dict[str, float]
    # Positive = buy, negative = sell (in shares).
    rebalancing_trades: dict[str, float]
