"""Adaptive learning: the bot tracks its own prediction accuracy and the
market regime, then adjusts future signals.

- Memory (memory.json): every cycle's predicted prob + price per symbol.
  After 5 trading days, predictions are settled (was it right?) and each
  symbol earns a trust score from its recent hit-rate.
- Calibration: low-trust symbols get their probability shrunk toward 50%,
  so the bot stops betting big on assets it keeps misreading.
- Regime filter: if SPY (or the universe average) is below its 50-day
  average -> bear regime: demand higher probability and halve sizes.
"""
import json
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent.parent
MEMORY_FILE = BASE / "memory.json"
SETTLE_DAYS = 5
MAX_RECORDS = 1000


def load_memory() -> list[dict]:
    try:
        data = json.loads(MEMORY_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_memory(mem: list[dict]) -> None:
    MEMORY_FILE.write_text(json.dumps(mem[-MAX_RECORDS:], indent=2))


def record(mem: list[dict], scored) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for s in scored:
        mem.append({
            "date": now,
            "symbol": s.symbol,
            "prob_up": round(float(s.prob_up), 4),
            "price": float(s.price),
            "settled": False,
        })


def settle(mem: list[dict], histories: dict) -> int:
    """Settle predictions old enough to judge. Returns count newly settled."""
    n = 0
    for r in mem:
        if r.get("settled"):
            continue
        df = histories.get(r["symbol"])
        if df is None or df.empty:
            continue
        import pandas as pd
        idx = df.index
        try:
            rec_ts = pd.Timestamp(r["date"])
            if rec_ts.tzinfo is None:
                rec_ts = rec_ts.tz_localize("UTC")
            if idx.tz is not None:
                rec_ts = rec_ts.tz_convert(idx.tz)
            try:
                rec_ts = rec_ts.as_unit(idx.unit)  # pandas 2/3 unit match (ns/us/ms)
            except Exception:
                pass
        except Exception:
            continue
        pos = idx.searchsorted(rec_ts)
        if pos >= len(idx) or pos + SETTLE_DAYS >= len(idx):
            continue  # not enough future data yet
        p0 = float(df["Close"].iloc[pos])
        p1 = float(df["Close"].iloc[pos + SETTLE_DAYS])
        fwd = p1 / p0 - 1.0 if p0 > 0 else 0.0
        predicted_up = float(r["prob_up"]) > 0.5
        r["settled"] = True
        r["fwd_return"] = round(fwd, 5)
        r["correct"] = bool(predicted_up == (fwd > 0))
        n += 1
    return n


def accuracy(mem: list[dict], symbol: str, last_n: int = 30) -> tuple[float | None, int]:
    recs = [r for r in mem if r.get("symbol") == symbol and r.get("settled")]
    recs = recs[-last_n:]
    if not recs:
        return None, 0
    acc = sum(1 for r in recs if r.get("correct")) / len(recs)
    return acc, len(recs)


def trust(mem: list[dict], symbol: str) -> float:
    """0.4..1.0 multiplier. Needs 5+ settled predictions before judging."""
    acc, n = accuracy(mem, symbol)
    if acc is None or n < 5:
        return 1.0
    return float(max(0.4, min(1.0, acc / 0.6)))


def calibrate(scored: list, mem: list[dict]) -> list:
    """Shrink each symbol's prob toward 50% by its trust score."""
    for s in scored:
        t = trust(mem, s.symbol)
        s.prob_up = float(0.5 + (s.prob_up - 0.5) * t)
        s.expected_return = float(s.expected_return * t)
        s.kelly = float(max(0.0, s.kelly * t))
        s.trust = t  # type: ignore[attr-defined]
    scored.sort(key=lambda s: (s.expected_return, s.prob_up), reverse=True)
    return scored


def regime(histories: dict) -> dict:
    """Bull/bear from SPY 50-day trend, else universe-average momentum."""
    try:
        ref = histories.get("SPY")
        if ref is None:
            ref = next(iter(histories.values()))
        close = ref["Close"].astype(float)
        ma50 = close.rolling(50).mean().iloc[-1]
        last = close.iloc[-1]
        if last < ma50:
            return {"label": "bear", "size_mult": 0.5, "prob_bump": 0.03,
                    "reason": f"trend below 50d avg ({last:.0f} < {ma50:.0f})"}
        return {"label": "bull", "size_mult": 1.0, "prob_bump": 0.0,
                "reason": f"trend above 50d avg ({last:.0f} > {ma50:.0f})"}
    except Exception:
        return {"label": "unknown", "size_mult": 1.0, "prob_bump": 0.0, "reason": "n/a"}


def stats_line(mem: list[dict], symbols: list[str]) -> str:
    parts = []
    for sym in symbols:
        acc, n = accuracy(mem, sym)
        if acc is None:
            parts.append(f"{sym}: learning ({n} settled)")
        else:
            parts.append(f"{sym}: {acc:.0%} hit-rate ({n})")
    return " | ".join(parts)
