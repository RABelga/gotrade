"""Gotrade manual signals: bot can't place orders inside the Gotrade app
(Gotrade offers no retail trading API), so this generates copy-into-app orders.

Usage:
    python run.py signals [fund_amount]
    e.g. python run.py signals 5000
"""
import json
from pathlib import Path
from datetime import datetime, timezone

from .data import fetch_all
from .strategy import rank_assets, score_asset
from .portfolio import allocate
from . import learner

BASE = Path(__file__).resolve().parent.parent


def generate_signals(cfg: dict, fund_amount: float) -> dict:
    histories = fetch_all(cfg["universe"], int(cfg.get("lookback_days", 120)))
    scored = rank_assets(
        histories,
        min_prob=float(cfg.get("min_probability", 0.52)),
        min_expected=float(cfg.get("min_expected_return", 0.001)),
    )
    mem = learner.load_memory()
    learner.settle(mem, histories)
    scored = learner.calibrate(scored, mem)
    reg = learner.regime(histories)
    if reg["prob_bump"]:
        scored = [s for s in scored
                  if s.prob_up >= float(cfg.get("min_probability", 0.52)) + reg["prob_bump"]]
    learner.record(mem, scored)
    learner.save_memory(mem)
    prices = {}
    for sym, df in histories.items():
        s = score_asset(sym, df)
        if s is not None:
            prices[sym] = s.price

    targets = allocate(scored, fund_amount, cfg)
    if reg["size_mult"] != 1.0:
        targets = {k: v * reg["size_mult"] for k, v in targets.items()}

    orders = []
    for s in scored:
        if s.symbol not in targets:
            continue
        w = targets[s.symbol]
        dollars = fund_amount * w
        qty = dollars / s.price if s.price > 0 else 0.0
        orders.append({
            "symbol": s.symbol,
            "action": "BUY",
            "weight_pct": round(w * 100, 2),
            "dollars": round(dollars, 2),
            "est_price": round(s.price, 2),
            "est_qty": round(qty, 4),
            "prob_up": round(s.prob_up, 4),
            "expected_return": round(s.expected_return, 5),
        })

    cash_reserve = round(fund_amount * float(cfg.get("cash_reserve_pct", 0.05)), 2)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fund_amount": fund_amount,
        "cash_reserve": cash_reserve,
        "regime": reg,
        "learning": {s: {"trust": round(learner.trust(mem, s), 3),
                         "accuracy": learner.accuracy(mem, s)} for s in cfg["universe"]},
        "orders": orders,
        "note": "Execute as market BUY orders in Gotrade app (fractional from $1). Re-run daily.",
    }


def print_signals(cfg: dict, fund_amount: float):
    sig = generate_signals(cfg, fund_amount)
    out_path = BASE / "signals.json"
    out_path.write_text(json.dumps(sig, indent=2))

    print(f"\n=== GoTrade signals (fund ${fund_amount:,.2f}) ===")
    print(f"Market regime: {sig.get('regime', {}).get('label')} ({sig.get('regime', {}).get('reason')})")
    print(f"Cash reserve: keep ~${sig['cash_reserve']:,.2f} uninvested")
    if not sig["orders"]:
        print("No asset passes the probability filter right now -> HOLD cash.")
    for o in sig["orders"]:
        print(f"  BUY {o['symbol']}: ${o['dollars']:,.2f} (~{o['est_qty']} sh @ ~${o['est_price']}) "
              f"| {o['weight_pct']}% | p={o['prob_up']:.1%}")
    print(f"\nSaved to {out_path}")
    print("In Gotrade app: buy each symbol as a market order for the dollar amount shown.")
    return sig
