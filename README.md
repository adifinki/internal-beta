<p align="center">
  <a href="https://github.com/adifinki/internal-beta/stargazers"><img src="https://img.shields.io/github/stars/adifinki/internal-beta?style=for-the-badge&color=yellow" alt="Stars"></a>
  <a href="https://github.com/adifinki/internal-beta/blob/main/LICENSE"><img src="https://img.shields.io/github/license/adifinki/internal-beta?style=for-the-badge&color=blue" alt="License"></a>
  <a href="https://github.com/adifinki/internal-beta/commits/main"><img src="https://img.shields.io/github/last-commit/adifinki/internal-beta?style=for-the-badge&color=green" alt="Last Commit"></a>
  <img src="https://img.shields.io/badge/Self--Hosted-Ready-7289DA?style=for-the-badge&logo=keepassxc" alt="Self-Hosted">
  <img src="https://img.shields.io/badge/Maintained-Yes-2ea44f?style=for-the-badge" alt="Maintained">
</p>

# <img src="data:image/svg+xml,%3Csvg%20width%3D%2224%22%20height%3D%2224%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Ccircle%20cx%3D%229.5%22%20cy%3D%2212%22%20r%3D%226.5%22%20stroke%3D%22rgba(148%2C163%2C184%2C0.4)%22%20stroke-width%3D%221%22%2F%3E%3Ccircle%20cx%3D%2214.5%22%20cy%3D%2212%22%20r%3D%226.5%22%20stroke%3D%22rgba(148%2C163%2C184%2C0.8)%22%20stroke-width%3D%221%22%2F%3E%3C%2Fsvg%3E" height="28" /> Internal Beta

**Open-source portfolio risk analyzer** for stock investors. Measures how any stock moves relative to *your specific portfolio*. Built with Python, FastAPI, React, and real-time financial data.

> **Portfolio risk management** | **Stock screener** | **Candidate stock analysis** | **Efficient frontier** | **Value at Risk** | **GARP investing** | **Quality scoring** | **Sharpe & Sortino ratios** | **Sector stress testing** | **Momentum analysis**

---

## Why Internal Beta?

Every brokerage shows you beta vs the S&P 500. But that's not *your* risk. A stock with market beta 1.2 might have internal beta 0.3 against your specific holdings - a great diversifier *for you*.

```
beta_internal = Cov(r_candidate, r_portfolio) / Var(r_portfolio)
```
---

## What It Does

### Portfolio Risk Dashboard
Risk analysis: **Sharpe ratio**, **max drawdown**, **MCTR** (marginal contribution to risk), **correlation matrix**, **efficient frontier**, **concentration analysis** (sector/geography/currency/HHI), **hedging exposure**, and **correlation clusters**.

### Candidate Stock Analysis ("Should I buy this?")
Pick any stock. The system auto-computes the optimal number of shares using a **5-factor composite score** — Sharpe improvement, volatility reduction, diversification benefit, tail risk (CVaR), and quality-valuation fit, then shows before/after comparisons for every metric, an efficient frontier overlay, and a concentration delta.

### Stock Screener (1,000+ tickers)
Scans **S&P 400 mid-caps**. Ranks by cheap-quality score (quality x valuation). Shows **Internal Beta** and **portfolio fit** for each candidate. Filter by sector, sort by any column, download CSV. Results stream in real-time via SSE.

### Quality & GARP Scoring
Every stock gets a **quality score** (0-100) from ROIC, gross margins, FCF yield, earnings consistency, debt health, and revenue growth. Plus a **GARP score** (Growth at a Reasonable Price) from PEG ratio, earnings growth, revenue growth, and forward P/E. **Thesis health check** flags when a compounding thesis is breaking down.


### Considerations 
Evidence-based **add/trim/exit/rebalance** suggestions driven by thesis health, concentration risks, risk contribution (MCTR), momentum signals, quality-valuation alignment, and age-appropriate asset allocation. Each recommendation includes an evidence string explaining the reasoning. Tuned to your investor profile:

| Profile | Age | Target Allocation | Drawdown Threshold |
|---|---|---|---|
| Growth | < 35 | 95% equity / 5% bonds | -55% |
| Accumulation | 35-49 | 85% / 15% | -45% |
| Pre-retirement | 50-59 | 70% / 30% | -35% |
| Distribution | 60+ | 50% / 50% | -25% |

---

## Features at a Glance

| Tab | Capabilities |
|---|---|
| **My Portfolio** | Donut chart, per-stock breakdown (price/shares/value/weight), collapsible fundamentals (P/E, margins, 52-week range, business summary) |
| **Analysis** | Sharpe, max drawdown, MCTR, internal beta (leave-one-out), correlation matrix, correlation clusters, quality/GARP/thesis health, concentration (sector/geo/currency/HHI), efficient frontier, sector scenarios |
| **Test a Stock** | 5-factor optimal allocation, before/after risk deltas, Internal Beta verdict, concentration delta |
| **Find a Stock** | snp 400 sector filtering, quality sorting, Internal Beta + portfolio fit |

