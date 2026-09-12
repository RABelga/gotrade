"""Main bot loop: score universe -> allocate -> rebalance paper portfolio."""
import json
import time
from pathlib import Path

from .data import fetch_all
from .strategy import rank_assets
from .portfolio import allocate
from .broker import PaperBroker
from . import learner

BASE = Path(__file__).resolve().parent.parent


def load_config(path: str | None = None) -> dict:
    p = Path(path) if path else BASE / "config.json"
    return json.loads(p.read_text())


def run_once(cfg: dict, broker: PaperBroker) -> dict:
    histories = fetch_all(cfg["universe"], int(cfg.get("lookback_days", 120)))
    if not histories:
        print("[bot] no data fetched")
        return {"equity": broker.cash, "targets": {}}

    scored = rank_assets(
        histories,
        min_prob=float(cfg.get("min_probability", 0.52)),
        min_expected=float(cfg.get("min_expected_return", 0.001)),
    )
    # --- adaptive learning: settle old predictions, calibrate, regime check ---
    mem = learner.load_memory(cfg)
    settled = learner.settle(mem, histories)
    scored = learner.calibrate(scored, mem)
    reg = learner.regime(histories)
    if reg["prob_bump"]:
        scored = [s for s in scored
                  if s.prob_up >= float(cfg.get("min_probability", 0.52)) + reg["prob_bump"]]
    learner.record(mem, scored)
    learner.save_memory(mem, cfg)
    print(f"[learn] {reg['label']} market ({reg['reason']}) | settled {settled} old calls")
    print(f"[learn] {learner.stats_line(mem, list(histories.keys()))}")
    prices = {s.symbol: s.price for s in
              [__import__("src.strategy", fromlist=["score_asset"]).score_asset(sym, df)
               for sym, df in histories.items()] if s is not None}

    print(f"[bot] scored {len(scored)} candidates:")
    for s in scored[:5]:
        print(f"  {s.symbol}: p={s.prob_up:.2%} exp={s.expected_return:.4f} "
              f"kelly={s.kelly:.2f} mom20={s.momentum_20d:.2%} sharpe={s.sharpe:.2f}")

    equity = broker.equity(prices)
    targets = allocate(scored, equity, cfg)
    if reg["size_mult"] != 1.0:
        targets = {k: v * reg["size_mult"] for k, v in targets.items()}
    print(f"[bot] equity=${equity:,.2f} cash=${broker.cash:,.2f} targets={targets}")

    broker.check_stops(prices, float(cfg.get("stop_loss_pct", 0.08)),
                       float(cfg.get("take_profit_pct", 0.25)))
    broker.rebalance(targets, prices, equity)
    return {"equity": broker.equity(prices), "targets": targets, "prices": prices}


def main():
    cfg = load_config()
    assert cfg.get("mode", "paper") == "paper", "Live mode not implemented - stay on paper."
    broker = PaperBroker(float(cfg.get("initial_cash", 10000)),
                         float(cfg.get("fee_per_trade_pct", 0.001)))
    interval = float(cfg.get("rebalance_interval_hours", 24)) * 3600
    print(f"[bot] {cfg.get('fund_name')} starting, paper cash=${broker.cash:,.2f}")
    while True:
        try:
            run_once(cfg, broker)
        except Exception as e:
            print(f"[bot] cycle error: {e}")
        print(f"[bot] sleeping {interval/3600:.1f}h...")
        time.sleep(interval)


if __name__ == "__main__":
    main()
