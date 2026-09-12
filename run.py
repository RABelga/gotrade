"""Entry point. Add --crypto to target the crypto fund instead of stocks.

Stock fund : python run.py signals 6
Crypto fund: python run.py signals 100 --crypto
Chat serves both funds at once: python run.py chat 6
Auto-trade (PC only, Binance blocks US cloud IPs):
             python run.py trade-loop 100 --crypto
"""
import sys
import time
from pathlib import Path
from src.bot import load_config, run_once
from src.broker import PaperBroker
from src.backtest import backtest

BASE = Path(__file__).resolve().parent


def parse_argv(argv: list[str]):
    crypto_mode = "--crypto" in argv
    rest = [a for a in argv if a != "--crypto"]
    mode = rest[0] if rest else "once"
    nums = []
    for a in rest[1:]:
        try:
            nums.append(float(a))
        except ValueError:
            pass
    return mode, nums, crypto_mode


def do_trade(cfg: dict, amt: float, live: bool) -> list[str]:
    """One auto-trade cycle: signals -> switch-gated rebalance -> sync -> Telegram fills."""
    from src.signals import generate_signals
    from src.binance_broker import BinanceBroker
    from src.paths import files as _files
    from src import holdings as _hd
    import json as _json
    sig = generate_signals(cfg, amt)
    F = _files(cfg)
    F["signals"].write_text(_json.dumps(sig, indent=2))
    broker = BinanceBroker(cfg, live=live)
    held = _hd.load(F["holdings"])
    lines = broker.rebalance(sig.get("orders", []), held)
    for line in lines:
        print(" ", line)
    try:
        if broker.client:
            from src.data import fetch_latest_price as _px
            bals = broker.balances()
            for sym in list(held.keys()):
                if broker.base_asset(sym) not in bals:
                    _hd.remove(sym, F["holdings"])
                    held = _hd.load(F["holdings"])
            for o in sig.get("orders", []):
                base = broker.base_asset(o["symbol"])
                if bals.get(base, 0) > 0 and o["symbol"] not in held:
                    try:
                        _hd.add(o["symbol"], _px(o["symbol"]), bals[base], F["holdings"])
                    except Exception:
                        pass
    except Exception as e:
        print(f" holdings sync skipped: {e}")
    actions = [l for l in lines if not l.startswith(("HOLD", "SKIP", "DRY-RUN"))]
    if actions and broker.mode in ("LIVE", "TESTNET"):
        from src import telegram as _tg
        _tg.alert_cfg(cfg, f"🤖 {cfg.get('fund_name')}: " + " | ".join(actions))
    return lines


if __name__ == "__main__":
    mode, nums, crypto_mode = parse_argv(sys.argv[1:])
    cfg = load_config(str(BASE / "crypto_config.json") if crypto_mode
                      else str(BASE / "config.json"))
    cash = float(cfg.get("initial_cash", 10000))
    amt = nums[0] if nums else cash
    if mode == "backtest":
        backtest(cfg)
    elif mode == "once":
        broker = PaperBroker(cash, float(cfg.get("fee_per_trade_pct", 0.001)))
        print(run_once(cfg, broker))
    elif mode == "signals":
        from src.signals import print_signals
        print_signals(cfg, amt)
    elif mode == "watch-once":
        from src.watch import check_once
        check_once(cfg, amt, silent_no_change=False)
    elif mode == "chat":
        from src.chat import loop as chat_loop
        ccfg = load_config(str(BASE / "crypto_config.json"))
        chat_loop(cfg, amt, (ccfg, float(ccfg.get("initial_cash", 100))))
    elif mode == "trade":
        # Default = dry-run (safe). Testnet: BINANCE_API_KEY/SECRET env set.
        # Live: ALSO binance.live=true in config AND --live flag.
        if not crypto_mode:
            print("trade mode is crypto-only: use python run.py trade <amt> --crypto")
            sys.exit(2)
        do_trade(cfg, amt, live=("--live" in sys.argv))
    elif mode == "trade-loop":
        # Local auto-trade loop. Runs on YOUR PC because your IP works with
        # Binance while GitHub's US cloud IPs are geo-blocked.
        if not crypto_mode:
            print("trade-loop is crypto-only: use python run.py trade-loop <amt> --crypto")
            sys.exit(2)
        hrs = nums[1] if len(nums) > 1 else 2.0
        print(f"[trade-loop] auto-trading ${amt:,.2f} every {hrs}h. Ctrl+C to stop.")
        while True:
            try:
                do_trade(cfg, amt, live=("--live" in sys.argv))
            except Exception as e:
                print(f"[trade-loop] cycle failed: {e}")
            time.sleep(hrs * 3600)
    elif mode == "watch":
        from src.watch import loop
        hrs = nums[1] if len(nums) > 1 else 4.0
        loop(cfg, amt, hrs)
    elif mode == "live-loop":
        from src.bot import main
        main()
    else:
        print("usage: python run.py [once|backtest|live-loop|signals <amt>|watch <amt> [hrs]|watch-once <amt>|chat <amt>|trade <amt>|trade-loop <amt>] [--crypto]")
