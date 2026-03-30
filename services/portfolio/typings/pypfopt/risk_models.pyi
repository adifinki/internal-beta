"""Stubs for pypfopt.risk_models — only symbols used by this service."""

from typing import Literal

import pandas as pd

class CovarianceShrinkage:
    def __init__(
        self,
        prices: pd.DataFrame,
        returns_data: bool = False,
        frequency: int = 252,
        log_returns: bool = False,
    ) -> None: ...
    def ledoit_wolf(
        self,
        shrinkage_target: Literal[
            "constant_variance", "single_factor", "constant_correlation"
        ] = "constant_variance",
    ) -> pd.DataFrame: ...
