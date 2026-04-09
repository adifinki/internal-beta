<p align="center">
  <a href="https://github.com/adifinki/internal-beta/stargazers"><img src="https://img.shields.io/github/stars/adifinki/internal-beta?style=for-the-badge&color=yellow" alt="Stars"></a>
  <a href="https://github.com/adifinki/internal-beta/commits/main"><img src="https://img.shields.io/github/last-commit/adifinki/internal-beta?style=for-the-badge&color=green" alt="Last Commit"></a>
  <img src="https://img.shields.io/badge/Self--Hosted-Ready-7289DA?style=for-the-badge&logo=docker" alt="Self-Hosted">
  <a href="https://internal-beta.adifinki.com/"><img src="https://img.shields.io/badge/Live-Demo-brightgreen?style=for-the-badge&logo=google-chrome&logoColor=white" alt="Live Demo"></a>
</p>

# 📈 Internal Beta
> **Stop measuring risk against the S&P 500. Measure it against *Your* Portfolio.**

**Internal Beta** is a professional-grade, self-hosted risk engine for stock investors. While standard tools compare stocks to the "Market," this system calculates how a stock moves relative to **your specific holdings**. 

Built with **Python 3.13 (FastAPI)**, **React 19**, and **Real-time Financial Data**, it identifies if a new stock is a true diversifier or just adding hidden concentration to your wealth.

---

## 📺 Demo
<p align="center">
  <video src="assets/demo.mp4" width="100%" controls autoplay loop muted></video>
</p>

---

## ✨ Why Internal Beta?

Every brokerage shows you Beta vs the S&P 500. But that's not *your* risk. 
* **The Insight:** A stock with a market beta of 1.2 might have an **Internal Beta of 0.3** against your specific portfolio — making it a powerful diversifier *for you*.
* **The Math:** We use **Leave-One-Out Covariance** to avoid self-correlation inflation and **Ledoit-Wolf Shrinkage** for stable risk estimation.

---

## 🛠️ What It Does

### 📊 Portfolio Risk Dashboard
Comprehensive analysis of your current state: **Sharpe ratio**, **Max Drawdown**, **MCTR** (Marginal Contribution to Risk), **Correlation Clusters**, and **Efficient Frontier** visualization.

### 🔍 Candidate Analysis ("Should I buy this?")
Pick any stock. The system runs a **5-factor composite score** (Sharpe improvement, Volatility reduction, Diversification benefit, Tail risk, and Quality-Valuation fit) to show you the optimal number of shares to add.

### ⚡ Smart Stock Screener
Scans **S&P 400** in real-time via SSE. Ranks candidates by **Cheap-Quality Score** (Quality x Valuation) and instantly shows their **Internal Beta** fit for your specific portfolio.

### 🛡️ Thesis Health Check
Automated monitoring of **ROIC**, **Gross Margins**, **FCF Yield**, and **Debt Health**. The system flags "Broken Theses" when fundamental compounding signals start to decelerate.

---

## 🏗️ Architecture & Tech Stack
The system is built as a high-performance, asynchronous microservices suite:

* **Frontend:** React 19, TypeScript, Tailwind CSS, Recharts (Heatmaps & Frontiers).
* **Backend:** Python 3.13, FastAPI (Async), Pydantic v2, Poetry.
* **Data Engine:** `yfinance` for data, `PyPortfolioOpt` for Ledoit-Wolf covariance shrinkage.
* **Infrastructure:**
    * **Nginx:** API Gateway with SSE passthrough.
    * **Redis:** Shared cache for price/analysis (30min - 24h TTL).
    * **PostgreSQL:** Secure portfolio persistence.

---

## 🚀 Quick Start (Docker)
Ensure you have **Docker** and **Docker Compose** installed, then run:

```bash
git clone [https://github.com/adifinki/internal-beta.git](https://github.com/adifinki/internal-beta.git)
cd internal-beta
docker compose up --build
