"""Brokers: PaperBroker for simulation + stub for live trading.

Start with PaperBroker. Only wire real money after backtests + small paper run.
"""
import time


class PaperBroker:
    def __init__(self, cash: float, fee_pct: float = 0.001):
        self.cash = float(cash)
        self.positions: dict[str, dict] = {}  # symbol -> {qty, avg_price}
        self.fee_pct = fee_pct
        self.history: list[dict] = []

    def equity(self, prices: dict[str, float]) -> float:
        eq = self.cash
        for sym, pos in self.positions.items():
            eq += pos["qty"] * prices.get(sym, pos["avg_price"])
        return eq

    def buy(self, symbol: str, notional: float, price: float):
        if notional <= 0 or price <= 0:
            return
        notional = min(notional, self.cash)
        if notional < 1.0:
            return
        fee = notional * self.fee_pct
        qty = (notional - fee) / price
        self.cash -= notional
        pos = self.positions.get(symbol, {"qty": 0.0, "avg_price": price})
        total_qty = pos["qty"] + qty
        pos["avg_price"] = (pos["qty"] * pos["avg_price"] + qty * price) / total_qty if total_qty else price
        pos["qty"] = total_qty
        self.positions[symbol] = pos
        self.history.append({"t": time.time(), "side": "buy", "symbol": symbol, "qty": qty, "price": price})

    def sell(self, symbol: str, qty: float, price: float):
        pos = self.positions.get(symbol)
        if not pos or qty <= 0:
            return
        qty = min(qty, pos["qty"])
        proceeds = qty * price
        fee = proceeds * self.fee_pct
        self.cash += proceeds - fee
        pos["qty"] -= qty
        if pos["qty"] < 1e-9:
            del self.positions[symbol]
        self.history.append({"t": time.time(), "side": "sell", "symbol": symbol, "qty": qty, "price": price})

    def rebalance(self, targets: dict[str, float], prices: dict[str, float], equity: float):
        # Sell what is no longer wanted
        for sym in list(self.positions.keys()):
            if sym not in targets and sym in prices:
                self.sell(sym, self.positions[sym]["qty"], prices[sym])
        # Buy / trim to targets
        for sym, w in targets.items():
            if sym not in prices:
                continue
            target_value = equity * w
            cur_value = self.positions.get(sym, {"qty": 0.0})["qty"] * prices[sym]
            diff = target_value - cur_value
            if diff > 1.0:
                self.buy(sym, diff, prices[sym])
            elif diff < -1.0:
                self.sell(sym, -diff / prices[sym], prices[sym])

    def check_stops(self, prices: dict[str, float], stop_pct: float, take_pct: float):
        for sym in list(self.positions.keys()):
            if sym not in prices:
                continue
            pos = self.positions[sym]
            pnl = prices[sym] / pos["avg_price"] - 1.0
            if pnl <= -stop_pct or pnl >= take_pct:
                self.sell(sym, pos["qty"], prices[sym])
                print(f"[risk] exited {sym} pnl={pnl:.2%}")


class LiveBrokerStub:
    """Plug your real broker API (Alpaca / Binance / IBKR) here.

    Implement buy/sell/equity/positions with your API keys.
    Keep paper mode until you are consistently profitable in backtest.
    """
    def __init__(self, *a, **kw):
        raise NotImplementedError("Live trading not wired. Use mode='paper' or implement LiveBrokerStub.")
