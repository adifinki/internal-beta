from src.schemas.funds_schemas import FundRow, FundTrackEntry

FUND_CATALOG: list[FundTrackEntry] = [
    FundTrackEntry(
        category="kupat_gemel_lehashkaa",
        company_id="analyst",
        company_name="Analyst",
        track_id="gemel_lehaskaa_klali",
        track_name="Gemel LeHaskaa Klali",
        as_of_date="2025-12-31",
        rows=[
            FundRow(label="Equities - TA-125", pct_of_fund=0.4746 * 0.45, proxy_ticker=None),
            FundRow(label="Equities - S&P 500", pct_of_fund=0.4746 * 0.15, proxy_ticker="SPY"),
            FundRow(label="Equities - MSCI World", pct_of_fund=0.4746 * 0.40, proxy_ticker="URTH"),
            FundRow(label="Government bonds (Tel Gov Klali)", pct_of_fund=0.3100, proxy_ticker="TASEGOV.TA"),
            FundRow(label="Corporate bonds - Israeli general", pct_of_fund=0.2359 * 0.75, proxy_ticker="TASEGEN.TA"),
            FundRow(label="Corporate bonds - Global aggregate", pct_of_fund=0.2359 * 0.25, proxy_ticker="LQD"),
            FundRow(label="Cash (Makam 3-month)", pct_of_fund=0.1377, proxy_ticker="TASETBILL.TA"),
            FundRow(label="Other", pct_of_fund=0.0151, proxy_ticker=None),
        ],
    ),
]
