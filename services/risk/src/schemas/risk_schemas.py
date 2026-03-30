from pydantic import BaseModel


class Holding(BaseModel):
    ticker: str
    shares: float


class Candidate(BaseModel):
    ticker: str
    shares_to_add: float | None = None  # None = auto-compute optimal


class AnalyzePortfolioRequest(BaseModel):
    portfolio: list[Holding]
    period: str = "5y"
    age: int = 27


class AnalyzeCandidateRequest(BaseModel):
    portfolio: list[Holding]
    candidate: Candidate
    period: str = "5y"


class SectorImpactRequest(BaseModel):
    portfolio: list[Holding]
    sector: str
    scenario_move: float
    period: str = "5y"


class BatchBetaRequest(BaseModel):
    portfolio: list[Holding]
    candidates: list[str]
    period: str = "5y"


class RecommendationsRequest(BaseModel):
    portfolio: list[Holding]
    period: str = "5y"
    age: int = 27