---

## How to Use

### 1. Enter your holdings
Type a ticker (e.g. `AAPL`, `SCHG`, `CSPX.L`), enter shares, press Enter. 

Holdings persist in the URL (`?h=AAPL:100,MSFT:50`) — bookmark or share to restore your portfolio.

### 2. My Portfolio
Donut chart sorted by position size. Hover to highlight across chart and table. Click any row to expand fundamentals.

### 3. Analysis
Loads with 2+ holdings. Shows all risk metrics, quality scores, correlation heatmap, efficient frontier with your portfolio plotted,  and actionable considerations. Hover **(i)** icons for explanations.

### 4. Test a Stock
Enter a candidate ticker. System grid-searches allocations from 1% to 40% (adapts to portfolio size) across 5 risk/quality factors. Shows the optimal allocation with a plain-English Internal Beta verdict and full before/after comparison.

### 5. Find a Stock
Streams results from 400 tickers with progress bar. Filter by sector and quality. If you have a portfolio loaded, each candidate shows Internal Beta and portfolio fit. Click "Analyze" to flow into candidate analysis.

---

## Architecture

```
Browser (React 19 + TypeScript + Recharts + Tailwind)
     |
     v
Nginx API Gateway :80
  /api/market-data/*  ->  market-data-service :8001
  /api/portfolio/*    ->  portfolio-service   :8002
  /api/risk/*         ->  risk-service        :8003
     |
     |-- market-data-service  (yfinance, prices, returns, fundamentals, quality scoring, screener)
     |-- portfolio-service    (correlation, concentration, efficient frontier, min-variance optimization)
     '-- risk-service         (candidate analysis, MCTR, internal beta, VaR, CVaR, drawdown, stress, momentum, hedging, recommendations)

Shared infrastructure:
  Redis    :6379  -- price/quality cache (24h TTL), analysis cache (30min TTL)
  Postgres :5432  -- portfolio storage
```

### API Endpoints

**market-data-service :8001**
| Endpoint | Method | Description |
|---|---|---|
| `/tickers/prices` | GET | OHLCV prices for multiple tickers (cache-aside with Redis) |
| `/tickers/returns` | GET | Log returns matrix for covariance/correlation calculations |
| `/tickers/{ticker}/info` | GET | Sector, country, fundamentals from yfinance |
| `/tickers/{ticker}/quality` | GET | Quality score, GARP score, thesis health, moat rating |
| `/screener/cheap-quality` | GET | SSE stream: scan 1,000+ tickers with real-time progress |
| `/screener/universes` | GET | Available ticker universes and their counts |

**portfolio-service :8002**
| Endpoint | Method | Description |
|---|---|---|
| `/portfolio/correlation` | GET | Pairwise correlation matrix (Pearson) |
| `/portfolio/profile` | POST | Full profile: weighted fundamentals, concentration, efficient frontier |
| `/portfolio/optimize` | POST | Min-variance rebalancing (Ledoit-Wolf covariance, no return predictions) |

**risk-service :8003**
| Endpoint | Method | Description |
|---|---|---|
| `/risk/analyze-portfolio` | POST | Complete baseline analysis with 15+ metrics and recommendations |
| `/risk/analyze-candidate` | POST | Before/after impact analysis with optimal allocation |
| `/risk/sector-impact` | POST | Sector or macro scenario analysis (tech, rates, USD, gold) |
| `/risk/batch-beta` | POST | Internal beta + correlation for multiple candidates (used by screener) |
| `/risk/recommendations` | POST | Exit/trim/rebalance recommendations with evidence |

---

## Key Financial Models

### Internal Beta (Leave-One-Out)
```
beta_internal = Cov(r_candidate, r_portfolio) / Var(r_portfolio)
```
For existing holdings, computed against the portfolio *without* that holding — avoids self-correlation inflation that inflates naive beta estimates.

### Sharpe Ratio (Geometric / CAGR-Based)
```
Sharpe = (CAGR - Rf) / sigma
CAGR = (prod(1 + r_simple))^(252/n) - 1
sigma = std(log(1 + r_simple), ddof=1) * sqrt(252)
```
Uses CAGR (not arithmetic mean) for consistency with the efficient frontier. Risk-free rate default: 4%.

