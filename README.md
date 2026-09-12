# GoTrade Auto-Invest Bot

Picks the assets with the **highest estimated probability of gain** each cycle and sizes positions with fractional Kelly.

> ⚠️ No bot can guarantee fund growth. This is educational / paper-trading software, not financial advice. Never run live with money you can't afford to lose.

## How "highest probability" works

For each symbol in `config.json` (`src/strategy.py`):
1. Win-rate last 60 days, 20-day momentum, Sharpe ratio → blended into `prob_up` via sigmoid
2. `expected_return = p*avg_win - (1-p)*avg_loss`
3. Filter `prob_up >= min_probability` (default 52%) and `expected > min_expected_return`
4. Rank by expected return, take top `max_positions`
5. Size with half-Kelly, capped per-asset, with cash reserve + stop-loss/take-profit (`src/broker.py`)

## Setup (Windows)

1. Install Python 3.10+ from https://www.python.org/downloads/ (tick **Add to PATH**)
2. Open PowerShell in this folder:
```powershell
pip install -r requirements.txt
python run.py once        # single paper cycle
python run.py backtest    # historical test
python run.py live-loop   # rebalance every rebalance_interval_hours
```

Edit `config.json` to change universe, cash, risk limits. Default universe: SPY, QQQ, AAPL, MSFT, BTC-USD, ETH-USD — free Yahoo Finance data, no API key.

## Files
- `config.json` — fund settings
- `src/data.py` — price fetching
- `src/strategy.py` — probability scoring
- `src/portfolio.py` — Kelly allocation
- `src/broker.py` — PaperBroker (+ LiveBrokerStub placeholder)
- `src/bot.py` — main loop
- `src/backtest.py` — walk-forward test
- `run.py` — CLI entry

## Going live (only after paper profits)
`src/broker.py: LiveBrokerStub` must be implemented with Alpaca/Binance/IBKR keys. Keep `mode: paper` until backtest + 1-2 months paper are solid.

## Next steps you can ask for
- Add ML model (logistic / XGBoost) for `prob_up`
- Add Telegram/Discord alerts, dashboard, trailing stops
- Wire Alpaca or Binance live trading
