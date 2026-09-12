"""Binance execution for the crypto fund. Three safety levels:

1. dry-run (default, no keys): prints what WOULD be traded. Always safe.
2. testnet (free fake money): keys from https://testnet.binance.vision
   (sign in -> Generate API key -> faucet USDT). Set env vars:
     setx BINANCE_API_KEY "..." / setx BINANCE_API_SECRET "..."
   and crypto_config.json -> binance.testnet: true
3. live (REAL money): ONLY when BOTH config binance.live=true AND you pass
   --live on the command line. Real keys must have Spot Trade permission
   and NEVER Withdraw permission.

Binance spot minimums (~5-10 USDT/order) are enforced: orders below
min_order_usdt are skipped with a warning.
"""
import os


def get_creds(cfg: dict) -> tuple[str | None, str | None]:
    b = (cfg or {}).get("binance") or {}
    key = os.environ.get("BINANCE_API_KEY") or b.get("api_key") or None
    sec = os.environ.get("BINANCE_API_SECRET") or b.get("api_secret") or None
    key = str(key).strip() if key else None
    sec = str(sec).strip() if sec else None
    if key in ("", "PASTE_KEY_HERE"):
        key = None
    if sec in ("", "PASTE_SECRET_HERE"):
        sec = None
    return key, sec


class BinanceBroker:
    def __init__(self, cfg: dict, live: bool = False):
        b = (cfg or {}).get("binance") or {}
        self.cfg = cfg
        self.symbols = b.get("symbols") or {}
        self.min_usdt = float(b.get("min_order_usdt", 5.0))
        self.testnet = bool(b.get("testnet", True))
        key, sec = get_creds(cfg)
        allow_live = bool(b.get("live", False)) and live
        if key and sec and allow_live:
            self.mode = "LIVE"
        elif key and sec:
            self.mode = "TESTNET"  # keys present but live not unlocked -> sandbox
        else:
            self.mode = "DRY-RUN"
        self.client = None
        if self.mode in ("LIVE", "TESTNET"):
            from binance.client import Client
            self.client = Client(key, sec, testnet=(self.mode == "TESTNET"))
        print(f"[binance] mode={self.mode}")

    def price(self, yf_symbol: str) -> float:
        pair = self.symbols.get(yf_symbol, yf_symbol.replace("-", ""))
        if self.client:
            t = self.client.get_symbol_ticker(symbol=pair)
            return float(t["price"])
        from .data import fetch_latest_price  # dry-run: Yahoo reference price
        return fetch_latest_price(yf_symbol)

    def balances(self) -> dict[str, float]:
        if not self.client:
            return {}
        out = {}
        for b in self.client.get_account()["balances"]:
            q = float(b["free"]) + float(b["locked"])
            if q > 0:
                out[b["asset"]] = q
        return out

    def base_asset(self, yf_symbol: str) -> str:
        pair = self.symbols.get(yf_symbol, yf_symbol.replace("-", ""))
        return pair.replace("USDT", "").replace("USDC", "")

    def execute(self, orders: list[dict], fund_name: str = "") -> list[str]:
        """orders: [{symbol (yf), dollars}]. Returns human-readable results."""
        results = []
        bals = self.balances() if self.client else {}
        for o in orders:
            sym, usdt = o["symbol"], float(o["dollars"])
            if usdt < self.min_usdt:
                results.append(f"SKIP {sym}: ${usdt:.2f} below ~${self.min_usdt} minimum")
                continue
            pair = self.symbols.get(sym, sym.replace("-", ""))
            if self.mode == "DRY-RUN":
                px = self.price(sym)
                results.append(f"DRY-RUN BUY {pair}: ${usdt:.2f} (~{usdt/px:.5f} @ ${px:,.2f})")
                continue
            # live/testnet market buy by quote amount
            try:
                r = self.client.order_market_buy(symbol=pair, quoteOrderQty=round(usdt, 2))
                fill = float(r.get("cummulativeQuoteQty", usdt))
                results.append(f"{self.mode} BUY {pair}: ${fill:.2f} (id {r.get('orderId')})")
            except Exception as e:
                results.append(f"FAILED {pair}: {str(e).splitlines()[0][:150]}")
        return results
