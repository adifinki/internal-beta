from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class Period(StrEnum):
    DAY = "1d"
    WEEK = "5d"
    MONTH = "1mo"
    YEAR = "1y"
    MAX = "5y"
    TEN_YEAR = "10y"


class Price(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    open: float = Field(alias="Open")
    high: float = Field(alias="High")
    low: float = Field(alias="Low")
    close: float = Field(alias="Close")
    volume: int = Field(alias="Volume")
    dividends: float = Field(alias="Dividends")
    stock_splits: float = Field(alias="Stock Splits")

    @staticmethod
    def from_yfinance(records: list[dict[str, Any]]) -> list["Price"]:
        """Map yfinance record dicts (Title Case keys) to `Price` models."""
        return _PRICE_LIST_ADAPTER.validate_python(records)


# Module-level adapter — TypeAdapter construction is expensive (builds a
# validation schema), so it must not be instantiated on every call.
_PRICE_LIST_ADAPTER: TypeAdapter[list[Price]] = TypeAdapter(list[Price])