```
Skips the most recent month to avoid short-term reversal noise. Trend classification: strong_up (>0.75), up, neutral, down, strong_down (<-0.75).

### MCTR (Marginal Contribution to Risk)
```
MCTR_i = (Sigma * w)_i / sigma_portfolio
```
Percentage contributions sum to 100%. Identifies which positions drive your portfolio's volatility.

### Optimal Allocation (5-Factor Composite)
Grid-searches candidate weight from 1% to 40% (adapts to portfolio size):

| Factor | Weight |
|---|---|
| Sharpe improvement | 25% |
| Volatility reduction | 25% |
| Diversification (internal beta + correlation) | 20% |
| Tail risk / CVaR improvement | 15% |
| Quality-valuation fit | 15% |

### Quality Score (0-100)
ROIC (25%), Gross margin + stability (25%), FCF yield (15%), Earnings consistency (15%), Debt health (10%), Revenue growth (10%). Only available components count — missing data does not penalize. ETFs use a simplified model (5yr return, P/E, yield, AUM, beta). Info-only fallback for holding companies and ADRs.

### GARP Score (0-100)
PEG ratio (40%), Earnings growth (25%), Revenue growth (15%), Forward P/E (20%). Only available components count.

### Thesis Health Check
Revenue trajectory, earnings growth, ROIC stability, FCF conversion, debt health across 5-year financials. Status: Strong / Monitor / Review / Broken. Uses 20% tolerance on deceleration to avoid false flags from high base rates.

### Correlation Clusters
Pairs of holdings with |correlation| >= 0.8. Flags hidden concentration — two stocks in different sectors that move together provide less diversification than expected.

### Max Drawdown
Peak-to-trough decline in cumulative wealth. Dollar figure is hypothetical: historical drawdown % applied to today's portfolio value. Includes recovery days from trough to next peak.

### Min-Variance Optimization
Ledoit-Wolf covariance shrinkage. No return predictions — uses only the covariance matrix. The only honest optimization when expected returns are unreliable.

### Efficient Frontier (Descriptive)
Historical frontier using Ledoit-Wolf covariance. Shows min-variance point, frontier curve, individual holding positions, and your portfolio's position. CAGR on Y-axis for consistency. Not a prediction — a backward-looking visualization.

---

## Tech Stack

### Backend (Python)
| Technology | Purpose |
|---|---|
| Python 3.13 | Runtime |
| FastAPI | Async REST API framework |
| Pydantic v2 | Request/response validation |
| Poetry | Dependency management |
| httpx | Async inter-service HTTP |
| yfinance | Historical prices, fundamentals, financial statements |
| PyPortfolioOpt | Min-variance optimization, Ledoit-Wolf covariance shrinkage |
| numpy / pandas | Numerical computing |
| redis-py (async) | Cache (24h prices, 30min analysis) |
| SQLAlchemy (async) + asyncpg | PostgreSQL ORM |
| pytest | unit tests |
| ruff | Linting + formatting |
| pyright | Static type checking (strict mode) |

### Frontend
| Technology | Purpose |
|---|---|
| React 19 | UI framework |
| TypeScript (strict) | Type safety |
| Vite | Build tool + dev server |
| Tailwind CSS v3 | Dark theme styling |
| Recharts | Correlation heatmap, efficient frontier, sector/geo pies, MCTR bars, drawdown chart |
| TanStack Query v5 | Data fetching, caching, loading/error states |

### Infrastructure
| Technology | Purpose |
|---|---|
| Docker Compose | 6-container local orchestration |
| Nginx | API gateway (SSE passthrough for screener) |
| Redis 7 | Shared cache layer |
| PostgreSQL 16 | Portfolio persistence |

---

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for frontend dev)
- Python 3.13 (for running tests locally)

### Quick Start

```bash
git clone <repo-url>
cd internal-beta-backend

# Production
docker compose up --build

# Development (hot reload)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

```bash
# Frontend
cd services/frontend
npm install
npm run dev    # http://localhost:3000
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API Gateway | http://localhost:80 |
| market-data docs | http://localhost:8001/docs |
| portfolio docs | http://localhost:8002/docs |
| risk docs | http://localhost:8003/docs |

---

## Design Decisions

**Why Internal Beta?** Every tool computes beta vs the S&P 500. Your actual risk depends on *your* holdings. Leave-one-out computation avoids self-correlation inflation.

**Why no max-Sharpe optimization?** Expected returns are unreliable. Max-Sharpe is highly sensitive to estimation errors. Min-variance uses only covariance (stable) and makes no predictions.

**Why Ledoit-Wolf shrinkage?** Sample covariance is noisy with few observations. Shrinkage toward scaled identity reduces estimation error. Both services use the same PyPortfolioOpt implementation for consistency.

**Why domain layer isolation?** Every service follows `routes/ -> domain/ -> infrastructure/`. Domain modules are pure Python + numpy/pandas with zero I/O imports. Unit tests run in milliseconds without mocks.

**Why async throughout?** Fetching 10 tickers sequentially: ~10s. With `asyncio.gather`: ~1s. All endpoints are `async def`.

**Why SSE for the screener?** Scanning 1,000+ tickers takes time. Server-Sent Events stream progress (phase + percentage) to the frontend in real-time. Nginx configured with `proxy_buffering off`.

---

## Running Tests

```bash
# Market-data service (59 tests)
cd services/market-data && poetry run pytest tests/ -v

