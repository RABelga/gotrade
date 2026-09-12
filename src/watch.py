"""Watch loop: re-check signals and Telegram-message you when something changes.

Notifies when:
- the top BUY pick changes (e.g. MSFT -> AAPL) = sell old / buy new
- all signals disappear (HOLD cash) or reappear
- market regime flips (bull <-> bear)

Usage:
    python run.py watch 6        # check every 4 hours, alert on change
    python run.py watch 6 1      # check every 1 hour
    python run.py watch-once 6   # single check (for Windows Task Scheduler)
"""
import json
import time
from pathlib import Path

from .signals import generate_signals

BASE = Path(__file__).resolve().parent.parent
STATE_FILE = BASE / "last_alert.json"


def summarize(sig: dict) -> dict:
    return {
        "symbols": [o["symbol"] for o in sig.get("orders", [])],
        "regime": (sig.get("regime") or {}).get("label"),
        "dollars": {o["symbol"]: o["dollars"] for o in sig.get("orders", [])},
    }


def load_state() -> dict | None:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return None


def describe_change(old: dict | None, new: dict) -> str | None:
    if old is None:
        if new["symbols"]:
            return f"Starting watch. Current pick: {', '.join(new['symbols'])}."
        return None
    if old["symbols"] != new["symbols"]:
        if not new["symbols"]:
            return (f"SELL signal: {', '.join(old['symbols'])} no longer passes. "
                    "Consider selling in Gotrade and holding cash.")
        if not old["symbols"]:
            return (f"BUY signal: {', '.join(new['symbols'])} now passes. "
                    "Consider buying in Gotrade.")
        return (f"SWITCH: sell {', '.join(old['symbols'])}, "
                f"buy {', '.join(new['symbols'])} in Gotrade.")
    if old.get("regime") != new.get("regime"):
        return f"Regime changed: {old.get('regime')} -> {new.get('regime')}. Review positions."
    return None


def check_once(cfg: dict, fund_amount: float, silent_no_change: bool = True) -> dict:
    sig = generate_signals(cfg, fund_amount)
    (BASE / "signals.json").write_text(json.dumps(sig, indent=2))
    new = summarize(sig)
    old = load_state()
    msg = describe_change(old, new)
    STATE_FILE.write_text(json.dumps(new, indent=2))
    if msg:
        detail = (f"{msg}\nFund ${fund_amount:,.2f} | regime={new['regime']} | "
                  f"orders={new['dollars']}")
        try:
            from . import telegram as tg
            tg.alert_cfg(cfg, f"🤖 GoTrade: {detail}")
        except Exception as e:
            print(f"[telegram] skipped: {e}")
    elif not silent_no_change:
        print("No change in signals.")
    else:
        print(f"[watch] no change (pick={new['symbols']}, regime={new['regime']})")
    return sig


def loop(cfg: dict, fund_amount: float, interval_hours: float = 4.0) -> None:
    print(f"[watch] watching ${fund_amount:,.2f} fund every {interval_hours}h. "
          "Leave this window open. Press Ctrl+C to stop.")
    while True:
        try:
            check_once(cfg, fund_amount)
        except Exception as e:
            print(f"[watch] check failed: {e}")
        time.sleep(interval_hours * 3600)
