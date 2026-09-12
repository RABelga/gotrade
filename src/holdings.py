"""Holdings tracker: because Gotrade has no API, you tell the bot what you
bought (Telegram: /bought MSFT 495.63). Every check then compares live
price vs your entry and alerts on take-profit or stop-loss.

File: holdings.json  {SYMBOL: {qty, buy_price, date}}
"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
FILE = BASE / "holdings.json"


def _file(fp=None) -> Path:
    return Path(fp) if fp else FILE


def load(fp=None) -> dict:
    try:
        d = json.loads(_file(fp).read_text())
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save(h: dict, fp=None) -> None:
    _file(fp).write_text(json.dumps(h, indent=2))


def add(symbol: str, price: float, qty: float = 0.0, fp=None) -> None:
    from datetime import datetime, timezone
    h = load(fp)
    h[symbol.upper()] = {"qty": float(qty), "buy_price": float(price),
                         "date": datetime.now(timezone.utc).isoformat()}
    save(h, fp)


def remove(symbol: str, fp=None) -> bool:
    h = load(fp)
    if symbol.upper() in h:
        del h[symbol.upper()]
        save(h, fp)
        return True
    return False


def check_targets(holdings: dict, prices: dict, cfg: dict) -> list[str]:
    """Alert strings for holdings hitting take-profit or stop-loss.

    Fires once per crossing (flags stored on the position); re-arms if price
    falls 3pp back below/above the line. Mutates holdings — caller must save.
    """
    msgs = []
    tp = float(cfg.get("take_profit_pct", 0.25))
    sl = float(cfg.get("stop_loss_pct", 0.08))
    for sym, pos in holdings.items():
        if sym not in prices or not pos.get("buy_price"):
            continue
        pnl = prices[sym] / pos["buy_price"] - 1.0
        if pnl >= tp and not pos.get("tp_alerted"):
            msgs.append(f"TAKE PROFIT: {sym} +{pnl:.1%} "
                        f"(${pos['buy_price']:.2f} -> ${prices[sym]:.2f}). Consider selling in Gotrade.")
            pos["tp_alerted"] = True
        elif pnl < tp - 0.03:
            pos["tp_alerted"] = False
        if pnl <= -sl and not pos.get("sl_alerted"):
            msgs.append(f"STOP LOSS: {sym} {pnl:.1%} "
                        f"(${pos['buy_price']:.2f} -> ${prices[sym]:.2f}). Consider selling in Gotrade.")
            pos["sl_alerted"] = True
        elif pnl > -sl + 0.03:
            pos["sl_alerted"] = False
    return msgs


def status(holdings: dict, prices: dict) -> str:
    if not holdings:
        return "No holdings tracked. Record one: /bought MSFT 495.63"
    lines = []
    for sym, pos in holdings.items():
        if sym in prices and pos.get("buy_price"):
            pnl = prices[sym] / pos["buy_price"] - 1.0
            lines.append(f"{sym}: {pnl:+.1%} (${pos['buy_price']:.2f} -> ${prices[sym]:.2f})")
        else:
            lines.append(f"{sym}: price unavailable")
    return "Holdings:\n" + "\n".join(lines)
