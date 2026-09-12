"""Entry point: once|backtest|live-loop|signals|watch|watch-once."""
import sys
from src.bot import load_config, run_once
from src.broker import PaperBroker
from src.backtest import backtest

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "once"
    cfg = load_config()
    if mode == "backtest":
        backtest(cfg)
    elif mode == "once":
        broker = PaperBroker(float(cfg.get("initial_cash", 10000)),
                             float(cfg.get("fee_per_trade_pct", 0.001)))
        print(run_once(cfg, broker))
    elif mode == "signals":
        from src.signals import print_signals
        amt = float(sys.argv[2]) if len(sys.argv) > 2 else float(cfg.get("initial_cash", 10000))
        print_signals(cfg, amt)
    elif mode == "watch-once":
        from src.watch import check_once
        amt = float(sys.argv[2]) if len(sys.argv) > 2 else float(cfg.get("initial_cash", 10000))
        check_once(cfg, amt, silent_no_change=False)
    elif mode == "chat":
        from src.chat import loop as chat_loop
        amt = float(sys.argv[2]) if len(sys.argv) > 2 else float(cfg.get("initial_cash", 10000))
        chat_loop(cfg, amt)
    elif mode == "watch":
        from src.watch import loop
        amt = float(sys.argv[2]) if len(sys.argv) > 2 else float(cfg.get("initial_cash", 10000))
        hrs = float(sys.argv[3]) if len(sys.argv) > 3 else 4.0
        loop(cfg, amt, hrs)
    elif mode == "live-loop":
        from src.bot import main
        main()
    else:
        print("usage: python run.py [once|backtest|live-loop|signals <amt>|watch <amt> [hrs]|watch-once <amt>|chat <amt>]")
