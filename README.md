# Market Regime Sentinel 

![Build Status](https://img.shields.io/badge/build-stable-brightgreen)
![Status](https://img.shields.io/badge/status-forward_testing-orange)
![Platform](https://img.shields.io/badge/platform-QuantConnect-blue)

**Market Regime Sentinel** is a quantitative trading strategy designed for the QuantConnect LEAN engine. It utilizes a composite signal of inter-market correlations (Gold, Silver, Utilities, USD, and Debt) to detect "high stress" market regimes.

Based on the detected regime, the algorithm dynamically switches the portfolio allocation between aggressive equities (Risk-On) and defensive assets or cash (Risk-Off).

##  Current Project Status: **Live Paper Trading**
> **Current Phase:** Forward Testing & Validation.
The algorithm has completed the historical backtesting phase and is currently deployed in a live paper-trading environment to validate execution logic, slippage modeling, and signal stability in real-time market conditions.

##  Backtest Performance (2008 - 2024)
*The following results reflect the "Refactored Logic" implementation including the 2022 correlation-break filter.*

![Backtest Performance Graph]

| Metric | Result | Notes |
| :--- | :--- | :--- |
| **Total Return** | **2,039.40%** | Significantly outperformed SPY benchmark. |
| **Net Profit** | **$1,773,491** | On $100k starting capital. |
| **PSR** | **32.23%** | Probabilistic Sharpe Ratio indicating statistical significance. |
| **Equity Curve** | **Stable** | Successfully flattened exposure during 2020 and 2022 drawdowns. |

*(Note: Past performance is not indicative of future results. These results are from in-sample and out-of-sample historical testing.)*

## Strategy Logic

### 1. Signal Generation (The "Canary in the Coal Mine")
The algorithm monitors a specific basket of assets that historically exhibit abnormal volatility prior to equity market crashes:
* **Metal Spreads:** Gold (GLD) vs Silver (SLV)
* **Utility Demand:** Utilities (XLU) vs Industrials (XLI)
* **Safe Havens:** USD (UUP) and Short-Term Treasuries (SHY)

### 2. Regime Detection
* **Risk-On:** When volatility signals are low, the algorithm allocates 100% to **QQQ** (Nasdaq-100).
* **Risk-Off:** When stress signals breach the statistical threshold (95th percentile), the algorithm rotates into **TLT** (Long-Term Treasuries) or **Cash**.

### 3. Momentum Filter
To prevent falling into "value traps" during bond market crashes (e.g., 2022), the strategy applies a secondary momentum filter to the defensive asset. If the defensive asset is also trending down, the portfolio moves to 100% Cash.

## 🛠️ Installation & Usage

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/YOUR_USERNAME/market-regime-sentinel.git](https://github.com/YOUR_USERNAME/market-regime-sentinel.git)
    ```
2.  **Deploy on QuantConnect:**
    * Create a new project in the Algorithm Lab.
    * Copy the contents of `main.py` into your project.
    * Set the Brokerage Model to `InteractiveBrokers` (Margin account required).

## Disclaimer
This project is for **educational and research purposes only**. It is not financial advice. The strategy relies on historical correlations that may break down in future market conditions.

## Credits
Based on the "In & Out" strategy concepts developed by:
* **Peter Guenther** (Original Author)
* **Vladimir** & **Tentor Testivis** (QuantConnect Community Contributors)