# Portfolio service (54 tests)
cd services/portfolio && poetry run pytest tests/ -v

# Risk service (19 tests)
cd services/risk && poetry run pytest tests/ -v
```

 tests covering: log return computation, log-linear interpolation, Pearson correlation, Ledoit-Wolf covariance properties (symmetric, PSD), portfolio weights, quality/GARP scoring, MCTR, internal beta, screener scoring, API response shapes.

```bash
# Lint + format
poetry run ruff check . --fix && poetry run ruff format .

# Type check (strict)
poetry run pyright .

# Frontend types
cd services/frontend && npx tsc --noEmit
```

---

## Project Structure

```
internal-beta-backend/
  docker-compose.yml              # Production (6 containers)
  docker-compose.dev.yml          # Dev overrides (hot reload)
  docs/PLAN.md                    # Living project plan
  services/
    market-data/                  # Prices, returns, fundamentals, quality, screener
      src/domain/                 #   Pure computation (no I/O)
      src/infrastructure/         #   yfinance, Redis cache
      src/routes/                 #   HTTP endpoints
      src/data/                   #   Ticker universe JSON (US, Israel, Europe, EM)
      tests/                      #   59 tests
    portfolio/                    # Correlation, concentration, frontier, optimization
      src/domain/
      src/infrastructure/
      src/routes/
      tests/                      #   54 tests
    risk/                         # Internal beta, MCTR, VaR, stress, momentum, hedging, recommendations
      src/domain/                 #   13 domain modules
      src/infrastructure/
      src/routes/
      tests/                      #   19 tests
    frontend/                     # React + TypeScript + Recharts + Tailwind
      src/api/                    #   Typed API client (SSE support)
      src/components/             #   12 visualization components
      src/pages/                  #   Holdings, Dashboard, Analysis, Screener
  infrastructure/
    nginx/nginx.conf              # API gateway (SSE passthrough)
    postgres/init.sql             # DB schema
```

---

## Roadmap

| Feature | Description |
|---|---|
| **Fama-French factor regression** | 3-factor and 5-factor decomposition: market, size, value, profitability, investment factors. Show where returns actually come from. |
| **AI-powered news analysis** | LLM analysis of yfinance ticker news: regulatory risks, geopolitical exposure, supply chain shifts, competitive dynamics. |
| **Tax-loss harvesting** | Identify unrealized losses for tax benefit. Show tax savings vs portfolio impact. |
| **User authentication** | JWT auth. DB schema ready (`portfolios.user_id` nullable, ready for FK). |
| **Portfolio style scatter** | Holdings on a value-vs-growth 2D plane, sized by weight. Visual clustering detection. |
| **Benchmark comparison** | Portfolio aggregate P/E, P/B, FCF yield vs S&P 500, Russell 1000, sector averages. |
| **Rebalancing drift alerts** | Continuous monitoring when position drift exceeds thresholds. |
| **Black-Litterman** | Express views on stocks, blend with market equilibrium for robust optimization. |
| **Skewness & kurtosis** | Fat-tail risk metrics beyond Sharpe: crash probability indicators. |
| **Upside/downside capture** | How much of benchmark up-months vs down-months the portfolio captures. |
| **Hierarchical Risk Parity** | Tree-based clustering + inverse-variance. More robust than classical min-variance. |
| **Rolling correlation decay** | 60/90/180-day trailing correlations. Detect when a diversifier stops diversifying. |
| **Information Ratio** | Active return vs tracking error. Are your stock picks adding value? |
| **Brinson-Fachler attribution** | Allocation effect vs selection effect. Did outperformance come from sectors or stocks? |

---

## Keywords

`portfolio analyzer` `portfolio risk management` `stock screener` `portfolio optimization` `efficient frontier` `value at risk` `expected shortfall` `sharpe ratio` `sortino ratio` `MCTR` `marginal contribution to risk` `internal beta` `synthetic beta` `portfolio beta` `correlation matrix` `covariance shrinkage` `ledoit wolf` `min variance optimization` `GARP investing` `quality investing` `ROIC screening` `PEG ratio` `thesis health check` `economic moat` `momentum factor` `stress testing` `sector analysis` `portfolio concentration` `HHI index` `max drawdown` `CVaR` `tail risk` `fastapi` `react` `typescript` `python` `microservices` `yfinance` `pypfopt`

---

## License

MIT
