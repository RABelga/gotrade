"""Entry point. Add --crypto to target the crypto fund instead of stocks.

Stock fund : python run.py signals 6
Crypto fund: python run.py signals 100 --crypto
Chat serves both funds at once: python run.py chat 6
"""
import sys
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
        # Auto-trade crypto fund on Binance. Default = dry-run (safe).
        # Testnet: set BINANCE_API_KEY/SECRET env + testnet:true in config.
        # Live   : ALSO set binance.live=true in config AND pass --live.
        if not crypto_mode:
            print("trade mode is crypto-only: use python run.py trade <amt> --crypto")
            sys.exit(2)
        from src.signals import generate_signals
        from src.binance_broker import BinanceBroker
        from src.paths import files as _files
        live = "--live" in sys.argv
        sig = generate_signals(cfg, amt)
        _files(cfg)["signals"].write_text(
            __import__("json").dumps(sig, indent=2))
        broker = BinanceBroker(cfg, live=live)
        for line in broker.execute(sig.get("orders", [])):
            print(" ", line)
    elif mode == "watch":
        from src.watch import loop
        hrs = nums[1] if len(nums) > 1 else 4.0
        loop(cfg, amt, hrs)
    elif mode == "live-loop":
        from src.bot import main
        main()
    else:
        print("usage: python run.py [once|backtest|live-loop|signals <amt>|watch <amt> [hrs]|watch-once <amt>|chat <amt>|trade <amt>] [--crypto]")
