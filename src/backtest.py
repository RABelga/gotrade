"""Simple backtest: walk-forward rebalance on historical daily data."""
import json
from pathlib import Path
import pandas as pd

from .data import fetch_history
from .strategy import score_asset, rank_assets
from .portfolio import allocate
from .broker import PaperBroker

BASE = Path(__file__).resolve().parent.parent


def backtest(cfg: dict, rebalance_every_days: int = 20) -> dict:
    hists = {s: fetch_history(s, int(cfg.get("lookback_days", 120)) + 252) for s in cfg["universe"]}
    hists = {k: v for k, v in hists.items() if v is not None and not v.empty}
    dates = sorted(set().union(*[set(df.index) for df in hists.values()]))
    broker = PaperBroker(float(cfg.get("initial_cash", 10000)),
                         float(cfg.get("fee_per_trade_pct", 0.001)))
    equities = []
    for i, day in enumerate(dates):
        prices = {}
        for sym, df in hists.items():
            past = df[df.index <= day]
            if not past.empty:
                prices[sym] = float(past["Close"].iloc[-1])
        if not prices:
            continue
        if i % rebalance_every_days == 0:
            window = {s: df[df.index <= day].tail(int(cfg.get("lookback_days", 120)))
                      for s, df in hists.items()}
            scored = rank_assets(window, float(cfg.get("min_probability", 0.52)),
                                 float(cfg.get("min_expected_return", 0.001)))
            eq = broker.equity(prices)
            broker.rebalance(allocate(scored, eq, cfg), prices, eq)
        equities.append((day, broker.equity(prices)))
    if not equities:
        return {"error": "no data"}
    start = equities[0][1]
    end = equities[-1][1]
    ret = end / start - 1
    print(f"[backtest] {start:,.2f} -> {end:,.2f} ({ret:.2%}) over {len(equities)} days")
    return {"start": start, "end": end, "return": ret, "days": len(equities)}


if __name__ == "__main__":
    cfg = json.loads((BASE / "config.json").read_text())
    backtest(cfg)
